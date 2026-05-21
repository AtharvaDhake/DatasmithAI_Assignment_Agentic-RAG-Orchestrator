import json
import httpx
import logging
import asyncio
from fastapi import UploadFile
from typing import Optional

from settings import get_settings
from models import IntentLabel, IntentResult, AgentResponse, ExecutionPlan
from tools import TOOL_MAP
from tools import audio as audio_tool
from parsers import parse_pdf_with_fallback, parse_image_with_fallback
from prompts import INTENT_PROMPT

logger = logging.getLogger(__name__)

async def _classify_intent(query: str, content_preview: str, file_type: str, history: list = None) -> IntentResult:
    settings = get_settings()

    prompt = INTENT_PROMPT.format(
        query=query,
        content_preview=content_preview[:600] if content_preview else "none",
        file_type=file_type or "none"
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"response_mime_type": "application/json"}
    }

    gemini_json_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key=" + settings.gemini_api_key

    for attempt in range(settings.max_retries):
        try:
            async with httpx.AsyncClient(timeout=settings.intent_classification_timeout) as client:
                resp = await client.post(gemini_json_url, json=payload)
                resp.raise_for_status()
                raw = resp.json()

            gemini_text = raw["candidates"][0]["content"]["parts"][0]["text"].strip()

            if gemini_text.startswith("```json"):
                gemini_text = gemini_text[7:]
            elif gemini_text.startswith("```"):
                gemini_text = gemini_text[3:]
            if gemini_text.endswith("```"):
                gemini_text = gemini_text[:-3]

            parsed = json.loads(gemini_text.strip())

            return IntentResult(
                intent=IntentLabel(parsed.get("intent", "conversational")),
                confidence=float(parsed.get("confidence", 0.5)),
                needs_clarification=bool(parsed.get("needs_clarification", False)),
                clarification_question=parsed.get("clarification_question"),
                reasoning=parsed.get("reasoning", ""),
            )
        except Exception as e:
            logger.warning(f"Classification attempt {attempt + 1} failed: {e}")
            if attempt < settings.max_retries - 1:
                await asyncio.sleep(settings.retry_base_delay * (2 ** attempt))
                continue
            return IntentResult(
                intent=IntentLabel.CONVERSATIONAL,
                confidence=0.4,
                needs_clarification=False,
                reasoning="Fallback to conversational due to error",
            )

async def run(query: str, file: Optional[UploadFile] = None, history: str = "[]") -> AgentResponse:
    plan = ExecutionPlan(plan_description="Agent processing pipeline")
    execution_log = []
    extracted_text = ""
    file_bytes = b""
    mime_type = ""
    settings = get_settings()

    try:
        parsed_history = json.loads(history) if history else []
    except Exception:
        parsed_history = []

    query_is_empty = not query.strip()
    file_is_present = file is not None

    if query_is_empty and file_is_present:
        mime_type = file.content_type or ""
        execution_log.append(f"File received: {file.filename} ({mime_type or 'unknown'}, 0KB)")
        return AgentResponse(
            response_type="clarification",
            result="I see you've uploaded a file. Please tell me what you'd like me to do with it.",
            execution_log=execution_log,
            intent=IntentLabel.UNCLEAR.value,
            execution_plan=plan,
        )
    elif query_is_empty and not file_is_present:
        return AgentResponse(
            response_type="clarification",
            result="Please provide a query or upload a file.",
            execution_log=execution_log,
            intent=IntentLabel.UNCLEAR.value,
            execution_plan=plan,
        )

    if file_is_present:
        mime_type = file.content_type or ""
        file_bytes = await file.read()
        file_size_kb = len(file_bytes) // 1024
        execution_log.append(f"File received: {file.filename} ({mime_type}, {file_size_kb}KB)")

        if mime_type == settings.allowed_pdf_type:
            execution_log.append("Extracting text from image/PDF")
            pdf_result = await parse_pdf_with_fallback(file_bytes, query, settings, execution_log)
            extracted_text = pdf_result.get("text", "")
        elif mime_type in settings.allowed_image_types:
            execution_log.append("Extracting text from image/PDF")
            img_result = await parse_image_with_fallback(file_bytes, query, settings, execution_log)
            extracted_text = img_result.get("text", "")
        elif mime_type in settings.allowed_audio_types:
            execution_log.append("Extracting text from audio")
            audio_out = await audio_tool.run(file_bytes=file_bytes, file=file, query=query)
            if hasattr(audio_out, "execution_log") and audio_out.execution_log:
                execution_log.extend(audio_out.execution_log)
            return AgentResponse(
                response_type="answer",
                result=audio_out.result,
                extracted_text=audio_out.extracted_text,
                execution_log=execution_log,
                intent=audio_out.intent.value,
                metadata=audio_out.metadata,
                execution_plan=plan,
            )
    else:
        # Context memory feature completely removed (do not carry forward extracted document text from past turns)
        pass

    execution_log.append("Classifying intent via Gemini")
    intent = await _classify_intent(
        query=query,
        content_preview=extracted_text,
        file_type=mime_type,
        history=parsed_history
    )

    execution_log.append(f"Intent: {intent.intent.value} (confidence: {intent.confidence:.2f}) – {intent.reasoning}")

    if intent.needs_clarification:
        execution_log.append("Intent requires clarification")
        return AgentResponse(
            response_type="clarification",
            result=intent.clarification_question or "Could you clarify your request?",
            extracted_text=extracted_text or None,
            execution_log=execution_log,
            intent=intent.intent.value,
            execution_plan=plan,
        )

    execution_log.append(f"Dispatching to: {intent.intent.value}")
    tool_fn = TOOL_MAP.get(intent.intent, TOOL_MAP[IntentLabel.CONVERSATIONAL])

    try:
        tool_out = await tool_fn(
            query=query,
            text=extracted_text,
            file_bytes=file_bytes,
            mime_type=mime_type,
            file=None,
            history=parsed_history,
        )
    except Exception as e:
        logger.error(f"Tool error: {e}")
        execution_log.append(f"Error: {str(e)}")
        return AgentResponse(
            response_type="answer",
            result=f"Processing error: {str(e)}",
            execution_log=execution_log,
            intent=intent.intent.value,
            execution_plan=plan,
        )

    if hasattr(tool_out, "execution_log") and tool_out.execution_log:
        execution_log.extend(tool_out.execution_log)

    return AgentResponse(
        response_type=tool_out.response_type,
        result=tool_out.result,
        extracted_text=tool_out.extracted_text or (extracted_text or None),
        execution_log=execution_log,
        intent=tool_out.intent.value,
        metadata=tool_out.metadata,
        execution_plan=plan,
    )

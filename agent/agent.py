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
    history_lines = [f"{'User' if msg.get('role') == 'user' else 'Agent'}: {msg.get('content', '')[:100]}" for msg in (history or [])[-6:]]
    history_context = "\n".join(history_lines) if history_lines else "None"

    prompt = INTENT_PROMPT.format(
        query=query,
        content_preview=content_preview[:600] if content_preview else "none",
        file_type=file_type or "none",
        history_context=history_context
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
        return AgentResponse(
            response_type="clarification",
            result="I see you've uploaded a file. Please tell me what you'd like me to do with it.",
            intent=IntentLabel.UNCLEAR.value,
            execution_plan=plan,
        )
    elif query_is_empty and not file_is_present:
        return AgentResponse(
            response_type="clarification",
            result="Please provide a query or upload a file.",
            intent=IntentLabel.UNCLEAR.value,
            execution_plan=plan,
        )

    if file_is_present:
        mime_type = file.content_type or ""
        file_bytes = await file.read()

        if mime_type == settings.allowed_pdf_type:
            pdf_result = await parse_pdf_with_fallback(file_bytes, query, settings)
            extracted_text = pdf_result.get("text", "")
        elif mime_type in settings.allowed_image_types:
            img_result = await parse_image_with_fallback(file_bytes, query, settings)
            extracted_text = img_result.get("text", "")
        elif mime_type in settings.allowed_audio_types:
            audio_out = await audio_tool.run(file_bytes=file_bytes, file=file, query=query)
            return AgentResponse(
                response_type="answer",
                result=audio_out.result,
                extracted_text=audio_out.extracted_text,
                execution_log=audio_out.execution_log,
                intent=audio_out.intent.value,
                metadata=audio_out.metadata,
                execution_plan=plan,
            )
    else:
        for msg in reversed(parsed_history):
            if ext_text := (msg.get("extractedText") or msg.get("extracted_text")):
                extracted_text = ext_text
                break

    intent = await _classify_intent(
        query=query,
        content_preview=extracted_text,
        file_type=mime_type,
        history=parsed_history
    )

    if intent.needs_clarification:
        return AgentResponse(
            response_type="clarification",
            result=intent.clarification_question or "Could you clarify your request?",
            extracted_text=extracted_text or None,
            intent=intent.intent.value,
            execution_plan=plan,
        )

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
        return AgentResponse(
            response_type="answer",
            result=f"Processing error: {str(e)}",
            intent=intent.intent.value,
            execution_plan=plan,
        )

    return AgentResponse(
        response_type=tool_out.response_type,
        result=tool_out.result,
        extracted_text=tool_out.extracted_text or (extracted_text or None),
        intent=tool_out.intent.value,
        metadata=tool_out.metadata,
        execution_plan=plan,
    )

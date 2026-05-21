import httpx
import logging
from config import GEMINI_URL
from models import IntentLabel, ToolOutput
from prompts import CONVERSATIONAL_PROMPT

logger = logging.getLogger(__name__)

async def run(query: str = "", text: str = "", **kwargs) -> ToolOutput:
    source = query.strip() or text.strip()

    if not source:
        return ToolOutput(
            result="Hello! I'm ready to help. You can ask me questions, upload files, or paste text.",
            intent=IntentLabel.CONVERSATIONAL,
        )

    text_content = text.strip()
    if text_content:
        document_context = f"Document Context (Content of the uploaded file):\n{text_content}\n"
    else:
        document_context = ""

    prompt = CONVERSATIONAL_PROMPT.format(
        source=query.strip() or text.strip(),
        document_context=document_context
    )

    payload = {
        "contents": [{
            "parts": [{
                "text": prompt
            }]
        }]
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(GEMINI_URL, json=payload)
            resp.raise_for_status()
            data = resp.json()
        answer = data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        logger.error(f"Conversational generation error: {e}")
        answer = f"I ran into an issue answering that: {e}"

    return ToolOutput(
        result=answer,
        intent=IntentLabel.CONVERSATIONAL,
    )

import httpx
import logging
from settings import get_settings
from models import IntentLabel, ToolOutput
from prompts import SUMMARIZE_PROMPT

logger = logging.getLogger(__name__)

async def run(text: str = "", query: str = "", **kwargs) -> ToolOutput:
    source_text = text.strip() if text.strip() else query.strip()

    if not source_text:
        return ToolOutput(
            result="No text provided to summarize.",
            intent=IntentLabel.SUMMARIZE,
        )

    if len(source_text) > 12000:
        source_text = source_text[:12000]
        logger.info("Input truncated to 12000 chars for summarization")

    logger.info(f"Summarizing {len(source_text.split())} words")

    prompt_text = SUMMARIZE_PROMPT.format(text=source_text)

    payload = {
        "contents": [{"parts": [{"text": prompt_text}]}]
    }

    settings = get_settings()
    
    try:
        async with httpx.AsyncClient(timeout=settings.summarization_timeout) as client:
            resp = await client.post(settings.gemini_url, json=payload)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as e:
        logger.error(f"HTTP error during summarization: {e}")
        return ToolOutput(
            result=f"Summarization failed — API error: {e}",
            intent=IntentLabel.SUMMARIZE,
        )

    try:
        summary = data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError):
        logger.error("Parsing Gemini response failed during summarization")
        return ToolOutput(
            result="Summarization returned an unexpected response format.",
            intent=IntentLabel.SUMMARIZE,
        )

    logger.info("Summary generated successfully")

    return ToolOutput(
        result=summary,
        intent=IntentLabel.SUMMARIZE,
        metadata={"input_words": len(source_text.split())},
    )

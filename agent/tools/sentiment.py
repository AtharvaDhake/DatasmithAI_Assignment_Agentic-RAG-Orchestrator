import json
import httpx
import logging
from settings import get_settings
from models import IntentLabel, ToolOutput
from prompts import SENTIMENT_PROMPT

logger = logging.getLogger(__name__)

async def run(text: str = "", query: str = "", **kwargs) -> ToolOutput:
    source = text.strip() if text.strip() else query.strip()

    if not source:
        return ToolOutput(
            result="No text provided for sentiment analysis.",
            intent=IntentLabel.SENTIMENT,
        )

    logger.info(f"Analyzing sentiment for {len(source.split())} words")

    payload = {
        "contents": [{"parts": [{"text": SENTIMENT_PROMPT.format(text=source)}]}],
        "generationConfig": {"response_mime_type": "application/json"}
    }

    settings = get_settings()
    gemini_json_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key=" + settings.gemini_api_key

    try:
        async with httpx.AsyncClient(timeout=settings.sentiment_analysis_timeout) as client:
            resp = await client.post(gemini_json_url, json=payload)
            resp.raise_for_status()
            raw = resp.json()
    except httpx.HTTPError as e:
        logger.error(f"HTTP error during sentiment analysis: {e}")
        return ToolOutput(
            result=f"Sentiment analysis failed: {e}",
            intent=IntentLabel.SENTIMENT,
        )

    try:
        gemini_text = raw["candidates"][0]["content"]["parts"][0]["text"]
        parsed = json.loads(gemini_text.strip())
        label = parsed["label"]
        conf  = float(parsed["confidence"])
        justification = parsed["justification"]
    except (KeyError, IndexError, json.JSONDecodeError, ValueError) as e:
        logger.error(f"Parse error during sentiment analysis: {e}")
        return ToolOutput(
            result="Could not parse sentiment response.",
            intent=IntentLabel.SENTIMENT,
        )

    logger.info(f"Sentiment: {label} ({round(conf * 100, 1)}%)")

    result_text = (
        f"**Sentiment: {label}** (Confidence: {round(conf * 100, 1)}%)\n\n"
        f"{justification}"
    )

    return ToolOutput(
        result=result_text,
        intent=IntentLabel.SENTIMENT,
        metadata={"label": label, "confidence": conf},
    )

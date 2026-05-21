import json
import httpx
import logging
from settings import get_settings
from models import IntentLabel, ToolOutput
from prompts import CODE_EXPLAIN_PROMPT

logger = logging.getLogger(__name__)

def _format_output(parsed: dict) -> str:
    lang     = parsed.get("language", "Unknown")
    explain  = parsed.get("explanation", "")
    bugs     = parsed.get("bugs", [])
    has_bugs = parsed.get("has_bugs", False)
    time_c   = parsed.get("time_complexity", "N/A")
    space_c  = parsed.get("space_complexity", "N/A")

    lines = [
        f"**Language:** {lang}\n",
        f"**Functional Description:**\n{explain}\n",
        f"**Time Complexity:** {time_c}",
        f"**Space Complexity:** {space_c}\n",
    ]

    if has_bugs and bugs:
        lines.append("**⚠️ Issues Found:**")
        for b in bugs:
            lines.append(f"- {b}")
    else:
        lines.append("**✅ No issues detected.**")

    return "\n".join(lines)

async def run(text: str = "", query: str = "", **kwargs) -> ToolOutput:
    code_text = text.strip() if text.strip() else query.strip()

    if not code_text:
        return ToolOutput(
            result="No code provided for analysis.",
            intent=IntentLabel.CODE_EXPLAIN,
        )

    logger.info(f"Analyzing {len(code_text.splitlines())} lines of code")

    payload = {
        "contents": [{"parts": [{"text": CODE_EXPLAIN_PROMPT.format(code=code_text)}]}],
        "generationConfig": {"response_mime_type": "application/json"}
    }

    settings = get_settings()
    gemini_json_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key=" + settings.gemini_api_key

    try:
        async with httpx.AsyncClient(timeout=settings.code_analysis_timeout) as client:
            resp = await client.post(gemini_json_url, json=payload)
            resp.raise_for_status()
            raw = resp.json()
    except httpx.HTTPError as e:
        logger.error(f"HTTP error during code analysis: {e}")
        return ToolOutput(
            result=f"Code analysis failed: {e}",
            intent=IntentLabel.CODE_EXPLAIN,
        )

    try:
        gemini_text = raw["candidates"][0]["content"]["parts"][0]["text"].strip()
        if gemini_text.startswith("```json"):
            gemini_text = gemini_text[7:]
        elif gemini_text.startswith("```"):
            gemini_text = gemini_text[3:]
        if gemini_text.endswith("```"):
            gemini_text = gemini_text[:-3]

        parsed = json.loads(gemini_text.strip())
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        logger.error(f"Parse error during code analysis: {e}")
        return ToolOutput(
            result="Could not parse code analysis response.",
            intent=IntentLabel.CODE_EXPLAIN,
        )

    lang = parsed.get("language", "Unknown")
    has_bugs = parsed.get("has_bugs", False)
    logger.info(f"Language detected: {lang} | Bugs found: {has_bugs}")

    return ToolOutput(
        result=_format_output(parsed),
        intent=IntentLabel.CODE_EXPLAIN,
        metadata={
            "language": lang,
            "has_bugs": has_bugs,
            "bug_count": len(parsed.get("bugs", [])),
        },
    )

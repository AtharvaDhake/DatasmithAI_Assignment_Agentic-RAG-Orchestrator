import re
import logging
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled
from models import IntentLabel, ToolOutput

logger = logging.getLogger(__name__)

_YT_RE = re.compile(
    r'(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})'
)


def _extract_video_id(text: str) -> str | None:
    m = _YT_RE.search(text)
    return m.group(1) if m else None


async def run(query: str = "", text: str = "", **kwargs) -> ToolOutput:
    yt_url = query + " " + (text or "")
    video_id = _extract_video_id(yt_url)

    if not video_id:
        return ToolOutput(
            result="No YouTube URL detected in the input. Please paste a valid youtube.com or youtu.be link.",
            intent=IntentLabel.YOUTUBE_TRANSCRIPT,
        )

    logger.info("Extracted video ID: %s", video_id)
    yt = YouTubeTranscriptApi()

    transcript = None
    try:
        transcript = yt.fetch(video_id, languages=["en", "en-US", "en-GB"])
    except Exception as primary_err:
        logger.debug("Primary transcript fetch failed for %s: %s", video_id, primary_err)
        try:
            transcript_list = yt.list(video_id)
            transcript = transcript_list.find_transcript(["en", "en-US", "en-GB"]).fetch()
        except Exception as fallback_err:
            logger.warning("Transcript unavailable for %s: %s / %s", video_id, primary_err, fallback_err)
            return ToolOutput(
                result="This video has no available transcript. The creator may have disabled captions.",
                intent=IntentLabel.YOUTUBE_TRANSCRIPT,
            )

    if not transcript:
        return ToolOutput(
            result="This video has no available transcript. The creator may have disabled captions.",
            intent=IntentLabel.YOUTUBE_TRANSCRIPT,
        )

    full_text = " ".join(
        (item.get("text") if isinstance(item, dict) else getattr(item, "text", ""))
        for item in transcript
    ).strip()

    if not full_text:
        return ToolOutput(
            result="This video has no available transcript. The creator may have disabled captions.",
            intent=IntentLabel.YOUTUBE_TRANSCRIPT,
        )

    word_count = len(full_text.split())
    if word_count > 200:
        from tools.summarize import run as do_summary
        logger.info("Transcript long — applying summarization")
        summary_out = await do_summary(text=full_text, query=query or "summarize this video")
        return ToolOutput(
            extracted_text=full_text,
            result=summary_out.result,
            intent=IntentLabel.YOUTUBE_TRANSCRIPT,
            metadata={"video_id": video_id, "word_count": word_count},
        )

    return ToolOutput(
        extracted_text=full_text,
        result=full_text,
        intent=IntentLabel.YOUTUBE_TRANSCRIPT,
        metadata={"video_id": video_id, "word_count": word_count},
    )

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

    logger.info(f"Extracted video ID: {video_id}")

    try:
        segments = None
        try:
            segments = YouTubeTranscriptApi.get_transcripts([video_id], languages=["en", "en-US", "en-GB"]).get(video_id, [])
        except Exception as e:
            logger.debug(f"Primary transcript fetch failed: {e}")
            try:
                transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
                first_transcript = next(iter(transcript_list.manually_created_transcripts or transcript_list.generated_transcripts or []))
                segments = first_transcript.fetch()
            except Exception as fallback_err:
                logger.debug(f"Fallback transcript fetch failed: {fallback_err}")
                raise NoTranscriptFound(f"Could not fetch transcript for video {video_id}")

        if not segments:
            raise NoTranscriptFound(f"No transcript found for video {video_id}")

        full_text = " ".join(
            (seg.get("text", "") if isinstance(seg, dict) else getattr(seg, "text", ""))
            for seg in segments
        )
        logger.info(f"Fetched transcript — {len(full_text.split())} words")

    except (NoTranscriptFound, TranscriptsDisabled):
        logger.warning("Transcript unavailable")
        return ToolOutput(
            result="This video has no available transcript. The creator may have disabled captions.",
            intent=IntentLabel.YOUTUBE_TRANSCRIPT,
        )
    except Exception as e:
        logger.error(f"Error fetching transcript: {e}")
        return ToolOutput(
            result=f"Could not fetch transcript: {str(e)}",
            intent=IntentLabel.YOUTUBE_TRANSCRIPT,
        )

    if len(full_text.split()) > 200:
        from tools.summarize import run as do_summary
        logger.info("Transcript long — applying summarization")
        summary_out = await do_summary(text=full_text, query=query or "summarize this video")
        return ToolOutput(
            extracted_text=full_text,
            result=summary_out.result,
            intent=IntentLabel.YOUTUBE_TRANSCRIPT,
            metadata={"video_id": video_id, "word_count": len(full_text.split())},
        )

    return ToolOutput(
        extracted_text=full_text,
        result=full_text,
        intent=IntentLabel.YOUTUBE_TRANSCRIPT,
        metadata={"video_id": video_id, "word_count": len(full_text.split())},
    )

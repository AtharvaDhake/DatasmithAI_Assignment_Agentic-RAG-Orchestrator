import re
import logging
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled
from models import IntentLabel, ToolOutput
import os
import shutil
import tempfile
import subprocess
from settings import get_settings

logger = logging.getLogger(__name__)

_YT_RE = re.compile(
    r'(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})'
)


def _download_audio_bytes(vid: str) -> bytes | None:
    # Try yt_dlp Python package first
    try:
        import yt_dlp
        with tempfile.TemporaryDirectory() as td:
            ydl_opts = {"format": "bestaudio/best", "outtmpl": td + "/%(id)s.%(ext)s", "quiet": True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.extract_info(f"https://youtu.be/{vid}", download=True)
                # find downloaded file
                for f in os.listdir(td):
                    if f.startswith(vid):
                        path = os.path.join(td, f)
                        with open(path, "rb") as fh:
                            return fh.read()
    except Exception:
        pass

    # Fallback to system yt-dlp binary
    ytdlp_bin = shutil.which("yt-dlp") or shutil.which("yt-dl")
    if not ytdlp_bin:
        return None
    with tempfile.TemporaryDirectory() as td:
        out_path = os.path.join(td, f"{vid}.%(ext)s")
        cmd = [ytdlp_bin, "-f", "bestaudio", "-o", out_path, f"https://youtu.be/{vid}"]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            # read first file in td
            for f in os.listdir(td):
                path = os.path.join(td, f)
                with open(path, "rb") as fh:
                    return fh.read()
        except Exception:
            return None


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
                # If ASR fallback is enabled, attempt to download audio and transcribe
                settings = get_settings()
                if settings.youtube_asr_fallback:
                    logger.info("Attempting ASR fallback for YouTube video %s", video_id)
                    try:
                        # lazy import of audio tool to avoid heavy deps at module import
                        from tools.audio import run as audio_run

                        audio_bytes = _download_audio_bytes(video_id)
                        if audio_bytes:
                            audio_out = audio_run(file_bytes=audio_bytes, query=query or "transcribe youtube audio")
                            # audio_run may be async or sync; handle both
                            import asyncio
                            if asyncio.iscoroutine(audio_out):
                                audio_out = await audio_out
                            # cache transcript to simple file cache
                            try:
                                cache_dir = os.path.join(os.path.dirname(__file__), "..", ".cache")
                                os.makedirs(cache_dir, exist_ok=True)
                                cache_path = os.path.join(cache_dir, f"{video_id}.txt")
                                with open(cache_path, "w", encoding="utf-8") as cf:
                                    cf.write(audio_out.extracted_text or audio_out.result or "")
                            except Exception:
                                pass
                            return audio_out
                    except Exception as ex_asr:
                        logger.error(f"ASR fallback failed: {ex_asr}")
                # re-raise API exception with proper signature
                raise NoTranscriptFound(video_id, [], []) from fallback_err

        if not segments:
            raise NoTranscriptFound(video_id, [], [])

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

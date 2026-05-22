import re
import logging
from youtube_transcript_api import YouTubeTranscriptApi
from models import IntentLabel, ToolOutput

logger = logging.getLogger(__name__)

_YT_RE = re.compile(
    r'(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})'
)


def _extract_video_id(text: str) -> str | None:
    m = _YT_RE.search(text)
    return m.group(1) if m else None


async def _get_yt_dlp_transcript(url: str) -> str | None:
    import asyncio
    import yt_dlp
    import httpx
    import os
    from settings import get_settings
    
    ydl_opts = {
        'skip_download': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': ['en', 'en-US', 'en-GB'],
        'quiet': True,
        'extractor_args': {'youtube': ['player_client=android,web']},
    }
    
    settings = get_settings()
    if settings.youtube_cookiefile and os.path.exists(settings.youtube_cookiefile):
        ydl_opts['cookiefile'] = settings.youtube_cookiefile
        
    def extract():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False)
            
    try:
        info = await asyncio.to_thread(extract)
    except Exception as e:
        logger.error("yt-dlp metadata extraction failed: %s", e)
        return None
        
    subs = info.get('subtitles', {})
    auto_subs = info.get('automatic_captions', {})
    
    en_subs = subs.get('en') or subs.get('en-US') or subs.get('en-GB')
    if not en_subs:
        en_subs = auto_subs.get('en') or auto_subs.get('en-US') or auto_subs.get('en-GB')
        
    if not en_subs:
        return None
        
    sub_url = next((s.get('url') for s in en_subs if s.get('ext') == 'json3'), None)
    if not sub_url:
        return None
        
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(sub_url)
            resp.raise_for_status()
            data = resp.json()
            
        events = data.get('events', [])
        text_chunks = [
            seg.get('utf8', '') 
            for ev in events 
            for seg in ev.get('segs', []) 
            if seg.get('utf8', '')
        ]
        return " ".join(text_chunks).replace('\n', ' ').strip()
    except Exception as e:
        logger.error("Failed to download or parse json3 subtitles: %s", e)
        return None

async def _fallback_asr_transcription(url: str, query: str) -> ToolOutput:
    import os
    import tempfile
    import asyncio
    import yt_dlp
    from tools.audio import run as do_audio_transcription
    from settings import get_settings
    
    settings = get_settings()
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': '%(id)s.%(ext)s',
        'quiet': True,
        'extractor_args': {'youtube': ['player_client=android,web']},
    }
    if settings.youtube_cookiefile and os.path.exists(settings.youtube_cookiefile):
        ydl_opts['cookiefile'] = settings.youtube_cookiefile
        
    with tempfile.TemporaryDirectory() as tmpdir:
        ydl_opts['outtmpl'] = os.path.join(tmpdir, '%(id)s.%(ext)s')
        
        def download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return ydl.prepare_filename(info)
                
        try:
            filepath = await asyncio.to_thread(download)
            with open(filepath, 'rb') as f:
                file_bytes = f.read()
                
            class MockFile:
                filename = os.path.basename(filepath)
                content_type = "audio/mp4"
                
            logger.info("Running ASR transcription on downloaded audio...")
            audio_out = await do_audio_transcription(file=MockFile(), file_bytes=file_bytes, query=query)
            audio_out.intent = IntentLabel.YOUTUBE_TRANSCRIPT
            if audio_out.metadata:
                audio_out.metadata["youtube_asr_fallback"] = True
            return audio_out
            
        except Exception as e:
            logger.error("ASR fallback failed: %s", e)
            return ToolOutput(
                result="This video has no available transcript, and ASR fallback failed.",
                intent=IntentLabel.YOUTUBE_TRANSCRIPT,
            )

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
    full_text = None
    
    try:
        transcript = yt.fetch(video_id, languages=["en", "en-US", "en-GB"])
    except Exception as primary_err:
        logger.debug("Primary transcript fetch failed for %s: %s", video_id, primary_err)
        try:
            transcript_list = yt.list(video_id)
            transcript = transcript_list.find_transcript(["en", "en-US", "en-GB"]).fetch()
        except Exception as fallback_err:
            logger.warning("youtube-transcript-api unavailable for %s: %s / %s", video_id, primary_err, fallback_err)
            
            logger.info("Attempting yt-dlp subtitle fetch fallback...")
            full_text = await _get_yt_dlp_transcript(yt_url)
            
            if not full_text:
                from settings import get_settings
                settings = get_settings()
                if settings.youtube_asr_fallback:
                    logger.info("Falling back to ASR transcription via yt-dlp and audio tool.")
                    return await _fallback_asr_transcription(yt_url, query)
                    
                return ToolOutput(
                    result="This video has no available transcript. The creator may have disabled captions. (Consider enabling youtube_asr_fallback in settings)",
                    intent=IntentLabel.YOUTUBE_TRANSCRIPT,
                )

    if transcript and not full_text:
        full_text = " ".join(
            (item.get("text") if isinstance(item, dict) else getattr(item, "text", ""))
            for item in transcript
        ).strip()

    if not full_text:
        return ToolOutput(
            result="This video has no available transcript. The creator may have disabled captions. (Consider enabling youtube_asr_fallback in settings)",
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

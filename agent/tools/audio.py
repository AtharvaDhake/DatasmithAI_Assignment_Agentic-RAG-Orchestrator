import os
import tempfile
import logging
from pathlib import Path
import shutil
import wave
import io
import base64
import httpx
import whisper
from models import IntentLabel, ToolOutput
from settings import get_settings

logger = logging.getLogger(__name__)

_whisper_model = None

def _get_model():
    global _whisper_model
    if _whisper_model is None:
        from config import WHISPER_MODEL
        _whisper_model = whisper.load_model(WHISPER_MODEL)
    return _whisper_model

def _get_audio_duration(file_bytes: bytes, mime_type: str) -> float:
    if mime_type and "wav" in mime_type.lower():
        try:
            with wave.open(io.BytesIO(file_bytes), "rb") as wav_file:
                frames = wav_file.getnframes()
                rate = wav_file.getframerate()
                if rate > 0:
                    return frames / float(rate)
        except Exception:
            pass
    return 0.0

async def _transcribe_via_gemini(file_bytes: bytes, mime_type: str) -> str:
    settings = get_settings()
    audio_base64 = base64.b64encode(file_bytes).decode("utf-8")

    mtype = mime_type or "audio/mp3"
    if "wav" in mtype:
        mtype = "audio/wav"
    elif "mp4" in mtype or "m4a" in mtype:
        mtype = "audio/mp4"
    elif "mpeg" in mtype or "mp3" in mtype:
        mtype = "audio/mp3"

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "inlineData": {
                            "mimeType": mtype,
                            "data": audio_base64
                        }
                    },
                    {
                        "text": "Please transcribe this audio accurately. Return ONLY the transcription text. Do not add any introduction, notes, or explanations."
                    }
                ]
            }
        ]
    }

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=" + settings.gemini_api_key
    headers = {"Content-Type": "application/json"}
    
    async with httpx.AsyncClient(timeout=45.0) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        raw = resp.json()
        
    try:
        transcript = raw["candidates"][0]["content"]["parts"][0]["text"].strip()
        return transcript
    except Exception as e:
        logger.error(f"Error parsing Gemini transcription: {e}")
        raise ValueError("Failed to parse transcription from Gemini response.")

async def run(file=None, file_bytes: bytes = b"", query: str = "", **kwargs) -> ToolOutput:
    if not file_bytes and file is not None:
        file_bytes = await file.read()

    if not file_bytes:
        return ToolOutput(
            result="No audio file received.",
            intent=IntentLabel.AUDIO_TRANSCRIBE,
        )

    suffix = ".mp3"
    if file is not None and hasattr(file, "filename") and file.filename:
        suffix = Path(file.filename).suffix.lower() or ".mp3"

    mime_type = None
    if file is not None and hasattr(file, "content_type") and file.content_type:
        mime_type = file.content_type
    
    if not mime_type and suffix:
        if suffix == ".wav":
            mime_type = "audio/wav"
        elif suffix in (".m4a", ".mp4"):
            mime_type = "audio/mp4"
        else:
            mime_type = "audio/mp3"

    ffmpeg_available = shutil.which("ffmpeg") is not None
    transcript = ""
    duration = 0.0

    if not ffmpeg_available:
        logger.info("ffmpeg not available. Falling back to Gemini API for transcription.")
        try:
            transcript = await _transcribe_via_gemini(file_bytes, mime_type)
            duration = _get_audio_duration(file_bytes, mime_type)
        except Exception as e:
            logger.error(f"Gemini transcription fallback failed: {e}")
            return ToolOutput(
                result=f"Could not transcribe audio: {str(e)}",
                intent=IntentLabel.AUDIO_TRANSCRIBE,
            )
    else:
        logger.info("Loading Whisper model")
        try:
            import asyncio
            model = await asyncio.to_thread(_get_model)

            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                    tmp.write(file_bytes)
                    tmp_path = tmp.name

                logger.info(f"Saved audio to temp file ({len(file_bytes) // 1024}KB)")

                # Run transcription in a thread pool to prevent event loop blocking
                result = await asyncio.to_thread(model.transcribe, tmp_path, language="en", fp16=False)
                transcript = result["text"].strip()
                duration = result.get("duration", 0.0)
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    os.unlink(tmp_path)
        except Exception as e:
            logger.error(f"Whisper transcription failed: {e}. Trying Gemini API fallback.")
            try:
                transcript = await _transcribe_via_gemini(file_bytes, mime_type)
                duration = _get_audio_duration(file_bytes, mime_type)
            except Exception as fallback_err:
                logger.error(f"Gemini fallback transcription failed: {fallback_err}")
                return ToolOutput(
                    result=f"Could not transcribe audio: {str(e)}",
                    intent=IntentLabel.AUDIO_TRANSCRIBE,
                )

    logger.info(f"Transcribed {round(duration)}s of audio — {len(transcript.split())} words")

    if not transcript:
        return ToolOutput(
            result="Transcription returned empty — audio may be silent or unsupported format.",
            intent=IntentLabel.AUDIO_TRANSCRIBE,
        )

    from tools.summarize import run as do_summary
    logger.info("Running summarization on transcript")
    summary_out = await do_summary(text=transcript, query="summarize this audio transcript")

    duration_str = f"{int(duration // 60)}m {int(duration % 60)}s" if duration else "unknown"
    footer = f"\n\n---\nAudio Duration: {duration_str} | Word Count: {len(transcript.split())}"

    return ToolOutput(
        extracted_text=transcript,
        result=summary_out.result + footer,
        intent=IntentLabel.AUDIO_TRANSCRIBE,
        metadata={"duration_seconds": round(duration), "word_count": len(transcript.split())},
    )

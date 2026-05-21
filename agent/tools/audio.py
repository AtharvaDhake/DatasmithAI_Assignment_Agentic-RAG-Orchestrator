import os
import tempfile
import logging
from pathlib import Path
import whisper
from models import IntentLabel, ToolOutput

logger = logging.getLogger(__name__)

_whisper_model = None

def _get_model():
    global _whisper_model
    if _whisper_model is None:
        from config import WHISPER_MODEL
        _whisper_model = whisper.load_model(WHISPER_MODEL)
    return _whisper_model

async def run(file=None, file_bytes: bytes = b"", query: str = "", **kwargs) -> ToolOutput:
    logger.info("Loading Whisper model")
    model = _get_model()

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

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        logger.info(f"Saved audio to temp file ({len(file_bytes) // 1024}KB)")

        try:
            result = model.transcribe(tmp_path, language="en", fp16=False)
            transcript = result["text"].strip()
            duration = result.get("duration", 0)
        except Exception as e:
            logger.error(f"Transcription Error: {e}")
            return ToolOutput(
                result=f"Could not transcribe audio: {str(e)}",
                intent=IntentLabel.AUDIO_TRANSCRIBE,
            )

        logger.info(f"Transcribed {round(duration)}s of audio — {len(transcript.split())} words")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

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

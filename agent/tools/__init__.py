"""
Tool registry — maps intent labels to tool run functions.
Uses a factory function to build the map at first access so we don't
crash on import if a dependency (pytesseract, whisper, etc.) is missing
during development. In the Docker container everything is installed.
"""
from models import IntentLabel

_tool_map = None

def _build_map():
    from tools.ocr import run as ocr_run
    from tools.audio import run as audio_run
    from tools.youtube import run as youtube_run
    from tools.summarize import run as summarize_run
    from tools.sentiment import run as sentiment_run
    from tools.code_explain import run as code_run
    from tools.rag import run as rag_run
    from tools.conversational import run as chat_run

    return {
        IntentLabel.IMAGE_PDF_EXTRACT:  ocr_run,
        IntentLabel.AUDIO_TRANSCRIBE:   audio_run,
        IntentLabel.YOUTUBE_TRANSCRIPT: youtube_run,
        IntentLabel.SUMMARIZE:          summarize_run,
        IntentLabel.SENTIMENT:          sentiment_run,
        IntentLabel.CODE_EXPLAIN:       code_run,
        IntentLabel.RAG_QA:             rag_run,
        IntentLabel.CONVERSATIONAL:     chat_run,
    }


def get_tool_map():
    global _tool_map
    if _tool_map is None:
        _tool_map = _build_map()
    return _tool_map


# keep a module-level TOOL_MAP reference that resolves lazily
# this lets `from tools import TOOL_MAP` still work, but only
# triggers the heavy imports when actually accessed at runtime
class _LazyToolMap:
    def __getitem__(self, key):
        return get_tool_map()[key]

    def get(self, key, default=None):
        return get_tool_map().get(key, default)

    def __contains__(self, key):
        return key in get_tool_map()

TOOL_MAP = _LazyToolMap()

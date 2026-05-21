from settings import get_settings

_settings = get_settings()

GEMINI_API_KEY = _settings.gemini_api_key
SUPABASE_URL = _settings.supabase_url
SUPABASE_KEY = _settings.supabase_service_role_key
GO_BACKEND_URL = _settings.go_backend_url

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models"
    "/gemini-3.1-flash-lite:generateContent?key=" + GEMINI_API_KEY
)

GEMINI_JSON_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models"
    "/gemini-3.1-flash-lite:generateContent?key=" + GEMINI_API_KEY
)

WHISPER_MODEL = _settings.whisper_model
RAG_THRESHOLD = _settings.rag_threshold

ALLOWED_IMAGE_TYPES = set(_settings.allowed_image_types)
ALLOWED_AUDIO_TYPES = set(_settings.allowed_audio_types)
ALLOWED_PDF_TYPE = _settings.allowed_pdf_type

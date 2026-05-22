from pydantic_settings import BaseSettings
from typing import Optional, List


class Settings(BaseSettings):
    gemini_api_key: str
    supabase_url: str
    supabase_service_role_key: str

    go_backend_url: str = "http://localhost:8081"

    whisper_model: str = "base"
    rag_threshold: float = 0.30

    max_pdf_size: int = 50 * 1024 * 1024
    max_audio_size: int = 100 * 1024 * 1024
    max_image_size: int = 10 * 1024 * 1024

    cors_origins: List[str] = ["*"]

    intent_classification_timeout: float = 15.0
    ocr_processing_timeout: float = 30.0
    sentiment_analysis_timeout: float = 20.0
    code_analysis_timeout: float = 25.0
    rag_query_timeout: float = 30.0
    youtube_fetch_timeout: float = 25.0
    # If true, when a YouTube transcript is unavailable the agent will
    # download the video's audio and attempt ASR transcription via the
    # existing audio transcription pipeline (Whisper or Gemini fallback).
    youtube_asr_fallback: bool = False
    # Optional path to a cookies file to pass to yt-dlp for authenticated YouTube downloads
    # Example: /run/secrets/youtube_cookies.txt or /home/user/youtube_cookies.txt
    youtube_cookiefile: Optional[str] = None
    summarization_timeout: float = 30.0

    max_retries: int = 3
    retry_base_delay: float = 1.0

    allowed_image_types: List[str] = ["image/jpeg", "image/png", "image/jpg", "image/webp"]
    allowed_audio_types: List[str] = ["audio/mpeg", "audio/wav", "audio/x-wav", "audio/mp4", "audio/m4a"]
    allowed_pdf_type: str = "application/pdf"

    service_version: str = "1.0.0"
    service_name: str = "DataSmith AI Agent"

    class Config:
        env_file = ".env"
        case_sensitive = False

    @property
    def gemini_url(self) -> str:
        return (
            "https://generativelanguage.googleapis.com/v1beta/models"
            "/gemini-3.1-flash-lite:generateContent?key=" + self.gemini_api_key
        )

    @property
    def gemini_json_url(self) -> str:
        return self.gemini_url


_settings: Optional[Settings] = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

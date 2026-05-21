import json
import logging
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Optional

from settings import get_settings
from models import AgentResponse, IntentLabel, FileValidationError
import agent

def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.service_name,
        version=settings.service_version,
        description="Multi-modal AI agent orchestrator"
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def add_security_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        return response

    @app.get("/health")
    def health():
        settings = get_settings()
        return {
            "status": "ok",
            "service": settings.service_name,
            "version": settings.service_version,
        }

    @app.get("/tools")
    def list_tools():
        return {
            "tools": [
                {"name": "image_pdf_extract"},
                {"name": "audio_transcribe"},
                {"name": "youtube_transcript"},
                {"name": "summarize"},
                {"name": "sentiment"},
                {"name": "code_explain"},
                {"name": "rag_qa"},
                {"name": "conversational"},
            ]
        }

    @app.post("/process", response_model=AgentResponse)
    async def process(
        query: str = Form(default=""),
        file: Optional[UploadFile] = File(default=None),
        history: str = Form(default="[]"),
    ):
        settings = get_settings()

        if file is not None:
            file_size = len(await file.read())
            await file.seek(0)

            mime_type = file.content_type or ""

            if mime_type == settings.allowed_pdf_type and file_size > settings.max_pdf_size:
                raise HTTPException(status_code=413, detail="PDF file too large")
            elif mime_type in settings.allowed_audio_types and file_size > settings.max_audio_size:
                raise HTTPException(status_code=413, detail="Audio file too large")
            elif mime_type in settings.allowed_image_types and file_size > settings.max_image_size:
                raise HTTPException(status_code=413, detail="Image file too large")

            allowed_types = settings.allowed_image_types + settings.allowed_audio_types + [settings.allowed_pdf_type]
            if mime_type not in allowed_types:
                raise HTTPException(status_code=400, detail=f"Unsupported file type: {mime_type}")

        result = await agent.run(query=query, file=file, history=history)
        return result

    @app.post("/process/text", response_model=AgentResponse)
    async def process_text(body: dict):
        query = body.get("query", "").strip()
        if not query:
            raise HTTPException(status_code=400, detail="query field is required")

        history = body.get("history", "[]")
        if isinstance(history, list):
            history = json.dumps(history)

        result = await agent.run(query=query, file=None, history=history)
        return result

    @app.exception_handler(ValueError)
    async def value_error_handler(request, exc):
        return JSONResponse(
            status_code=400,
            content={"error": "Validation error", "detail": str(exc)},
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        import logging
        logging.error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": "An unexpected error occurred. Please try again later."},
        )

    return app

app = create_app()

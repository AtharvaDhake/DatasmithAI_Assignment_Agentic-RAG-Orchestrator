# DataSmith AI Agentic Application

This project is a multi-modal agentic application built for the DataSmith AI assignment. It provides a robust orchestration layer capable of handling text, images, PDFs, audio, and YouTube URLs, integrating these modalities with a vector-based Retrieval-Augmented Generation (RAG) backend.

## Architecture Overview

The system is decomposed into three main microservices:

1. **FastAPI Agent (Port 8000)**: The core orchestration layer.
   - Routes intents to specialized tools.
   - Integrates with Gemini models for complex multimodal tasks.
   - Services: OCR (`pytesseract` + `PyMuPDF`), Audio STT (`whisper`), YouTube transcript fetching, Summarization, Sentiment Analysis, and Code Explanation.
2. **Go Backend (Port 8081)**: The retrieval system.
   - Manages the RAG pipeline.
   - Uses Supabase `pgvector` for vector search and similarity matching.
3. **Next.js Frontend (Port 3000)**: The user interface.
   - Modern chat interface supporting drag-and-drop file uploads for all supported modalities.

### Component Flow

1. User submits a query or file via the Next.js frontend.
2. The FastAPI service extracts text/content based on the MIME type.
3. The intent is classified and routed to the appropriate tool.
4. For document querying (`rag_qa`), the request is forwarded to the Go backend for vector search.
5. Final responses, including execution metadata and citations, are streamed back to the client.

## Quick Start (Docker Compose)

The easiest way to run the application is via Docker Compose, which builds and networks all three services automatically.

1. **Configure Environment**
   Create a `.env` file in the root directory:
   ```env
   GEMINI_API_KEY=your_gemini_api_key
   SUPABASE_URL=your_supabase_url
   SUPABASE_SERVICE_ROLE_KEY=your_supabase_key
   ```

2. **Build and Run**
   ```bash
   docker compose up --build
   ```
   *Note: The initial build pulls necessary dependencies including PyTorch and the Whisper base model. This may take a few minutes depending on your network connection.*

## Testing

The Python agent includes a test suite covering intent extraction, edge cases, and tool execution.

```bash
cd agent
python -m pytest tests/ -v
```

## CI/CD Pipeline

The project includes a GitHub Actions workflow (`.github/workflows/cicd.yaml`) that builds the Docker images, pushes them to Amazon ECR, and deploys the stack to a self-hosted EC2 instance.

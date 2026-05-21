# Agentic RAG Orchestrator

Multi-modal agentic app that takes in text, images, PDFs, audio files, or YouTube URLs — figures out what the user wants, and runs the right tool automatically. Built with FastAPI + Go + Next.js.

## Agentic RAG Orchestraor Live On EC2 

http://13.60.78.68:3000/

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Next.js Frontend (:3000)              │
│           Chat UI + file upload + markdown render       │
└───────────────────────┬─────────────────────────────────┘
                        │ POST /process (multipart form)
                        ▼
┌─────────────────────────────────────────────────────────┐
│                 FastAPI Agent (:8000)                   │
│                                                         │
│  1. Parse file (PDF/image/audio) → extract text         │
│  2. Classify intent via Gemini                          │
│  3. Route to the right tool:                            │
│     ┌──────────────┬──────────────┬──────────────┐      │
│     │ summarize    │ sentiment    │ code_explain │     │
│     │ youtube      │ ocr/extract  │ audio_transcr│     │
│     │ rag_qa       │ conversation │              │      |
│     └──────────────┴──────────────┴──────────────┘      │
│  4. Return result + execution log + extracted text      │
└─────────────────┬───────────────────────────────────────┘
                  │ (only for rag_qa intent)
                  ▼
┌─────────────────────────────────────────────────────────┐
│               Go Backend (:8081)                        │
│  embed query → pgvector search on Supabase → Gemini     │
│  returns answer + page-level citations                  │
└─────────────────────────────────────────────────────────┘
```

**How the orchestration works (agent.py):**

1. User sends a query (+ optional file) from the frontend
2. If a file is attached, we extract its content first:
   - PDF → PyMuPDF text extraction, falls back to Tesseract OCR, falls back to Gemini multimodal
   - Image → Gemini multimodal OCR, falls back to Tesseract
   - Audio → Whisper STT (threaded), falls back to Gemini 2.5 Flash for cloud transcription
3. If there's no query and only a file, we ask the user what they want to do with it (clarification gate)
4. Intent classification happens via Gemini — returns one of 9 labels with confidence + reasoning
5. The classified intent maps to a tool function, which gets called with the query + extracted text
6. Everything gets logged into `execution_log` so the user can see what happened

## Tools

| Tool | What it does | Output format |
|------|-------------|---------------|
| **summarize** | 1-line summary + 3 bullet points + 5-sentence detailed summary | structured text |
| **sentiment** | Label (Positive/Negative/Neutral/Mixed) + confidence score + one-line justification | structured text |
| **code_explain** | Detects language, explains what code does, finds bugs, gives time/space complexity | structured text |
| **youtube_transcript** | Extracts video ID from URL → fetches transcript → auto-summarizes if long (>200 words) | text + metadata |
| **image_pdf_extract** | OCR/text extraction from images and PDFs with fallback chain | extracted text |
| **audio_transcribe** | Speech-to-text (Whisper local or Gemini cloud) → summarize | transcript + summary |
| **rag_qa** | Searches the nutrition textbook via pgvector → generates grounded answer with citations | text + citations |
| **conversational** | General chat, greetings, follow-ups | text |

## Sample Execution Logs

These are actual outputs from the agent running locally:

**Conversational:**
```
Query: "Hello, how are you?"

Execution Log:
  → Classifying intent via Gemini
  → Intent: conversational (confidence: 1.00) – standard social greeting
  → Dispatching to: conversational

Result: "I am doing well, thank you for asking! How can I help you today?"
```

**Summarization:**
```
Query: "Summarize this text: The Python programming language was created by Guido van Rossum..."

Execution Log:
  → Classifying intent via Gemini
  → Intent: summarize (confidence: 1.00) – user explicitly requested to summarize
  → Dispatching to: summarize

Result:
  ONE-LINE SUMMARY:
  Guido van Rossum released Python in 1991, creating a versatile, readable language...

  KEY POINTS:
  • Python prioritizes code readability through significant indentation.
  • Supports multiple paradigms: OOP, structured, functional.
  • "Batteries-included" standard library for diverse fields.

  DETAILED SUMMARY: [5 sentences]
```

**Sentiment Analysis:**
```
Query: "Analyze the sentiment: This product is absolutely terrible..."

Execution Log:
  → Classifying intent via Gemini
  → Intent: sentiment (confidence: 1.00) – user explicitly requested sentiment analysis
  → Dispatching to: sentiment

Result: Sentiment: Negative (Confidence: 100.0%)
  "The review uses strong pejorative language such as 'terrible', 'awful',
   and 'horrendous' to express complete dissatisfaction..."
```

**Code Explanation:**
```
Query: "Explain this code: def fibonacci(n): ..."

Execution Log:
  → Classifying intent via Gemini
  → Intent: code_explain (confidence: 1.00) – user requested explanation for Python code
  → Dispatching to: code_explain

Result:
  Language: python
  Functional Description: Computes nth Fibonacci number using classic recursion...
  Time Complexity: O(2^n) — exponential recursion tree
  Space Complexity: O(n) — call stack depth
  ⚠️ Issues Found:
  - Lacks memoization, causes redundant calculations
```

**YouTube Transcript:**
```
Query: "Get me the transcript of https://www.youtube.com/watch?v=LfWU5Kjitcg"

Execution Log:
  → Classifying intent via Gemini
  → Intent: youtube_transcript (confidence: 1.00) – YouTube URL present
  → Dispatching to: youtube_transcript

Result: [auto-summarized since transcript was 1401 words]
  ONE-LINE SUMMARY: AI companies are hiring "forward deployed engineers"...
  Metadata: {video_id: "LfWU5Kjitcg", word_count: 1401}
```

**PDF + Question (clarification gate):**
```
Query: "" (empty, just file upload)

Execution Log:
  → File received: report.pdf (application/pdf, 245KB)

Result: "I see you've uploaded a file. Please tell me what you'd like me to do with it."
Response Type: clarification
```

## Project Structure

```
├── agent/                  # FastAPI orchestrator (Python)
│   ├── main.py             # FastAPI app, endpoints, validation
│   ├── agent.py            # Core orchestration: extract → classify → dispatch
│   ├── models.py           # Pydantic models (IntentLabel, ToolOutput, etc.)
│   ├── prompts.py          # All LLM prompts
│   ├── settings.py         # Pydantic settings with env vars
│   ├── config.py           # Derived config (URLs, constants)
│   ├── parsers.py          # PDF/image extraction with fallback chains
│   ├── tools/
│   │   ├── __init__.py     # Lazy tool registry (intent → handler map)
│   │   ├── summarize.py
│   │   ├── sentiment.py
│   │   ├── code_explain.py
│   │   ├── youtube.py
│   │   ├── audio.py
│   │   ├── ocr.py
│   │   ├── rag.py
│   │   └── conversational.py
│   ├── tests/              # 28 tests (pytest)
│   ├── Dockerfile
│   └── requirements.txt
├── backend/                # Go RAG service
│   ├── main.go             # HTTP server, embedding, pgvector search, Gemini
│   └── Dockerfile
├── frontend/               # Next.js chat UI
│   ├── src/app/page.tsx    # Main chat component
│   ├── src/app/globals.css # Styling
│   └── Dockerfile
├── docker-compose.yml      # Ties everything together
├── ingest.py               # Script to chunk + embed the PDF into Supabase
└── human-nutrition-text.pdf # Source document for RAG
```

## Setup

### Docker (recommended)

1. Create `.env` in the project root:
   ```
   GEMINI_API_KEY=your_key
   SUPABASE_URL=your_supabase_url
   SUPABASE_SERVICE_ROLE_KEY=your_supabase_key
   ```

2. Build and run:
   ```bash
   docker compose up --build
   ```

3. Open `http://localhost:3000`

### Local dev (without Docker)

**Agent:**
```bash
cd agent
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

**Go backend:**
```bash
cd backend
go run main.go
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## Testing

```bash
python -m pytest agent/tests/ -v
```

28 tests covering:
- Clarification gates (file without query, empty input)
- File size/type validation
- Intent classification labels
- YouTube URL regex parsing
- Tool map completeness
- Output format compliance (summarize, sentiment, code_explain)
- API endpoint behavior (health, tools, process)

## Tech Stack

- **Agent**: Python 3.13, FastAPI, Pydantic, httpx, PyMuPDF, pytesseract, OpenAI Whisper
- **Backend**: Go 1.23, Supabase pgvector
- **Frontend**: Next.js 16, React, react-markdown, react-syntax-highlighter
- **LLM**: Gemini 3.1 Flash Lite (intent + tools), Gemini 2.5 Flash (audio transcription)
- **Infra**: Docker Compose, GitHub Actions CI/CD

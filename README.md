# Agentic RAG Orchestrator

![Agentic RAG Orchestrator](https://img.shields.io/badge/Status-Live%20on%20EC2-brightgreen) ![Tech Stack](https://img.shields.io/badge/Stack-FastAPI%20%7C%20Go%20%7C%20Next.js-blue)

**Live EC2 Deployment:** [http://13.60.78.68:3000/](http://13.60.78.68:3000/)

---

## 🎯 Executive Summary (For Evaluators)

This project is a highly robust, multi-modal **Agentic RAG (Retrieval-Augmented Generation) Orchestrator**. It is designed to act as a unified, intelligent assistant capable of processing diverse inputs—Text, PDFs, Images, Audio files, and YouTube URLs.

Instead of forcing the user to select a specific tool or pipeline, the system utilizes an **LLM-based Intent Router** (powered by Gemini) to automatically deduce what the user wants to do and dynamically dispatch the payload to the correct specialized pipeline.

### Key Architectural Decisions

- **Next.js (Frontend)**: Provides a slick, real-time chat interface with file upload previews, typing indicators, and rich markdown/code rendering.
- **FastAPI (Python Agent)**: Acts as the "brain". Python was chosen here because it is the industry standard for AI/ML tasks. It handles heavy multi-modal extraction (OCR, Whisper STT) and the core LLM intent classification.
- **Go (Backend)**: Acts as a high-performance RAG microservice. Go was chosen for its unparalleled concurrency and speed. It manages embeddings, connects to Supabase (`pgvector`) for semantic search over textbook data, and generates grounded answers with explicit page-level citations.

---

## 🏗️ Architecture Flow

```text
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
│     │ summarize    │ sentiment    │ code_explain │      │
│     │ youtube      │ ocr/extract  │ audio_transcr│      │
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

---

## ⚙️ Core Features & Implementation Details

### 1. Intelligent Orchestration & Clarification Gates

The core of the system is the **Intent Router** (`agent.py`). When a user uploads a file and/or types a query, the agent:

1. **Pre-processes the file**: Extracts text from PDFs, Images, or Audio files before sending anything to the LLM.
2. **Classifies Intent**: Feeds the query and the file context into a Gemini model to classify the user's intent into one of 8 distinct labels (plus a fallback `conversational` intent).
3. **Dispatches**: Routes the payload to the corresponding specialized tool handler.
4. **Clarification Gate**: If a user uploads a file but provides _no instructions_ (empty query), the agent halts execution and prompts the user for direction (e.g., "I see you uploaded an image. Do you want me to summarize it, extract text, or something else?").

### 2. Multi-Tiered Fallback Extraction Pipelines

To ensure enterprise-grade reliability, we built multi-modal extraction pipelines that automatically fall back to secondary methods if the primary method fails:

- **PDF Extraction**: Attempts `PyMuPDF` first for raw text extraction. If the PDF is scanned or empty, it falls back to local `Tesseract OCR`, and if that fails, it falls back to `Gemini Multimodal` vision parsing.
- **Image Extraction**: Utilizes `Gemini Multimodal OCR` as the primary method, with local `Tesseract` as a secondary fallback.
- **Audio/Speech**: Uses local `OpenAI Whisper` for Speech-to-Text (STT). If local processing fails or times out, it offloads the audio transcription to `Gemini 2.5 Flash`.

### 3. Resilient YouTube Transcripts (Evading Cloud IP Bans)

Extracting transcripts from YouTube is handled natively via `youtube-transcript-api`. However, if a video lacks manual/auto-captions, or if the request is blocked by YouTube, the system falls back to a custom **ASR (Automatic Speech Recognition) Pipeline**:

- The system utilizes `yt-dlp` (configured with Android client spoofing) to bypass YouTube's aggressive bot-detection blocks.
- It downloads the raw audio stream directly to the server.
- The audio is then fed into the Audio STT pipeline (Whisper) to generate a highly accurate transcript from scratch.

### 4. Grounded RAG QA (Retrieval-Augmented Generation)

For the `rag_qa` intent, the system proxies the request to the Go microservice. The Go backend:

1. Embeds the user's query using `sentence-transformers`.
2. Performs a Cosine Similarity search against a PostgreSQL database (`pgvector` hosted on Supabase) populated with chunked textbook data.
3. Streams back an LLM response containing explicit **page-level citations** so the user can verify the source of the information.

---

## 🛠️ Tool Registry

| Tool                   | Implementation Details                                                                                            | Output format        |
| ---------------------- | ----------------------------------------------------------------------------------------------------------------- | -------------------- |
| **summarize**          | Generates a 1-line summary, 3 key bullet points, and a 5-sentence detailed summary.                               | structured text      |
| **sentiment**          | Evaluates text (Positive/Negative/Neutral/Mixed), provides a confidence score, and a 1-line justification.        | structured text      |
| **code_explain**       | Detects the programming language, explains the logic, flags potential bugs, and calculates Time/Space complexity. | structured text      |
| **youtube_transcript** | Extracts video ID from URL → fetches transcript → auto-summarizes if the video is long (>200 words).              | text + metadata      |
| **image_pdf_extract**  | OCR/text extraction from images and PDFs utilizing the fallback chain (PyMuPDF -> Tesseract -> Gemini).           | extracted text       |
| **audio_transcribe**   | Speech-to-text (Whisper local or Gemini cloud) → summarizes the transcription.                                    | transcript + summary |
| **rag_qa**             | Searches the nutrition textbook via pgvector → generates a grounded answer with citations.                        | text + citations     |
| **conversational**     | Handles general chat, greetings, and generic follow-ups.                                                          | text                 |

---

## 🛑 Troubleshooting & Known Issues

### YouTube IP Blocking on AWS / Cloud Providers

**The Issue:** When deploying to AWS EC2, you may encounter an error stating `youtube-transcript-api unavailable: YouTube is blocking requests from your IP` followed by a complete failure to retrieve the transcript.
**The Cause:** YouTube actively blocks API requests and media downloads originating from known cloud provider IP ranges (AWS, GCP, Azure) to prevent bot scraping.
**Our Advanced Mitigation:** We have implemented a multi-layered fallback mechanism specifically to defeat this:

1. Setting `YOUTUBE_ASR_FALLBACK=true` in the `.env` allows the system to gracefully switch from the blocked API to downloading the raw audio and generating the transcript locally using Whisper.
2. To ensure the audio download itself isn't blocked, `yt-dlp` is configured with `player_client=android,web` spoofing and utilizes `nodejs` to evade standard web-player JavaScript bot checks.

---

## 📋 Sample Execution Logs

These are actual outputs from the agent running locally:

**Conversational:**
```text
Query: "Hello, how are you?"

Execution Log:
  → Classifying intent via Gemini
  → Intent: conversational (confidence: 1.00) – standard social greeting
  → Dispatching to: conversational

Result: "I am doing well, thank you for asking! How can I help you today?"
```

**Summarization:**
```text
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
```text
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
```text
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
```text
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
```text
Query: "" (empty, just file upload)

Execution Log:
  → File received: report.pdf (application/pdf, 245KB)

Result: "I see you've uploaded a file. Please tell me what you'd like me to do with it."
Response Type: clarification
```

---

## 📁 Project Structure

```text
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

## 🚀 Setup & Deployment

### Docker (Recommended)

1. Create a `.env` file in the project root:

   ```env
   GEMINI_API_KEY=your_key
   SUPABASE_URL=your_supabase_url
   SUPABASE_SERVICE_ROLE_KEY=your_supabase_key
   YOUTUBE_ASR_FALLBACK=true
   ```

2. Build and spin up the microservices:

   ```bash
   docker compose up --build
   ```

3. Access the UI at `http://localhost:3000`

### Local Development (Without Docker)

**FastAPI Agent:**

```bash
cd agent
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

**Go Backend:**

```bash
cd backend
go run main.go
```

**Next.js Frontend:**

```bash
cd frontend
npm install
npm run dev
```

---

## 🧪 Testing Suite

We have implemented a comprehensive test suite using `pytest`.

```bash
python -m pytest agent/tests/ -v
```

**28 passing tests covering:**

- Clarification gates (handling files uploaded without queries, or empty inputs)
- File size and MIME-type validation
- Strict Intent classification label checking
- YouTube URL regex parsing
- Tool map completeness and dispatching
- Output format compliance for structured tools (summarize, sentiment, code_explain)
- API endpoint behavior (health checks, tools listing, multipart process parsing)

---

## 💻 Tech Stack Summary

- **Agent Framework**: Python 3.13, FastAPI, Pydantic, httpx
- **Extraction Tools**: PyMuPDF, pytesseract, yt-dlp, OpenAI Whisper, ffmpeg
- **RAG Backend**: Go 1.23, Supabase (PostgreSQL + pgvector), SentenceTransformers
- **Frontend**: Next.js 16, React 19, react-markdown, TailwindCSS
- **LLM Engine**: Gemini 3.1 Flash Lite (for fast intent routing + tool execution), Gemini 2.5 Flash (for heavy audio transcription)
- **Infrastructure**: Docker Compose, GitHub Actions CI/CD pipeline targeting AWS EC2

FROM python:3.11-slim AS builder

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /install

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip "setuptools<82" wheel \
 && pip install --no-cache-dir \
    torch==2.6.0 --index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir --no-build-isolation -r requirements.txt

RUN python -c "import whisper; whisper.load_model('base')"

FROM python:3.11-slim

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    ffmpeg \
    curl \
 && rm -rf /var/lib/apt/lists/*

# Install Deno for yt-dlp EJS support (improves YouTube extraction)
RUN curl -fsSL https://deno.land/x/install/install.sh | sh \
 && ln -s /root/.deno/bin/deno /usr/local/bin/deno || true

COPY --from=builder /usr/local/lib/python3.11 /usr/local/lib/python3.11
COPY --from=builder /usr/local/bin             /usr/local/bin
COPY --from=builder --chown=1001:1001 /root/.cache /home/appuser/.cache

COPY agent.py       ./
COPY main.py        ./
COPY models.py      ./
COPY parsers.py     ./
COPY prompts.py     ./
COPY settings.py    ./
COPY config.py      ./
COPY tools/         ./tools/

RUN addgroup --system --gid 1001 appgroup \
 && adduser  --system --uid 1001 --ingroup appgroup appuser

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=45s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

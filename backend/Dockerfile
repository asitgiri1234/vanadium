# Vanadium API — production image with ffmpeg, Tesseract, Whisper (PyTorch).
# Deploy on Railway, Render, Fly.io, or any container host with a /data volume.

FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    CHROMA_PERSIST_DIR=/data/chroma \
    ANALYSIS_PERSIST_DIR=/data/analyses \
    HOST=0.0.0.0 \
    PORT=8000

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

RUN mkdir -p /data/chroma /data/analyses

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')" || exit 1

CMD ["sh", "-c", "mkdir -p /data/chroma /data/analyses && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

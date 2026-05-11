FROM python:3.11-slim

WORKDIR /app

# Minimal system deps — no ffmpeg (no audio pipeline on free tier)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Lightweight requirements only — no torch / transformers / mediapipe / whisper / easyocr
# Rule-based NLP fallback + XGBoost fusion handle inference without heavy ML deps
COPY requirements-deploy.txt .
RUN pip install --no-cache-dir --timeout 300 -r requirements-deploy.txt

# Copy application code
COPY . .

# Environment
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV PORT=8000

EXPOSE 8000

# Run FastAPI — use $PORT from Render/Railway, fallback to 8000 for local Docker
CMD ["sh", "-c", "python -m uvicorn backend_services.api_gateway.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

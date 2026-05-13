FROM python:3.11-slim

WORKDIR /app

# System deps for video pipeline (yt-dlp + ffmpeg)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Deploy requirements include FastAPI + OCR + CPU Torch/Transformers runtime
# so CLIP/PhoBERT and image OCR can run in Docker as well.
COPY requirements-deploy.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --timeout 300 -r requirements-deploy.txt

# Copy application code
COPY . .

# Environment
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV PORT=8000

EXPOSE 8000

# Run FastAPI — use $PORT from Render/Railway, fallback to 8000 for local Docker
CMD ["sh", "-c", "python -m uvicorn backend_services.api_gateway.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

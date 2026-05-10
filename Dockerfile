FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install in small batches — each layer is cached separately, preventing
# mid-batch BrokenPipeError from forcing a full re-download on retry.

# Batch 1: Web framework & utilities
RUN pip install --no-cache-dir --timeout 300 \
    fastapi==0.104.0 \
    "uvicorn[standard]==0.24.0" \
    pydantic==2.5.0 \
    python-multipart==0.0.6 \
    jinja2==3.1.2 \
    requests==2.31.0 \
    aiohttp==3.9.0 \
    httpx==0.25.2 \
    aiofiles>=23.0 \
    python-dotenv==1.0.0 \
    tqdm==4.66.1 \
    python-dateutil==2.8.2 \
    pytz==2023.3

# Batch 2: Database & auth
RUN pip install --no-cache-dir --timeout 300 \
    pymongo==4.6.0 \
    neo4j==5.15.0 \
    redis==5.0.1 \
    "python-jose[cryptography]==3.3.0" \
    "passlib[bcrypt]==1.7.4"

# Batch 3: Monitoring
RUN pip install --no-cache-dir --timeout 300 \
    prometheus-client==0.19.0 \
    structlog==23.2.0 \
    sentry-sdk==1.38.0

# Batch 4: PyTorch CPU (large wheels ~200MB each)
RUN pip install --no-cache-dir --timeout 600 \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    torch==2.2.0+cpu \
    torchvision==0.17.0+cpu

# Batch 5: Transformers & ONNX
# transformers<5.0.0: v5 requires torch>=2.4, but we have torch==2.2.0+cpu
# sentencepiece: required by PhoBERT tokenizer
# pandas: required by XGBoost fusion model
# numpy<2.0: torch==2.2 was compiled against NumPy 1.x — NumPy 2.x causes crash
RUN pip install --no-cache-dir --timeout 300 \
    "numpy>=1.26.0,<2.0.0" \
    "transformers>=4.40.0,<5.0.0" \
    "onnxruntime>=1.17.1" \
    sentencepiece \
    pandas

# Batch 6: Audio processing
RUN pip install --no-cache-dir --timeout 300 \
    "yt-dlp>=2024.1.0" \
    "ffmpeg-python>=0.2.0" \
    "librosa>=0.10.1" \
    "scikit-learn>=1.3.0" \
    "xgboost>=2.0.0" \
    "accelerate>=0.27.0"

# Batch 7: openai-whisper — install without triton (GPU-only, not needed for CPU inference)
RUN pip install --no-cache-dir --timeout 300 \
    tiktoken \
    more-itertools
RUN pip install --no-cache-dir --timeout 300 --no-deps \
    "openai-whisper>=20231117"

# Batch 8: Vision
RUN pip install --no-cache-dir --timeout 300 \
    "Pillow>=10.1.0" \
    "opencv-python>=4.8.1" \
    "mediapipe>=0.10.9" \
    "easyocr>=1.7.1"

# Copy application code
COPY . .

# Environment
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV PORT=8000

EXPOSE 8000

# Run FastAPI with uvicorn
CMD ["python", "-m", "uvicorn", "backend_services.api_gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]

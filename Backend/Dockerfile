# ============================================================
# VidScholar Backend - Dockerfile
# ============================================================
FROM python:3.11-slim

# Prevent Python from writing .pyc files and buffering stdout/stderr,
# which makes container logs appear immediately.
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies. build-essential is needed for some
# packages (e.g. onnxruntime/chromadb transitive deps) that compile
# native extensions during install; curl is used by the HEALTHCHECK.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (separate layer) so Docker can
# cache this step and skip reinstalling when only app code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Create the directory ChromaDB persists vectors to, and the SQLite
# database file location, so the container has correct permissions
# even before the app's first run creates them itself.
RUN mkdir -p /app/chroma_data

EXPOSE 8000

# Healthcheck hits our /health endpoint defined in main.py
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

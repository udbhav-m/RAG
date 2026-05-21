FROM python:3.12-slim

# System deps for `unstructured` document parsing
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Railway injects $PORT — shell form (no brackets) so the var expands
CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT
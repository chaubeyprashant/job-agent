FROM python:3.11-slim

# Install system dependencies required for building and Playwright
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium with dependencies
RUN playwright install chromium --with-deps

# Copy application code
COPY . .

# Expose port (Render sets PORT env, but Uvicorn needs to use it)
ENV PORT=8000
EXPOSE 8000

# Start server. Render injects the PORT env var.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

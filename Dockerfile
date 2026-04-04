FROM python:3.11-slim

# Install system dependencies required for building and Playwright
# texlive-latex-extra provides moderncv.cls and many CV/bibliography packages used by real resumes.
# texlive-fonts-extra provides icons (fontawesome5), symbols, and additional font families.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    texlive-latex-base \
    texlive-fonts-recommended \
    texlive-latex-recommended \
    texlive-latex-extra \
    texlive-fonts-extra \
    lmodern \
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

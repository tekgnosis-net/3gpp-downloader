# 3GPP Downloader Dockerfile

FROM node:20-bullseye AS frontend-builder
WORKDIR /app/frontend

# Install frontend dependencies and build the production bundle
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim

ARG APP_VERSION=dev

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/
COPY run_web.py .
COPY README.md .

# Copy the pre-built frontend bundle
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Annotate image with version metadata
LABEL org.opencontainers.image.title="3gpp-downloader"
LABEL org.opencontainers.image.version="${APP_VERSION}"
LABEL org.opencontainers.image.source="https://github.com/tekgnosis-net/3gpp-downloader"

# Create directories for downloads and logs
RUN mkdir -p downloads logs

# Set environment variables
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1
ENV APP_VERSION=${APP_VERSION}

# Expose port for web UI
EXPOSE 32123

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:32123')" || exit 1

# Default command to run web UI
CMD ["python", "run_web.py"]
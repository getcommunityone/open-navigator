# Multi-stage build for Hugging Face Spaces
# Runs all three apps: Docusaurus docs, React frontend, FastAPI backend

FROM node:20-slim AS docs-builder
WORKDIR /build

# Set baseUrl to /docs/ for HuggingFace deployment  # Docs are served at nginx /docs/ location
# routeBasePath: '/' in docusaurus.config.ts prevents /docs/docs/ nesting
ENV DOCUSAURUS_BASE_URL=/docs/

COPY web_docs/package*.json ./
RUN npm config set fetch-retry-mintimeout 20000 && \
    npm config set fetch-retry-maxtimeout 120000 && \
    npm ci --prefer-offline --no-audit || npm install --prefer-offline --no-audit

# Add cache-busting argument to force rebuild when needed
ARG CACHE_BUST=2026-06-08-23-36-90830cd4

COPY web_docs/ ./

# Verify environment variable is set and build
RUN echo "Building Docusaurus with DOCUSAURUS_BASE_URL=$DOCUSAURUS_BASE_URL" && \
    echo "Cache bust: 2026-06-08-23-36-90830cd4" &&
    npm run build && \
    echo "Verifying baseUrl in build output..." && \
    grep -r "baseUrl" build/ | head -5 || true

FROM python:3.11-slim

# Install system dependencies, nginx, and Node.js for frontend build
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    tesseract-ocr \
    nginx \
    supervisor \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy Python requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# OPTIMIZATION: Copy frontend package files first for better caching
COPY web_app/package*.json /app/web_app/
RUN cd /app/web_app && npm ci

# Copy application code (now npm ci layer is cached)
COPY . .

# Install workspace kernel packages so config/agents/models import as
# top-level modules at runtime (--no-deps keeps the dependency closure unchanged).
RUN pip install --no-cache-dir --no-deps ./packages/core ./packages/datamodels ./packages/agents ./packages/scrapers

# Copy built static files from docs stage
COPY --from=docs-builder /build/build /app/static/docs

# Build frontend (npm_modules already cached from above)
# Set production environment variables for Vite
ENV VITE_CANONICAL_DOMAIN=www.communityone.com
ENV VITE_API_URL=/api
# Cache bust: 2026-04-29-remove-axios
ARG CACHE_BUST_FRONTEND=2026-06-08-23-36-90830cd4
RUN cd /app/web_app && echo "Frontend build cache bust: $CACHE_BUST_FRONTEND" && npm run build

# Frontend is already built to /app/api/static/ via vite.config.ts
# Create frontend directory in /app/static for nginx
RUN mkdir -p /app/static/frontend && \
    ls -la /app/api/static/ && \
    cp -r /app/api/static/* /app/static/frontend/

# Create necessary directories
RUN mkdir -p /app/logs /app/data /var/log/supervisor

# Copy Hugging Face specific configs
COPY .huggingface/nginx.conf /etc/nginx/nginx.conf
COPY .huggingface/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY .huggingface/start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Expose port 7860 (Hugging Face Spaces default)
EXPOSE 7860

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO
ENV HF_SPACES=1

# Use supervisor to run all services
CMD ["/app/start.sh"]

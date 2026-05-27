FROM python:3.11-slim

# Install Node.js for frontend build
RUN apt-get update && apt-get install -y \
    curl \
    tesseract-ocr \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements-cpu.txt .
RUN pip install --no-cache-dir -r requirements-cpu.txt

# Copy frontend and build
COPY frontend/ ./frontend/
WORKDIR /app/frontend
RUN npm install && npm run build

# Copy backend
WORKDIR /app
COPY api/ ./api/
COPY packages/agents/agents/ ./agents/
COPY packages/core/config/ ./config/
COPY pipeline/ ./pipeline/
COPY visualization/ ./visualization/
COPY databricks/ ./databricks/
COPY .env.example .env

# Expose port
EXPOSE 8000

# Run app
CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000"]

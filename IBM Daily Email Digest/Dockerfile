# IBM Code Engine Dockerfile for IBM Daily Email Digest
# Python 3.11 runtime with all dependencies

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for potential PDF/image processing
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt requirements-ibm.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt -r requirements-ibm.txt

# Copy application code
COPY src/ ./src/
COPY config/ ./config/
COPY grounding/ ./grounding/

# Create output directory
RUN mkdir -p /app/output/logs /app/output/decks

# Set environment variables for IBM Cloud
ENV PYTHONUNBUFFERED=1
ENV CLOUD_PROVIDER=ibm
ENV EMAIL_METHOD=sendgrid

# Entry point - runs the digest
CMD ["python", "-m", "src.main", "--no-decks"]

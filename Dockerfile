FROM python:3.11-slim
WORKDIR /app

# Install build-essential for some Python packages that require C extensions
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY advanced-agent/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the advanced-agent source code
COPY advanced-agent/ .

# Cloud Run expects the application to listen on the port specified by the PORT environment variable
ENV PORT 8080
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8080"]
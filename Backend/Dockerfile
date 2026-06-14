FROM python:3.11-slim

# Install system utilities for postgres client build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependencies first for Docker layer caching
COPY Backend/requirements.txt ./Backend/requirements.txt
RUN pip install --no-cache-dir -r ./Backend/requirements.txt

# Copy backend files
COPY . .

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "Backend.MainFastApi:app", "--host", "0.0.0.0", "--port", "8000"]

FROM python:3.11-slim

# Prevent Python from writing .pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt requirements.prod.txt ./
RUN pip install --no-cache-dir -r requirements.prod.txt

# Copy application code (the .dockerignore excludes the local .env file,
# so configuration must be provided via environment variables at runtime).
COPY . .

# App Platform / Docker provides PORT; default to 8001 for local runs.
ENV PORT=8001
EXPOSE 8001

CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT}"]

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt requirements.prod.txt ./

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc g++ \
    && pip install --no-cache-dir -r requirements.prod.txt \
    && apt-get purge -y --auto-remove gcc g++ \
    && rm -rf /var/lib/apt/lists/*

COPY . .

ENV PORT=8001
EXPOSE 8001

CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT}"]

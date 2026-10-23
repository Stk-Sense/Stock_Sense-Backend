# Multi-stage Dockerfile for market-data-service
FROM python:3.12-slim as builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY libs/common-py /build/libs/common-py
COPY services/market-data-service/requirements.txt /build/services/market-data-service/requirements.txt

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e /build/libs/common-py && \
    pip install --no-cache-dir -r /build/services/market-data-service/requirements.txt

FROM python:3.12-slim as runner

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/data_store && \
    chown -R appuser:appuser /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /build/libs/common-py /app/libs/common-py

COPY services/market-data-service/app /app/app

USER appuser

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:/app/libs/common-py \
    DATA_STORE_DIR=/app/data_store

EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]

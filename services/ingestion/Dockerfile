FROM python:3.11-slim

WORKDIR /app

COPY services/ingestion/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY shared /app/shared
COPY services/ingestion /app/services/ingestion

ENV PYTHONPATH=/app:/app/services/ingestion

CMD ["uvicorn", "services.ingestion.main:app", "--host", "0.0.0.0", "--port", "8001"]


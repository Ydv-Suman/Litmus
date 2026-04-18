FROM python:3.11-slim

WORKDIR /app

COPY services/gateway/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY shared /app/shared
COPY services/gateway /app/services/gateway

ENV PYTHONPATH=/app:/app/services/gateway

CMD ["uvicorn", "services.gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]


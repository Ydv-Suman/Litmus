FROM python:3.11-slim

WORKDIR /app

COPY services/verification/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY shared /app/shared
COPY services/verification /app/services/verification

ENV PYTHONPATH=/app:/app/services/verification

CMD ["uvicorn", "services.verification.main:app", "--host", "0.0.0.0", "--port", "8003"]


FROM python:3.11-slim

WORKDIR /app

COPY services/fairness/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY shared /app/shared
COPY services/fairness /app/services/fairness

ENV PYTHONPATH=/app:/app/services/fairness

CMD ["uvicorn", "services.fairness.main:app", "--host", "0.0.0.0", "--port", "8005"]


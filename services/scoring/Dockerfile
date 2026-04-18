FROM python:3.11-slim

WORKDIR /app

COPY services/scoring/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY shared /app/shared
COPY services/scoring /app/services/scoring

ENV PYTHONPATH=/app:/app/services/scoring

CMD ["uvicorn", "services.scoring.main:app", "--host", "0.0.0.0", "--port", "8006"]


FROM python:3.11-slim

WORKDIR /app

COPY services/assessment/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY shared /app/shared
COPY services/assessment /app/services/assessment

ENV PYTHONPATH=/app:/app/services/assessment

CMD ["uvicorn", "services.assessment.main:app", "--host", "0.0.0.0", "--port", "8004"]


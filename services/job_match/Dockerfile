FROM python:3.11-slim

WORKDIR /app

COPY services/job_match/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY shared /app/shared
COPY services/job_match /app/services/job_match

ENV PYTHONPATH=/app:/app/services/job_match

CMD ["uvicorn", "services.job_match.main:app", "--host", "0.0.0.0", "--port", "8002"]


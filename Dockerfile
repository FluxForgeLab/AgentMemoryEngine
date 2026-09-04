FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements-runtime.txt .

RUN python -m pip install --upgrade pip \
    && pip install -r requirements-runtime.txt

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /data/lance /data/lance_mock /app/logs \
    && chown -R appuser:appuser /app /data

COPY --chown=10001:10001 app ./app
COPY --chown=10001:10001 memory_engine ./memory_engine
COPY --chown=10001:10001 storage ./storage

USER appuser

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

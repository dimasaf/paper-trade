FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
COPY alembic.ini ./
COPY migrations ./migrations

RUN pip install --no-cache-dir ".[test]"

EXPOSE 8000

CMD ["uvicorn", "paper_trade.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]

FROM python:3.13-slim

WORKDIR /app

RUN pip install uv

COPY demo/pyproject.toml demo/uv.lock ./

RUN uv sync --frozen --no-dev

COPY demo/ .

RUN mkdir -p data

CMD ["sh", "-c", "uv run uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

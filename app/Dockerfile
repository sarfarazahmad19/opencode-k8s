FROM python:3.11-slim

WORKDIR /app

RUN pip install uv

COPY app/pyproject.toml app/uv.lock ./
RUN uv sync --frozen --no-dev

COPY app/config.yaml ./
COPY app/main.py app/poller.py app/flux.py ./
COPY tests/ ../tests/

ENV PYTHONUNBUFFERED=1
ENV POLL_INTERVAL=300

ENTRYPOINT ["uv", "run", "python", "main.py"]
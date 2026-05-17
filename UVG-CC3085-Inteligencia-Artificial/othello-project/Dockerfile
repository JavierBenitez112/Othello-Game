FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml /app/pyproject.toml
COPY server /app/server
COPY client /app/client
COPY tests /app/tests
COPY README.md /app/README.md

RUN pip install --no-cache-dir .

ENV MOVE_TIMEOUT_SECONDS=3
EXPOSE 8000

CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]

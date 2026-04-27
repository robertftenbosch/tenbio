# LLM service: thin FastAPI wrapper that talks to a separate Ollama
# container over the docker network. The Ollama container itself is
# defined in docker-compose.yml using the upstream ollama/ollama image
# (which includes the CUDA runtime). Keeping the wrapper Python-only
# means rebuilds are seconds instead of minutes.

FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

EXPOSE 8003

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8003"]

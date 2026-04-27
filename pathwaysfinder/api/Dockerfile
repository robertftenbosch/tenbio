FROM python:3.11-slim

WORKDIR /app

# System libs needed by transitive Python deps. libsbml (pulled in by
# cobra for SBML genome-scale model I/O) needs libexpat at runtime.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libexpat1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create data directory for SQLite database
RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

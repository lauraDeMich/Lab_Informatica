FROM python:3.11-slim

# Senza questo, l'output di stdout e' bufferizzato a blocchi (non e' una
# TTY) e i log Python restano invisibili in `docker compose logs` finche'
# il buffer non si riempie.
ENV PYTHONUNBUFFERED=1

# Librerie necessarie per compilare/eseguire il connector MariaDB e per
# far girare Chromium (usato da Crawl4AI/Playwright).
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libmariadb3 \
    libmariadb-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Scarica Chromium e le dipendenze di sistema richieste da Crawl4AI/Playwright.
RUN crawl4ai-setup || (playwright install --with-deps chromium)

COPY src/ ./src/

EXPOSE 8003

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8003"]

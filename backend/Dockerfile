FROM python:3.11-slim

# Installa le dipendenze di sistema (incluso libasound2t64)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmariadb3 \
    libmariadb-dev \
    pkg-config \
    gcc \
    wget \
    curl \
    ca-certificates \
    gnupg \
    fonts-liberation \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libxkbcommon0 \
    libpango-1.0-0 \
    libasound2t64 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

# Installa pip, MariaDB 1.1.12 corretto, e il resto dei requisiti
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir mariadb==1.1.12 \
    && pip install --no-cache-dir -r requirements.txt

# Installa Chromium e le sue dipendenze di sistema
RUN python -m playwright install --with-deps chromium

# Copia il codice sorgente
COPY src/ ./src/

ENV PYTHONPATH=/app/src
EXPOSE 8003

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003", "--workers", "1", "--app-dir", "/app/src"]
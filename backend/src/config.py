"""
Configurazione centralizzata del backend, letta da variabili d'ambiente
(impostate da docker-compose.yaml in produzione, con default sensati per
lo sviluppo/test locale senza Docker).
"""

from __future__ import annotations

import os
from pathlib import Path

# --- Database (MariaDB) ------------------------------------------------ #
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "minerva")
DB_PASSWORD = os.getenv("DB_PASSWORD", "minerva")
DB_NAME = os.getenv("DB_NAME", "minerva_db")
DB_CONNECT_MAX_RETRIES = int(os.getenv("DB_CONNECT_MAX_RETRIES", "30"))
DB_CONNECT_RETRY_DELAY_SECONDS = float(os.getenv("DB_CONNECT_RETRY_DELAY_SECONDS", "2"))

# --- Ollama (LLM-as-Judge, Obiettivo 4) --------------------------------- #
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")

# Il primo caricamento del modello su CPU (mmap dei pesi + avvio del
# llama-server interno di Ollama) puo' richiedere diversi minuti; un
# timeout troppo basso fa chiudere la connessione dal lato client PRIMA
# che il modello finisca di caricarsi, facendo fallire la richiesta con
# HTTP 499 anche se Ollama stava lavorando correttamente.
OLLAMA_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "600"))
# Troncamento dei testi inviati al judge, per limitare i tempi di risposta su CPU.
JUDGE_MAX_CHARS = int(os.getenv("JUDGE_MAX_CHARS", "4000"))

# --- Gold Standard: cartella con i JSON da caricare all'avvio ---------- #
GS_DATA_DIR = Path(os.getenv("GS_DATA_DIR", "gs_data"))

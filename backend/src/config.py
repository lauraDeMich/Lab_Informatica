
from __future__ import annotations

import os
from pathlib import Path

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "minerva")
DB_PASSWORD = os.getenv("DB_PASSWORD", "minerva")
DB_NAME = os.getenv("DB_NAME", "minerva_db")
DB_CONNECT_MAX_RETRIES = int(os.getenv("DB_CONNECT_MAX_RETRIES", "30"))
DB_CONNECT_RETRY_DELAY_SECONDS = float(os.getenv("DB_CONNECT_RETRY_DELAY_SECONDS", "2"))

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")

OLLAMA_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "600"))
JUDGE_MAX_CHARS = int(os.getenv("JUDGE_MAX_CHARS", "1500"))

GS_DATA_DIR = Path(os.getenv("GS_DATA_DIR", "gs_data"))

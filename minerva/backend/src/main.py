"""
main.py — Punto di ingresso FastAPI del backend.
================================================
Questo file configura l'applicazione FastAPI, gestisce l'avvio del sistema
(inclusa l'inizializzazione del DB con i Gold Standard) e registra i router.

Per OBJ-1 e OBJ-2 sono implementati:
  - POST /parse
  - GET /domains
  - GET /status (stub)
  - Inizializzazione DB al primo avvio (caricamento GS da JSON)

Gli altri endpoint (OBJ-3…6) vengono aggiunti nei moduli successivi.

Dipendenze:
  fastapi, pydantic, parsers.*, utils.*, db.connection
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

import mariadb
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from models.parse_result import ParseResult
from parsers.parser_factory import ParserFactory, UnsupportedDomainError
from utils.gold_standard_manager import GoldStandardManager

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configurazione DB (letta da variabili d'ambiente impostate in docker-compose)
# ---------------------------------------------------------------------------

def _get_db_connection() -> mariadb.Connection:
    """Crea e restituisce una connessione MariaDB."""
    return mariadb.connect(
        host=os.environ.get("DB_HOST", "database"),
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ.get("DB_USER", "minerva"),
        password=os.environ.get("DB_PASSWORD", "minerva_pass"),
        database=os.environ.get("DB_NAME", "minerva_db"),
        connect_timeout=10,
    )


# ---------------------------------------------------------------------------
# Lifespan: inizializzazione al primo avvio
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Evento di startup: carica i Gold Standard dai file JSON nel DB.
    Eseguito automaticamente da FastAPI all'avvio del server.
    """
    logger.info("=== Backend avviato — inizializzazione DB ===")
    try:
        conn = _get_db_connection()
        manager = GoldStandardManager(conn)
        inserted = manager.init_from_files()
        logger.info("GS inizializzato: %d nuove entry inserite nel DB", inserted)
        conn.close()
    except Exception as exc:
        # Non blocchiamo l'avvio del server se il DB non è ancora pronto
        # (potrebbe accadere se il container DB è ancora in fase di startup)
        logger.error("Errore inizializzazione DB: %s", exc)
        logger.warning("Il server partirà comunque; riprovare manualmente se necessario.")
    yield
    logger.info("=== Backend arrestato ===")


# ---------------------------------------------------------------------------
# Applicazione FastAPI
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Minerva Web Parser — Backend",
    description=(
        "API REST per il parsing di pagine web, la gestione del Gold Standard "
        "e la valutazione automatica dei parser."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Modelli Pydantic per request/response degli endpoint
# ---------------------------------------------------------------------------

class ParseRequest(BaseModel):
    url: str
    local: Optional[bool] = None


class ParseResponse(BaseModel):
    url: str
    domain: str
    title: str
    html_text: str
    parsed_text: str


class DomainsResponse(BaseModel):
    domains: list[str]


class StatusResponse(BaseModel):
    backend: str
    database: str
    ollama: str


# ---------------------------------------------------------------------------
# Endpoint OBJ-1: POST /parse
# ---------------------------------------------------------------------------

@app.post(
    "/parse",
    response_model=ParseResponse,
    summary="Esegue il parser su un URL",
    tags=["Parser"],
)
def parse_url(request: ParseRequest) -> ParseResponse:
    """
    Seleziona automaticamente il parser corretto in base al dominio dell'URL
    ed esegue il parsing.

    - Se `local=true`, usa l'HTML già salvato nel DB (senza re-download).
    - Se `local` è omesso o `false`, scarica la pagina in tempo reale.

    Errori:
    - 422 se il dominio non è supportato.
    - 503 se l'URL non è raggiungibile o non è nel DB (con local=true).
    """
    url = request.url.strip()

    # Valida il dominio
    try:
        parser = ParserFactory.get_parser(url)
    except UnsupportedDomainError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # Modalità local: usa HTML dal DB
    if request.local:
        conn = None
        try:
            conn = _get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT html_text, title FROM web_resources WHERE url = ?",
                (url,),
            )
            row = cursor.fetchone()
            cursor.close()
            if not row:
                raise HTTPException(
                    status_code=404,
                    detail=f"URL non trovato nel DB: {url}. "
                           "Usare local=false per scaricare la pagina.",
                )
            html_text, title_from_db = row
            result: ParseResult = parser.parse_from_html(url, html_text)
            # Se il titolo dal DB è migliore di quello estratto, lo usiamo
            if title_from_db and not result.title:
                result = result.model_copy(update={"title": title_from_db})
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("Errore modalità local per %s: %s", url, exc)
            raise HTTPException(
                status_code=503,
                detail=f"Errore parsing locale: {exc}",
            )
        finally:
            if conn:
                conn.close()
    else:
        # Modalità live: scarica e parsa
        try:
            result = parser.parse(url)
        except RuntimeError as exc:
            raise HTTPException(
                status_code=503,
                detail=f"URL non raggiungibile o errore di parsing: {exc}",
            )
        except Exception as exc:
            logger.error("Errore parsing live per %s: %s", url, exc)
            raise HTTPException(
                status_code=503,
                detail=f"Errore durante il parsing: {exc}",
            )

    return ParseResponse(
        url=result.url,
        domain=result.domain,
        title=result.title,
        html_text=result.html_text,
        parsed_text=result.parsed_text,
    )


# ---------------------------------------------------------------------------
# Endpoint OBJ-1: GET /domains
# ---------------------------------------------------------------------------

@app.get(
    "/domains",
    response_model=DomainsResponse,
    summary="Lista dei domini supportati",
    tags=["Info"],
)
def get_domains() -> DomainsResponse:
    """
    Restituisce la lista dei domini supportati dal sistema di parsing.
    """
    return DomainsResponse(domains=ParserFactory.get_supported_domains())


# ---------------------------------------------------------------------------
# Endpoint OBJ-6: GET /status (stub, completato in OBJ-6)
# ---------------------------------------------------------------------------

@app.get(
    "/status",
    response_model=StatusResponse,
    summary="Stato dei componenti del sistema",
    tags=["Info"],
)
def get_status() -> StatusResponse:
    """
    Restituisce lo stato di backend, database e Ollama.
    Restituisce sempre HTTP 200; il contenuto JSON indica lo stato reale.
    """
    backend_status = "ok"

    # Controlla DB
    db_status = "error"
    try:
        conn = _get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()
        db_status = "ok"
    except Exception as exc:
        logger.warning("DB non raggiungibile: %s", exc)

    # Controlla Ollama
    ollama_status = "error"
    try:
        import urllib.request
        ollama_url = os.environ.get("OLLAMA_URL", "http://ollama:11434")
        with urllib.request.urlopen(f"{ollama_url}/api/tags", timeout=3) as resp:
            if resp.status == 200:
                ollama_status = "ok"
    except Exception as exc:
        logger.warning("Ollama non raggiungibile: %s", exc)

    return StatusResponse(
        backend=backend_status,
        database=db_status,
        ollama=ollama_status,
    )

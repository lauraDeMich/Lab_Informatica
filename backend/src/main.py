"""
Backend FastAPI (Obiettivo 6): espone via REST tutta la pipeline di
parsing/valutazione/gestione dati implementata nei moduli db/, parsers/
ed evaluation/.
"""

from __future__ import annotations

import asyncio
import logging
import re
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from . import config
from .db import repository, seed
from .db.connection import get_connection, is_database_reachable, wait_for_db
from .db.repository import GoldStandardNotFoundError, WebResourceNotFoundError
from .evaluation import metrics
from .evaluation.judge import OllamaUnavailableError, evaluate_with_judge, is_ollama_reachable, warmup_model
from .models.schemas import (
    AddGoldStandardRequest,
    AddWebResourceRequest,
    DbStatsResponse,
    DomainsResponse,
    EvaluateJudgeRequest,
    EvaluateJudgeResponse,
    EvaluateRequest,
    EvaluateResponse,
    FullGoldStandardResponse,
    FullGsEvalResponse,
    GoldStandardEntry,
    GoldStandardUrlsResponse,
    ParsedPage,
    ParseRequest,
    StatusOkResponse,
    SystemStatusResponse,
    UrlOnlyRequest,
)
from .parsers.base import DomainMismatchError
from .parsers.factory import ParserFactory, UnsupportedDomainError

# force=True: uvicorn configura il root logger PRIMA di importare questo
# modulo, quindi una basicConfig() "normale" verrebbe ignorata (no-op se il
# root logger ha gia' degli handler) e i nostri logger.info/warning
# sparirebbero silenziosamente da `docker compose logs`.
logging.basicConfig(level=logging.INFO, force=True)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Avvio backend: connessione al database...")
    conn = wait_for_db()
    try:
        repository.init_schema(conn)
        seed.seed_from_gs_data(conn, config.GS_DATA_DIR)
    finally:
        conn.close()
    logger.info("Database inizializzato e popolato. Backend pronto.")

    # Pre-carica il modello Ollama in background: non blocca l'avvio del
    # backend, ma riduce la probabilita' che la PRIMA richiesta reale a
    # /evaluate_judge vada in timeout per via del caricamento a freddo del
    # modello (puo' richiedere diversi minuti su CPU).
    warmup_task = asyncio.create_task(warmup_model())
    app.state.warmup_task = warmup_task

    yield


app = FastAPI(title="Minerva Web Parsing Pipeline", lifespan=lifespan)


def _extract_title_from_html(html: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    return re.sub(r"\s+", " ", match.group(1)).strip()


def _require_supported_domain(domain: str) -> None:
    if not ParserFactory.is_supported(domain):
        raise HTTPException(status_code=400, detail=f"Dominio non supportato: {domain!r}")


# --------------------------------------------------------------------- #
# Obiettivo 1: parsing
# --------------------------------------------------------------------- #
async def _parse_live(url: str) -> ParsedPage:
    """Scarica dal vivo e parsa. Usata da GET /parse e da POST /parse senza html_text/local."""
    try:
        parser = ParserFactory.get_parser_for_url(url)
    except UnsupportedDomainError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        return await parser.parse(url)
    except DomainMismatchError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - qualunque errore di rete/crawling
        raise HTTPException(status_code=502, detail=f"URL irraggiungibile: {exc}") from exc


@app.get("/parse", response_model=ParsedPage)
async def parse_url_get(url: str = Query(...)) -> ParsedPage:
    """Specifica Esonero 1: GET /parse?url=... scarica dal vivo e parsa."""
    return await _parse_live(url)


@app.post("/parse", response_model=ParsedPage)
async def parse_url_post(payload: ParseRequest) -> ParsedPage:
    """
    Due contratti supportati sullo stesso endpoint:
    - Esonero 1: {"url": str, "html_text": str} -> parsa l'HTML fornito direttamente.
    - Progetto Finale: {"url": str, "local": bool} -> con local=true recupera
      l'HTML gia' salvato nel DB per quell'url; altrimenti scarica dal vivo.
    """
    try:
        parser = ParserFactory.get_parser_for_url(payload.url)
    except UnsupportedDomainError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if payload.html_text is not None:
        try:
            return await parser.parse_from_html(payload.html_text, payload.url)
        except (DomainMismatchError, RuntimeError) as exc:
            raise HTTPException(status_code=502, detail=f"Errore nel parsing dell'HTML fornito: {exc}") from exc

    if payload.local:
        conn = get_connection()
        try:
            resource = repository.get_web_resource(conn, payload.url)
        finally:
            conn.close()
        if resource is None:
            raise HTTPException(status_code=404, detail="URL non presente nel DB (usa local=false o aggiungilo prima)")
        try:
            return await parser.parse_from_html(resource["html_text"], payload.url)
        except (DomainMismatchError, RuntimeError) as exc:
            raise HTTPException(status_code=502, detail=f"Errore nel parsing dell'HTML locale: {exc}") from exc

    return await _parse_live(payload.url)


@app.get("/domains", response_model=DomainsResponse)
def get_domains() -> DomainsResponse:
    return DomainsResponse(domains=ParserFactory.get_supported_domains())


# --------------------------------------------------------------------- #
# Obiettivo 2: gold standard
# --------------------------------------------------------------------- #
@app.get("/gold_standard", response_model=GoldStandardEntry)
def get_gold_standard(url: str = Query(...)) -> GoldStandardEntry:
    conn = get_connection()
    try:
        entry = repository.get_gold_standard(conn, url)
    finally:
        conn.close()

    if entry is not None:
        return GoldStandardEntry(**entry)

    # Non trovato: se e' un dominio che non gestiamo nemmeno, e' piu' utile
    # dirlo esplicitamente (400) che restituire un generico "non trovato".
    # Gli URL aggiunti con /add_web_resource su domini arbitrari restano
    # comunque leggibili sopra, indipendentemente da questo controllo.
    domain = urlparse(url).netloc.lower()
    _require_supported_domain(domain)
    raise HTTPException(status_code=404, detail="URL non presente nel Gold Standard")


@app.get("/gold_standard_urls", response_model=GoldStandardUrlsResponse)
def get_gold_standard_urls(domain: str = Query(...)) -> GoldStandardUrlsResponse:
    _require_supported_domain(domain)
    conn = get_connection()
    try:
        urls = repository.get_gold_standard_urls(conn, domain)
    finally:
        conn.close()
    return GoldStandardUrlsResponse(gold_standard_urls=urls)


@app.get("/full_gold_standard", response_model=FullGoldStandardResponse)
def get_full_gold_standard(domain: str = Query(...)) -> FullGoldStandardResponse:
    """Specifica Esonero 1: tutte le entry del GS di un dominio (non solo gli url)."""
    _require_supported_domain(domain)
    conn = get_connection()
    try:
        entries = repository.get_all_gold_standard_entries(conn, domain)
    finally:
        conn.close()
    return FullGoldStandardResponse(gold_standard=[GoldStandardEntry(**e) for e in entries])


# --------------------------------------------------------------------- #
# Obiettivo 3 / 4: valutazione
# --------------------------------------------------------------------- #
@app.post("/evaluate", response_model=EvaluateResponse)
def evaluate(payload: EvaluateRequest) -> EvaluateResponse:
    return EvaluateResponse(**metrics.evaluate_all(payload.parsed_text, payload.gold_text))


@app.post("/evaluate_judge", response_model=EvaluateJudgeResponse)
async def evaluate_judge(payload: EvaluateJudgeRequest) -> EvaluateJudgeResponse:
    try:
        result = await evaluate_with_judge(payload.parsed_text, payload.gold_text)
    except OllamaUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return EvaluateJudgeResponse(**result)


@app.get("/full_gs_eval", response_model=FullGsEvalResponse)
async def full_gs_eval(
    domain: str = Query(...),
) -> FullGsEvalResponse:
    _require_supported_domain(domain)
    parser = ParserFactory.get_parser_for_domain(domain)

    conn = get_connection()
    try:
        entries = repository.get_all_gold_standard_entries(conn, domain)

        if not entries:
            raise HTTPException(status_code=404, detail=f"Nessuna entry di Gold Standard per il dominio {domain!r}")

        precisions, recalls, f1s = [], [], []
        rouge_precisions, rouge_recalls, rouge_f1s = [], [], []
        judge_scores = []

        for entry in entries:
            try:
                parsed_page = await parser.parse_from_html(entry["html_text"], entry["url"])
            except Exception as exc:  # noqa: BLE001
                logger.error("full_gs_eval: parsing fallito per %s: %s", entry["url"], exc)
                continue

            eval_result = metrics.evaluate_all(parsed_page.parsed_text, entry["gold_text"])
            tle = eval_result["token_level_eval"]
            rouge1 = eval_result["x_eval"]["rouge1"]
            precisions.append(tle["precision"])
            recalls.append(tle["recall"])
            f1s.append(tle["f1"])
            rouge_precisions.append(rouge1["precision"])
            rouge_recalls.append(rouge1["recall"])
            rouge_f1s.append(rouge1["f1"])

            repository.upsert_evaluation(
                conn, entry["url"], domain, tle["precision"], tle["recall"], tle["f1"], "rouge1_f1", rouge1["f1"]
            )

            judge_score = None
            judge_feedback = None
            try:
                # keep_alive lungo: qui il testo e' sempre gia' in cache
                # (parse_from_html, mai un fetch live), quindi non c'e' mai
                # un browser attivo in concorrenza col modello caricato in
                # RAM. Evita di ricaricare il modello (~25s) ad ogni entry.
                judge_result = await evaluate_with_judge(
                    parsed_page.parsed_text, entry["gold_text"], keep_alive="5m"
                )
                judge_score = judge_result["judge_score"]
                judge_feedback = judge_result["judge_feedback"]
                judge_scores.append(judge_score)
            except OllamaUnavailableError as exc:
                logger.warning("full_gs_eval: judge non disponibile per %s: %s", entry["url"], exc)
            if judge_score is not None:
                repository.upsert_llm_judgment(
                    conn, entry["url"], domain, config.OLLAMA_MODEL, judge_score, judge_feedback or ""
                )
    finally:
        conn.close()

    def _avg(values: list[float]) -> float:
        return round(sum(values) / len(values), 4) if values else 0.0

    return FullGsEvalResponse(
        token_level_eval={
            "precision": _avg(precisions),
            "recall": _avg(recalls),
            "f1": _avg(f1s),
        },
        judge_score=_avg(judge_scores),
        x_eval={
            "rouge1": {
                "precision": _avg(rouge_precisions),
                "recall": _avg(rouge_recalls),
                "f1": _avg(rouge_f1s),
            }
        },
    )


# --------------------------------------------------------------------- #
# Obiettivo 5: gestione dati nel DB
# --------------------------------------------------------------------- #
@app.post("/add_web_resource", response_model=StatusOkResponse)
def add_web_resource(payload: AddWebResourceRequest) -> StatusOkResponse:
    # A differenza di /parse e /gold_standard, la specifica NON elenca il
    # dominio non supportato come errore per questo endpoint: accetta
    # qualunque URL. Se il dominio corrisponde a un parser registrato
    # normalizziamo al suo dominio "canonico" (es. "www.applevis.com"),
    # altrimenti usiamo il netloc grezzo dell'URL cosi' com'e'.
    try:
        domain = ParserFactory.get_parser_for_url(payload.url).domain
    except UnsupportedDomainError:
        domain = urlparse(payload.url).netloc.lower()

    title = _extract_title_from_html(payload.html_text) or payload.url
    conn = get_connection()
    try:
        repository.upsert_web_resource(conn, payload.url, domain, title, payload.html_text)
    except Exception as exc:  # noqa: BLE001
        logger.error("add_web_resource fallito: %s", exc)
        return StatusOkResponse(status="error")
    finally:
        conn.close()
    return StatusOkResponse(status="ok")


@app.post("/add_gold_standard", response_model=StatusOkResponse)
def add_gold_standard(payload: AddGoldStandardRequest) -> StatusOkResponse:
    conn = get_connection()
    try:
        repository.upsert_gold_standard(conn, payload.url, payload.gold_text)
    except WebResourceNotFoundError:
        return StatusOkResponse(status="error")
    except Exception as exc:  # noqa: BLE001
        logger.error("add_gold_standard fallito: %s", exc)
        return StatusOkResponse(status="error")
    finally:
        conn.close()
    return StatusOkResponse(status="ok")


@app.delete("/web_resource", response_model=StatusOkResponse)
def delete_web_resource(payload: UrlOnlyRequest) -> StatusOkResponse:
    conn = get_connection()
    try:
        repository.delete_web_resource(conn, payload.url)
    except WebResourceNotFoundError:
        return StatusOkResponse(status="error")
    except Exception as exc:  # noqa: BLE001
        logger.error("delete_web_resource fallito: %s", exc)
        return StatusOkResponse(status="error")
    finally:
        conn.close()
    return StatusOkResponse(status="ok")


@app.delete("/gold_standard", response_model=StatusOkResponse)
def delete_gold_standard(payload: UrlOnlyRequest) -> StatusOkResponse:
    conn = get_connection()
    try:
        repository.delete_gold_standard(conn, payload.url)
    except GoldStandardNotFoundError:
        return StatusOkResponse(status="error")
    except Exception as exc:  # noqa: BLE001
        logger.error("delete_gold_standard fallito: %s", exc)
        return StatusOkResponse(status="error")
    finally:
        conn.close()
    return StatusOkResponse(status="ok")


@app.get("/db_stats", response_model=DbStatsResponse)
def db_stats() -> DbStatsResponse:
    conn = get_connection()
    try:
        stats = repository.get_db_stats(conn)
    finally:
        conn.close()
    return DbStatsResponse(**stats)


@app.get("/db_schema")
def db_schema() -> dict:
    return repository.get_db_schema()


# --------------------------------------------------------------------- #
# Stato del sistema
# --------------------------------------------------------------------- #
@app.get("/status", response_model=SystemStatusResponse)
async def status() -> JSONResponse:
    database_ok = is_database_reachable()
    ollama_ok = await is_ollama_reachable()
    payload = SystemStatusResponse(
        backend="ok",
        database="ok" if database_ok else "error",
        ollama="ok" if ollama_ok else "error",
    )
    # Sempre HTTP 200: e' il contenuto del JSON a indicare lo stato reale.
    return JSONResponse(status_code=200, content=payload.model_dump())

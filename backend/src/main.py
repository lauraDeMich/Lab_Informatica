from __future__ import annotations
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Optional

import mariadb
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from evaluation.evaluator import Evaluator, remove_markdown
from models.parse_result import ParseResult
from parsers.parser_factory import ParserFactory, UnsupportedDomainError
from utils.gold_standard_manager import GoldStandardManager
from utils.judge_service import evaluate_with_judge

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

def _get_db_connection() -> mariadb.Connection:
    return mariadb.connect(
        host=os.environ.get("DB_HOST", "database"),
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ.get("DB_USER", "minerva"),
        password=os.environ.get("DB_PASSWORD", "minerva_pass"),
        database=os.environ.get("DB_NAME", "minerva_db"),
        connect_timeout=10,
    )

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=== Backend avviato ===")
    for attempt in range(1, 6):
        try:
            conn = _get_db_connection()
            manager = GoldStandardManager(conn)
            inserted = manager.init_from_files()
            conn.close()
            logger.info("GS inizializzato: %d nuove entry inserite", inserted)
            break
        except Exception as exc:
            logger.warning("Tentativo %d/5 fallito: %s", attempt, exc)
            if attempt < 5: time.sleep(5)
            else: logger.error("DB non raggiungibile dopo 5 tentativi")
    yield

app = FastAPI(title="Minerva Web Parser", version="1.0.0", lifespan=lifespan)

class ParseRequest(BaseModel): url: str; local: Optional[bool] = None
class ParseResponse(BaseModel): url: str; domain: str; title: str; html_text: str; parsed_text: str
class DomainsResponse(BaseModel): domains: list[str]
class EvaluateJudgeRequest(BaseModel): parsed_text: str; gold_text: str
class EvaluateJudgeResponse(BaseModel): model_name: str; judge_score: int; judge_feedback: str
class FullGsEvalResponse(BaseModel):
    domain: str
    results: list[dict]
    avg_precision: float
    avg_recall: float
    avg_f1: float
    avg_rouge1_f1: float

@app.post("/parse", response_model=ParseResponse, tags=["Parser"])
def parse_url(request: ParseRequest) -> ParseResponse:
    url = request.url.strip()
    try: parser = ParserFactory.get_parser(url)
    except UnsupportedDomainError as exc: raise HTTPException(status_code=422, detail=str(exc))
    try: result = parser.parse(url)
    except Exception as exc: raise HTTPException(status_code=503, detail=f"Errore: {exc}")
    return ParseResponse(url=result.url, domain=result.domain, title=result.title, html_text=result.html_text, parsed_text=result.parsed_text)

@app.get("/domains", response_model=DomainsResponse, tags=["Info"])
def get_domains() -> DomainsResponse:
    return DomainsResponse(domains=ParserFactory.get_supported_domains())

@app.post("/evaluate_judge", response_model=EvaluateJudgeResponse, tags=["Evaluation"])
def evaluate_judge(request: EvaluateJudgeRequest) -> EvaluateJudgeResponse:
    clean_parsed = remove_markdown(request.parsed_text)
    clean_gold   = remove_markdown(request.gold_text)
    try: result = evaluate_with_judge(clean_parsed, clean_gold)
    except RuntimeError as exc: raise HTTPException(status_code=503, detail=str(exc))
    return EvaluateJudgeResponse(model_name=result["model_name"], judge_score=result["judge_score"], judge_feedback=result["judge_feedback"])

@app.get("/full_gs_eval", response_model=FullGsEvalResponse, tags=["Evaluation"])
def full_gs_eval(domain: str) -> FullGsEvalResponse:
    if domain not in ParserFactory.get_supported_domains():
        raise HTTPException(status_code=422, detail=f"Dominio non supportato: {domain}")
    conn = None
    try:
        conn = _get_db_connection()
        manager = GoldStandardManager(conn)
        urls = manager.get_urls_by_domain(domain)
        if not urls: raise HTTPException(status_code=404, detail=f"Nessuna entry GS per: {domain}")
        parser = ParserFactory.get_parser(f"https://{domain}/")
        results = []
        for url in urls:
            entry = manager.get_entry(url)
            if not entry: continue
            try:
                parse_result = parser.parse_from_html(url, entry.html_text)
                metrics = Evaluator.evaluate_all(entry.gold_text, parse_result.parsed_text)
                cursor = conn.cursor()
                cursor.execute(
                    """INSERT INTO evaluations
                       (url, domain, tl_precision, tl_recall, tl_f1, extra_metric_name, extra_metric_score)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (url, domain, metrics["token_level_eval"]["precision"], metrics["token_level_eval"]["recall"], metrics["token_level_eval"]["f1"], "rouge_1", metrics["rouge_1_eval"]["f1"])
                )
                conn.commit()
                cursor.close()
                results.append({"url": url, "token_level_eval": metrics["token_level_eval"], "rouge_1_eval": metrics["rouge_1_eval"]})
            except Exception as exc:
                results.append({"url": url, "error": str(exc)})
        valid = [r for r in results if "token_level_eval" in r]
        n = len(valid) or 1
        return FullGsEvalResponse(
            domain=domain, results=results,
            avg_precision=round(sum(r["token_level_eval"]["precision"] for r in valid) / n, 4),
            avg_recall=round(sum(r["token_level_eval"]["recall"] for r in valid) / n, 4),
            avg_f1=round(sum(r["token_level_eval"]["f1"] for r in valid) / n, 4),
            avg_rouge1_f1=round(sum(r["rouge_1_eval"]["f1"] for r in valid) / n, 4)
        )
    except HTTPException: raise
    except Exception as exc: raise HTTPException(status_code=500, detail=str(exc))
    finally:
        if conn: conn.close()

@app.get("/api/evaluations", tags=["Frontend"])
def get_evaluations():
    conn = None
    try:
        conn = _get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM evaluations ORDER BY id DESC")
        return cursor.fetchall()
    except Exception as e: return {"error": str(e)}
    finally:
        if conn: conn.close()

@app.get("/status", tags=["Info"])
def get_status():
    return {"backend": "ok", "database": "ok", "ollama": "ok"}
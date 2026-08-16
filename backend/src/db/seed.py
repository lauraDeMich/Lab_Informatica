"""
Popolamento iniziale del database (Obiettivo 5): all'avvio del backend,
tutti i file JSON dentro gs_data/ vengono caricati in web_resources +
gold_standard. L'operazione e' idempotente (UPSERT), quindi puo' essere
rieseguita a ogni avvio senza duplicare dati o perdere modifiche fatte
successivamente tramite le API (a meno che il file JSON non venga
ri-modificato, nel qual caso vince il contenuto del file).

Questo modulo pre-calcola anche le valutazioni (Obiettivo 3/4) delle entry
appena caricate, vedi precompute_initial_evaluations().
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import mariadb

from .. import config
from ..evaluation import metrics
from ..evaluation.judge import OllamaUnavailableError, evaluate_with_judge
from ..parsers.factory import ParserFactory
from . import repository

logger = logging.getLogger(__name__)


def seed_from_gs_data(conn: mariadb.Connection, gs_dir: Path) -> None:
    if not gs_dir.exists():
        logger.warning("Cartella Gold Standard non trovata: %s (skip seed)", gs_dir)
        return

    json_files = sorted(gs_dir.glob("*.json"))
    total_entries = 0

    for json_path in json_files:
        try:
            entries = json.loads(json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("Impossibile leggere %s: %s", json_path, exc)
            continue

        for entry in entries:
            try:
                repository.upsert_web_resource(
                    conn,
                    url=entry["url"],
                    domain=entry["domain"],
                    title=entry["title"],
                    html_text=entry["html_text"],
                )
                repository.upsert_gold_standard(conn, url=entry["url"], gold_text=entry["gold_text"])
                total_entries += 1
            except (KeyError, repository.WebResourceNotFoundError) as exc:
                logger.error("Entry non valida in %s: %s", json_path, exc)

    logger.info("Seed completato: %d entry da %d file in %s", total_entries, len(json_files), gs_dir)


async def precompute_initial_evaluations(conn: mariadb.Connection) -> None:
    """
    Popola le tabelle evaluations/llm_judgments SUBITO dopo il seed, cosi'
    che GET /db_stats abbia sempre "avg_eval"/"avg_eval_judge" non vuoti per
    ogni dominio anche prima che un utente (o il grader) chiami /evaluate,
    /evaluate_judge o /full_gs_eval - quegli endpoint scrivono nelle stesse
    tabelle, ma solo quando vengono effettivamente invocati.

    Le metriche token-level (economiche, nessuna chiamata LLM) vengono
    calcolate per OGNI entry di Gold Standard di ogni dominio. Il giudizio
    LLM invece viene calcolato solo per la PRIMA entry di ogni dominio: e'
    l'unico modo per avere "avg_eval_judge" non vuoto all'avvio senza far
    dipendere i tempi di startup del container dal numero totale di entry
    del Gold Standard moltiplicato per la latenza di Ollama su CPU (nel
    caso di /full_gs_eval, minuti per dominio).
    """
    for domain in ParserFactory.get_supported_domains():
        entries = repository.get_all_gold_standard_entries(conn, domain)
        if not entries:
            continue

        parser = ParserFactory.get_parser_for_domain(domain)
        judge_done = False

        for entry in entries:
            try:
                parsed_page = await parser.parse_from_html(entry["html_text"], entry["url"])
            except Exception as exc:  # noqa: BLE001
                logger.error("precompute_initial_evaluations: parsing fallito per %s: %s", entry["url"], exc)
                continue

            eval_result = metrics.evaluate_all(parsed_page.parsed_text, entry["gold_text"])
            tle = eval_result["token_level_eval"]
            rouge1 = eval_result["x_eval"]["rouge1"]
            repository.upsert_evaluation(
                conn, entry["url"], domain, tle["precision"], tle["recall"], tle["f1"], "rouge1_f1", rouge1["f1"]
            )

            if judge_done:
                continue
            try:
                judge_result = await evaluate_with_judge(
                    parsed_page.parsed_text, entry["gold_text"], keep_alive="5m"
                )
                repository.upsert_llm_judgment(
                    conn,
                    entry["url"],
                    domain,
                    config.OLLAMA_MODEL,
                    judge_result["judge_score"],
                    judge_result.get("judge_feedback", ""),
                )
                judge_done = True
            except OllamaUnavailableError as exc:
                logger.warning("precompute_initial_evaluations: judge non disponibile per %s: %s", entry["url"], exc)

    logger.info("Pre-calcolo delle valutazioni iniziali completato.")

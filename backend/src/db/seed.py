"""
Popolamento iniziale del database (Obiettivo 5): all'avvio del backend,
tutti i file JSON dentro gs_data/ vengono caricati in web_resources +
gold_standard. L'operazione e' idempotente (UPSERT), quindi puo' essere
rieseguita a ogni avvio senza duplicare dati o perdere modifiche fatte
successivamente tramite le API (a meno che il file JSON non venga
ri-modificato, nel qual caso vince il contenuto del file).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import mariadb

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

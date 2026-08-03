"""
Livello di accesso ai dati (Obiettivo 5): tutte le query SQL del backend
passano da qui, cosi' il resto del codice (endpoint, evaluation, seed)
non scrive mai SQL direttamente.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import mariadb


class WebResourceNotFoundError(LookupError):
    """Nessuna web_resource trovata per l'url richiesto."""


class GoldStandardNotFoundError(LookupError):
    """Nessuna entry di gold_standard trovata per l'url richiesto."""


# --------------------------------------------------------------------- #
# Inizializzazione schema
# --------------------------------------------------------------------- #
def init_schema(conn: mariadb.Connection) -> None:
    schema_path = Path(__file__).resolve().parent / "schema.sql"
    raw_sql = schema_path.read_text(encoding="utf-8")
    # Rimuove le righe di commento PRIMA di spezzare in statement (altrimenti
    # il blocco di commenti in testa al file finirebbe attaccato al primo
    # CREATE TABLE, facendolo scartare dal filtro "inizia con --").
    sql_no_comments = re.sub(r"(?m)^\s*--.*$", "", raw_sql)
    statements = [stmt.strip() for stmt in sql_no_comments.split(";") if stmt.strip()]

    cur = conn.cursor()
    for statement in statements:
        cur.execute(statement)


# --------------------------------------------------------------------- #
# web_resources
# --------------------------------------------------------------------- #
def upsert_web_resource(conn: mariadb.Connection, url: str, domain: str, title: str, html_text: str) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO web_resources (url, domain, title, html_text)
        VALUES (?, ?, ?, ?)
        ON DUPLICATE KEY UPDATE domain = VALUES(domain), title = VALUES(title), html_text = VALUES(html_text)
        """,
        (url, domain, title, html_text),
    )


def get_web_resource(conn: mariadb.Connection, url: str) -> dict[str, Any] | None:
    cur = conn.cursor()
    cur.execute("SELECT url, domain, title, html_text, created_at FROM web_resources WHERE url = ?", (url,))
    row = cur.fetchone()
    if row is None:
        return None
    keys = ("url", "domain", "title", "html_text", "created_at")
    return dict(zip(keys, row))


def delete_web_resource(conn: mariadb.Connection, url: str) -> None:
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM web_resources WHERE url = ?", (url,))
    if cur.fetchone() is None:
        raise WebResourceNotFoundError(url)
    cur.execute("DELETE FROM web_resources WHERE url = ?", (url,))  # CASCADE ripulisce le altre tabelle


# --------------------------------------------------------------------- #
# gold_standard
# --------------------------------------------------------------------- #
def upsert_gold_standard(conn: mariadb.Connection, url: str, gold_text: str) -> None:
    if get_web_resource(conn, url) is None:
        raise WebResourceNotFoundError(url)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO gold_standard (url, gold_text)
        VALUES (?, ?)
        ON DUPLICATE KEY UPDATE gold_text = VALUES(gold_text)
        """,
        (url, gold_text),
    )


def get_gold_standard(conn: mariadb.Connection, url: str) -> dict[str, Any] | None:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT w.url, w.domain, w.title, w.html_text, g.gold_text
        FROM gold_standard g
        JOIN web_resources w ON w.url = g.url
        WHERE g.url = ?
        """,
        (url,),
    )
    row = cur.fetchone()
    if row is None:
        return None
    keys = ("url", "domain", "title", "html_text", "gold_text")
    return dict(zip(keys, row))


def get_gold_standard_urls(conn: mariadb.Connection, domain: str) -> list[str]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT g.url
        FROM gold_standard g
        JOIN web_resources w ON w.url = g.url
        WHERE w.domain = ?
        ORDER BY g.url
        """,
        (domain,),
    )
    return [row[0] for row in cur.fetchall()]


def get_all_gold_standard_entries(conn: mariadb.Connection, domain: str) -> list[dict[str, Any]]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT w.url, w.domain, w.title, w.html_text, g.gold_text
        FROM gold_standard g
        JOIN web_resources w ON w.url = g.url
        WHERE w.domain = ?
        ORDER BY g.url
        """,
        (domain,),
    )
    keys = ("url", "domain", "title", "html_text", "gold_text")
    return [dict(zip(keys, row)) for row in cur.fetchall()]


def delete_gold_standard(conn: mariadb.Connection, url: str) -> None:
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM gold_standard WHERE url = ?", (url,))
    if cur.fetchone() is None:
        raise GoldStandardNotFoundError(url)
    cur.execute("DELETE FROM gold_standard WHERE url = ?", (url,))


# --------------------------------------------------------------------- #
# evaluations / llm_judgments (risultati pre-calcolati per /db_stats)
# --------------------------------------------------------------------- #
def upsert_evaluation(
    conn: mariadb.Connection,
    url: str,
    domain: str,
    precision: float,
    recall: float,
    f1: float,
    extra_metric_name: str,
    extra_metric_score: float,
) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO evaluations (url, domain, precision_value, recall_value, f1_value, extra_metric_name, extra_metric_score)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON DUPLICATE KEY UPDATE
            domain = VALUES(domain),
            precision_value = VALUES(precision_value),
            recall_value = VALUES(recall_value),
            f1_value = VALUES(f1_value),
            extra_metric_name = VALUES(extra_metric_name),
            extra_metric_score = VALUES(extra_metric_score)
        """,
        (url, domain, precision, recall, f1, extra_metric_name, extra_metric_score),
    )


def upsert_llm_judgment(
    conn: mariadb.Connection,
    url: str,
    domain: str,
    model_name: str,
    judge_score: int,
    judge_feedback: str,
) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO llm_judgments (url, domain, model_name, judge_score, judge_feedback)
        VALUES (?, ?, ?, ?, ?)
        ON DUPLICATE KEY UPDATE
            domain = VALUES(domain),
            model_name = VALUES(model_name),
            judge_score = VALUES(judge_score),
            judge_feedback = VALUES(judge_feedback)
        """,
        (url, domain, model_name, judge_score, judge_feedback),
    )


# --------------------------------------------------------------------- #
# Statistiche e schema (Obiettivo 6: /db_stats, /db_schema)
# --------------------------------------------------------------------- #
def get_db_stats(conn: mariadb.Connection) -> dict[str, Any]:
    cur = conn.cursor()

    cur.execute("SELECT domain, COUNT(*) FROM web_resources GROUP BY domain")
    web_resources = {domain: count for domain, count in cur.fetchall()}

    cur.execute(
        """
        SELECT w.domain, COUNT(*)
        FROM gold_standard g
        JOIN web_resources w ON w.url = g.url
        GROUP BY w.domain
        """
    )
    gold_standard = {domain: count for domain, count in cur.fetchall()}

    cur.execute(
        """
        SELECT domain, AVG(precision_value), AVG(recall_value), AVG(f1_value),
               MAX(extra_metric_name), AVG(extra_metric_score)
        FROM evaluations
        GROUP BY domain
        """
    )
    avg_eval: dict[str, Any] = {}
    for domain, avg_p, avg_r, avg_f1, extra_name, avg_extra in cur.fetchall():
        avg_eval[domain] = {
            "token_level_eval": {
                "precision": round(float(avg_p), 4),
                "recall": round(float(avg_r), 4),
                "f1": round(float(avg_f1), 4),
            },
            "x_eval": {
                (extra_name or "extra_metric"): round(float(avg_extra), 4) if avg_extra is not None else None,
            },
        }

    cur.execute("SELECT domain, AVG(judge_score) FROM llm_judgments GROUP BY domain")
    avg_eval_judge = {
        domain: {"judge_score": round(float(avg_score), 4)} for domain, avg_score in cur.fetchall()
    }

    return {
        "web_resources": web_resources,
        "gold_standard": gold_standard,
        "avg_eval": avg_eval,
        "avg_eval_judge": avg_eval_judge,
    }


def get_db_schema() -> dict[str, Any]:
    """
    Descrizione dello schema del DB (Obiettivo 6: GET /db_schema).
    Tenuta come dizionario "a mano" (allineato a schema.sql) invece che
    tramite introspezione INFORMATION_SCHEMA, per restituire una
    descrizione leggibile coerente col formato mostrato nella specifica.
    """
    return {
        "web_resources": {
            "url": "varchar(768), PK",
            "domain": "varchar(255)",
            "title": "varchar(2048)",
            "html_text": "longtext",
            "created_at": "datetime",
        },
        "gold_standard": {
            "url": "varchar(768), PK, FK(web_resources.url)",
            "gold_text": "longtext",
            "created_at": "datetime",
        },
        "evaluations": {
            "url": "varchar(768), PK, FK(web_resources.url)",
            "domain": "varchar(255)",
            "precision_value": "double",
            "recall_value": "double",
            "f1_value": "double",
            "extra_metric_name": "varchar(255), nullable",
            "extra_metric_score": "double, nullable",
            "created_at": "datetime",
        },
        "llm_judgments": {
            "url": "varchar(768), PK, FK(web_resources.url)",
            "domain": "varchar(255)",
            "model_name": "varchar(255)",
            "judge_score": "tinyint, CHECK 1-5",
            "judge_feedback": "text",
            "created_at": "datetime",
        },
    }

"""
Connessione a MariaDB (Obiettivo 5) tramite MariaDB Connector/Python.

Il backend puo' partire prima che il container del database sia pronto
ad accettare connessioni: wait_for_db() ritenta la connessione con un
piccolo delay, per un numero massimo di tentativi, prima di arrendersi.
"""

from __future__ import annotations

import time

import mariadb

from .. import config


def _connect() -> mariadb.Connection:
    return mariadb.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME,
        autocommit=True,
    )


def get_connection() -> mariadb.Connection:
    """Apre una nuova connessione al database."""
    return _connect()


def wait_for_db(
    max_retries: int = config.DB_CONNECT_MAX_RETRIES,
    delay_seconds: float = config.DB_CONNECT_RETRY_DELAY_SECONDS,
) -> mariadb.Connection:
    """Ritenta la connessione finche' il DB non e' pronto (o si esauriscono i tentativi)."""
    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            return _connect()
        except mariadb.Error as exc:  # pragma: no cover - dipende dal timing di Docker
            last_error = exc
            time.sleep(delay_seconds)
    raise RuntimeError(
        f"Impossibile connettersi a MariaDB dopo {max_retries} tentativi: {last_error}"
    )


def is_database_reachable() -> bool:
    """Usato da GET /status: True se il DB risponde a una query banale."""
    try:
        conn = _connect()
        try:
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.fetchall()
            return True
        finally:
            conn.close()
    except mariadb.Error:
        return False

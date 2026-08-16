
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
    return _connect()


def wait_for_db(
    max_retries: int = config.DB_CONNECT_MAX_RETRIES,
    delay_seconds: float = config.DB_CONNECT_RETRY_DELAY_SECONDS,
) -> mariadb.Connection:
    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            return _connect()
        except mariadb.Error as exc:
            last_error = exc
            time.sleep(delay_seconds)
    raise RuntimeError(
        f"Impossibile connettersi a MariaDB dopo {max_retries} tentativi: {last_error}"
    )


def is_database_reachable() -> bool:
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

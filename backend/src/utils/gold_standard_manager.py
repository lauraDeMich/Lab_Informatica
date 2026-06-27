"""
utils/gold_standard_manager.py
================================
GoldStandardManager: caricamento, validazione e persistenza del Gold Standard.

Responsabilità:
  - Leggere i file JSON in gs_data/ e validarne lo schema tramite Pydantic.
  - Inserire le entry validate nelle tabelle web_resources e gold_standard
    del database MariaDB.
  - Gestire i duplicati (INSERT IGNORE / ON DUPLICATE KEY UPDATE).
  - Fornire metodi per la lettura del GS dal DB (usati dalle API REST).

Dipendenze:
  json, pathlib, logging, mariadb, models.parse_result
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

import mariadb

from models.parse_result import GoldStandardEntry

logger = logging.getLogger(__name__)

# Path della cartella gs_data relativa alla root del progetto.
# In Docker il volume è montato su /app/gs_data.
_GS_DATA_DIR = Path(__file__).resolve().parents[2] / "gs_data"

# Mapping nome file JSON → domain string (usato per la ricerca per dominio)
_DOMAIN_FILE_MAP: dict[str, str] = {
    "wikipedia.json": "en.wikipedia.org",
    "applevis.json": "applevis.com",
    "basketball_reference.json": "basketball-reference.com",
    "ondarock.json": "ondarock.it",
}


class GoldStandardManager:
    """
    Gestisce le operazioni CRUD sul Gold Standard.

    Parameters
    ----------
    connection : mariadb.Connection
        Connessione attiva al database MariaDB.
    gs_data_dir : Path, optional
        Percorso della cartella contenente i file JSON del GS.
        Default: gs_data/ nella root del progetto.
    """

    def __init__(
        self,
        connection: mariadb.Connection,
        gs_data_dir: Optional[Path] = None,
    ) -> None:
        self._conn = connection
        self._gs_dir = gs_data_dir or _GS_DATA_DIR

    # ------------------------------------------------------------------ #
    # Caricamento e validazione da file JSON                               #
    # ------------------------------------------------------------------ #

    def load_all_from_files(self) -> list[GoldStandardEntry]:
        """
        Legge tutti i file JSON in gs_data/ e restituisce una lista
        di GoldStandardEntry validate.

        Salta silenziosamente i file non trovati (con warning).
        Lancia ValidationError se lo schema di una entry non è valido.
        """
        entries: list[GoldStandardEntry] = []

        for filename in _DOMAIN_FILE_MAP:
            filepath = self._gs_dir / filename
            if not filepath.exists():
                logger.warning("File GS non trovato: %s", filepath)
                continue

            domain_entries = self._load_file(filepath)
            entries.extend(domain_entries)
            logger.info(
                "Caricate %d entry da %s", len(domain_entries), filename
            )

        logger.info("Totale entry GS caricate: %d", len(entries))
        return entries

    def _load_file(self, filepath: Path) -> list[GoldStandardEntry]:
        """
        Legge e valida un singolo file JSON del Gold Standard.

        Il file deve contenere una lista JSON di oggetti conformi
        allo schema GoldStandardEntry.
        """
        with filepath.open(encoding="utf-8") as f:
            raw_data = json.load(f)

        if not isinstance(raw_data, list):
            raise ValueError(
                f"Il file {filepath.name} deve contenere una lista JSON, "
                f"trovato: {type(raw_data).__name__}"
            )

        validated: list[GoldStandardEntry] = []
        for i, item in enumerate(raw_data):
            try:
                entry = GoldStandardEntry(**item)
                validated.append(entry)
            except Exception as exc:
                logger.error(
                    "Entry %d in %s non valida: %s", i, filepath.name, exc
                )
                raise ValueError(
                    f"Entry {i} in {filepath.name} non valida: {exc}"
                ) from exc

        return validated

    # ------------------------------------------------------------------ #
    # Inserimento nel DB                                                   #
    # ------------------------------------------------------------------ #

    def persist_all(self, entries: list[GoldStandardEntry]) -> int:
        """
        Inserisce tutte le entry nel DB.
        Usa INSERT IGNORE per non duplicare le entry già presenti.

        Returns
        -------
        int
            Numero di entry effettivamente inserite (nuove).
        """
        inserted = 0
        cursor = self._conn.cursor()

        try:
            for entry in entries:
                # 1. Inserisce nella tabella web_resources
                cursor.execute(
                    """
                    INSERT IGNORE INTO web_resources
                        (url, domain, title, html_text, created_at)
                    VALUES (?, ?, ?, ?, NOW())
                    """,
                    (entry.url, entry.domain, entry.title, entry.html_text),
                )
                wr_inserted = cursor.rowcount

                # 2. Inserisce nella tabella gold_standard
                cursor.execute(
                    """
                    INSERT IGNORE INTO gold_standard
                        (url, gold_text, created_at)
                    VALUES (?, ?, NOW())
                    """,
                    (entry.url, entry.gold_text),
                )
                gs_inserted = cursor.rowcount

                if wr_inserted > 0 or gs_inserted > 0:
                    inserted += 1
                    logger.debug("Inserita entry GS: %s", entry.url)

            self._conn.commit()
            logger.info("Persistite %d nuove entry GS nel DB", inserted)

        except Exception as exc:
            self._conn.rollback()
            logger.error("Errore persistenza GS: %s", exc)
            raise
        finally:
            cursor.close()

        return inserted

    def init_from_files(self) -> int:
        """
        Metodo di convenienza per l'inizializzazione del DB:
        carica tutti i file JSON e li persiste nel DB.

        Returns
        -------
        int
            Numero di nuove entry inserite.
        """
        entries = self.load_all_from_files()
        if not entries:
            logger.warning("Nessuna entry GS trovata nei file JSON.")
            return 0
        return self.persist_all(entries)

    # ------------------------------------------------------------------ #
    # Lettura dal DB (usata dalle API REST)                                #
    # ------------------------------------------------------------------ #

    def get_entry(self, url: str) -> Optional[GoldStandardEntry]:
        """
        Recupera una entry del GS dal DB dato l'URL.

        Returns
        -------
        GoldStandardEntry | None
        """
        cursor = self._conn.cursor()
        try:
            cursor.execute(
                """
                SELECT wr.url, wr.domain, wr.title, wr.html_text, gs.gold_text
                FROM web_resources wr
                JOIN gold_standard gs ON wr.url = gs.url
                WHERE wr.url = ?
                """,
                (url,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return GoldStandardEntry(
                url=row[0],
                domain=row[1],
                title=row[2],
                html_text=row[3],
                gold_text=row[4],
            )
        finally:
            cursor.close()

    def get_urls_by_domain(self, domain: str) -> list[str]:
        """
        Restituisce tutti gli URL del GS per un dato dominio.
        """
        cursor = self._conn.cursor()
        try:
            cursor.execute(
                """
                SELECT wr.url
                FROM web_resources wr
                JOIN gold_standard gs ON wr.url = gs.url
                WHERE wr.domain = ?
                ORDER BY wr.created_at
                """,
                (domain,),
            )
            return [row[0] for row in cursor.fetchall()]
        finally:
            cursor.close()

    def add_web_resource(
        self, url: str, html_text: str, domain: str = "", title: str = ""
    ) -> None:
        """
        Aggiunge una riga in web_resources.
        Lancia ValueError se l'URL esiste già.
        """
        cursor = self._conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO web_resources (url, domain, title, html_text, created_at)
                VALUES (?, ?, ?, ?, NOW())
                """,
                (url, domain, title, html_text),
            )
            self._conn.commit()
        except mariadb.IntegrityError as exc:
            self._conn.rollback()
            raise ValueError(f"URL già presente in web_resources: {url}") from exc
        finally:
            cursor.close()

    def add_gold_standard(self, url: str, gold_text: str) -> None:
        """
        Aggiunge una riga in gold_standard.
        Richiede che l'URL esista già in web_resources (FK).
        Lancia ValueError se l'URL non esiste o è già nel GS.
        """
        cursor = self._conn.cursor()
        try:
            # Verifica che web_resource esista
            cursor.execute(
                "SELECT 1 FROM web_resources WHERE url = ?", (url,)
            )
            if not cursor.fetchone():
                raise ValueError(
                    f"URL non presente in web_resources: {url}. "
                    "Usare POST /add_web_resource prima."
                )

            cursor.execute(
                """
                INSERT INTO gold_standard (url, gold_text, created_at)
                VALUES (?, ?, NOW())
                """,
                (url, gold_text),
            )
            self._conn.commit()
        except mariadb.IntegrityError as exc:
            self._conn.rollback()
            raise ValueError(f"URL già presente in gold_standard: {url}") from exc
        finally:
            cursor.close()

    def delete_web_resource(self, url: str) -> None:
        """
        Elimina una riga da web_resources.
        La DELETE CASCADE rimuove automaticamente la entry in gold_standard.
        Lancia ValueError se l'URL non esiste.
        """
        cursor = self._conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM web_resources WHERE url = ?", (url,)
            )
            if cursor.rowcount == 0:
                raise ValueError(f"URL non trovato in web_resources: {url}")
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
        finally:
            cursor.close()

    def delete_gold_standard(self, url: str) -> None:
        """
        Elimina solo la riga da gold_standard, lasciando intatta web_resources.
        Lancia ValueError se l'URL non è nel GS.
        """
        cursor = self._conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM gold_standard WHERE url = ?", (url,)
            )
            if cursor.rowcount == 0:
                raise ValueError(f"URL non trovato in gold_standard: {url}")
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
        finally:
            cursor.close()

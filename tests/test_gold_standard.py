"""
Test per l'Obiettivo 2 (Gold Standard).

Due livelli di verifica:
1. test_schema_validation_static: NON richiede il file GS, valida solo che
   il modello Pydantic GoldStandardEntry accetti/rifiuti correttamente i
   dati (funziona sempre, anche prima di aver costruito il GS).
2. test_gold_standard_file_*: richiedono che
   data/gold_standard/it_wikipedia_org.json esista già (generato con
   scripts/build_gold_standard.py e poi completato A MANO con i gold_text).
   Se il file non esiste ancora, questi test vengono saltati con un
   messaggio esplicativo invece di fallire "a sorpresa".
"""

import json
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic import ValidationError

from models.schema import GoldStandardEntry

GS_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "gold_standard"
    / "it_wikipedia_org.json"
)

MIN_ENTRIES = 10
EXPECTED_DOMAIN = "it.wikipedia.org"


def test_schema_validation_static():
    valid_entry = {
        "url": "https://it.wikipedia.org/wiki/Roma",
        "domain": "it.wikipedia.org",
        "title": "Roma",
        "html_text": "<html>...</html>",
        "gold_text": "Roma è la capitale d'Italia...",
    }
    entry = GoldStandardEntry(**valid_entry)
    assert entry.domain == "it.wikipedia.org"
    print("OK: GoldStandardEntry valida accettata correttamente")

    invalid_entry = dict(valid_entry)
    del invalid_entry["gold_text"]
    try:
        GoldStandardEntry(**invalid_entry)
        raise AssertionError("Doveva fallire per campo 'gold_text' mancante")
    except ValidationError:
        print("OK: GoldStandardEntry senza 'gold_text' correttamente rifiutata")


def _load_gs_or_skip():
    if not GS_PATH.exists():
        print(
            f"SALTATO: {GS_PATH} non trovato.\n"
            "  -> Esegui prima 'python scripts/build_gold_standard.py' "
            "(in locale, con rete libera) e poi compila i campi 'gold_text' a mano."
        )
        return None
    with GS_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def test_gold_standard_file_structure():
    data = _load_gs_or_skip()
    if data is None:
        return

    assert isinstance(data, list), "Il file GS deve contenere una lista di entry"
    assert len(data) >= MIN_ENTRIES, (
        f"Servono almeno {MIN_ENTRIES} entry, trovate {len(data)}"
    )

    for raw_entry in data:
        entry = GoldStandardEntry(**raw_entry)  # valida schema + campi obbligatori
        assert entry.domain == EXPECTED_DOMAIN

    print(f"OK: {len(data)} entry, tutte conformi allo schema GoldStandardEntry")


def test_gold_standard_no_home_page_and_unique_urls():
    data = _load_gs_or_skip()
    if data is None:
        return

    urls = [entry["url"] for entry in data]
    assert len(urls) == len(set(urls)), "Ci sono URL duplicati nel Gold Standard"

    for url in urls:
        path = urlparse(url).path.strip("/")
        assert path not in ("", "wiki"), f"'{url}' sembra una home page, non consentita"

    print("OK: nessun URL duplicato o home page nel Gold Standard")


def test_gold_standard_manual_fields_not_empty():
    data = _load_gs_or_skip()
    if data is None:
        return

    empty_gold = [e["url"] for e in data if not e.get("gold_text", "").strip()]
    empty_title = [e["url"] for e in data if not e.get("title", "").strip()]

    assert not empty_title, f"Titoli mancanti per: {empty_title}"
    assert not empty_gold, (
        f"'gold_text' ANCORA VUOTO per {len(empty_gold)} pagine (da compilare a mano): {empty_gold}"
    )
    print("OK: tutti i 'gold_text' risultano compilati")


if __name__ == "__main__":
    test_schema_validation_static()
    test_gold_standard_file_structure()
    test_gold_standard_no_home_page_and_unique_urls()
    test_gold_standard_manual_fields_not_empty()
    print("\nTutti i test del Gold Standard passati (o saltati se il file non esiste ancora).")

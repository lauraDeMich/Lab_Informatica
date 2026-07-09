"""
Script di supporto per inserire i 'gold_text' (scritti a mano in file .txt
semplici) dentro data/gold_standard/it_wikipedia_org.json, SENZA dover
modificare il JSON a mano (evita di rompere la sintassi con virgolette,
a-capo, ecc.).

Come si usa:
1. Esegui prima 'python scripts/build_gold_standard.py': oltre a creare lo
   scheletro JSON (html_text/title compilati, gold_text vuoto), crea anche
   un file .txt VUOTO già col nome giusto per ogni pagina, dentro
   data/gold_standard/manual_texts/ (NON serve calcolare nulla a mano).
2. Apri ogni file .txt in quella cartella e incolla dentro SOLO il testo
   copiato dal browser (titolo + corpo dell'articolo, es. con la modalità
   Lettura di Safari/Firefox), poi salva.
3. Esegui questo script:
     python scripts/fill_gold_text.py
   Per ogni file .txt trovato, il contenuto viene letto e scritto nel
   campo "gold_text" della entry corrispondente, con json.dump che si
   occupa automaticamente di ogni escaping necessario (virgolette,
   a-capo, caratteri speciali): non c'è possibilità di rompere il JSON.
4. Verifica con:
     python tests/test_gold_standard.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

GS_JSON = Path(__file__).resolve().parent.parent / "data" / "gold_standard" / "it_wikipedia_org.json"
MANUAL_TEXTS_DIR = Path(__file__).resolve().parent.parent / "data" / "gold_standard" / "manual_texts"


def slugify(url: str) -> str:
    """Stessa funzione usata in build_gold_standard.py, per coerenza dei nomi file."""
    name = url.rstrip("/").rsplit("/", 1)[-1]
    return re.sub(r"[^A-Za-z0-9_-]", "_", name) or "page"


def main() -> None:
    if not GS_JSON.exists():
        print(
            f"ERRORE: {GS_JSON} non trovato.\n"
            "Esegui prima: python scripts/build_gold_standard.py"
        )
        return

    if not MANUAL_TEXTS_DIR.exists():
        print(
            f"ERRORE: {MANUAL_TEXTS_DIR} non trovata.\n"
            "Creala e mettici dentro un file <slug>.txt per ogni pagina "
            "(vedi istruzioni in cima a questo script)."
        )
        return

    with GS_JSON.open("r", encoding="utf-8") as f:
        entries = json.load(f)

    updated = 0
    missing = []

    for entry in entries:
        slug = slugify(entry["url"])
        txt_path = MANUAL_TEXTS_DIR / f"{slug}.txt"
        if txt_path.exists():
            text = txt_path.read_text(encoding="utf-8").strip()
            if text:
                entry["gold_text"] = text
                updated += 1
                print(f"OK   {entry['url']}  <-  {txt_path.name}")
            else:
                missing.append(entry["url"])
                print(f"VUOTO  {txt_path.name} è presente ma vuoto")
        else:
            missing.append(entry["url"])
            print(f"MANCA  nessun file trovato per {entry['url']} (atteso: {txt_path.name})")

    with GS_JSON.open("w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    print(f"\nAggiornate {updated}/{len(entries)} entry.")
    if missing:
        print(f"Ancora da fare per {len(missing)} pagine:")
        for url in missing:
            print(f"  - {url}")
    else:
        print("Tutte le entry hanno un gold_text! Esegui ora: python tests/test_gold_standard.py")


if __name__ == "__main__":
    main()

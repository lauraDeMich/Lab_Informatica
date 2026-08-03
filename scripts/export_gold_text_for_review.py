"""
Esporta i 'gold_text' attualmente presenti in gs_data/basketball_reference_gs.json
e gs_data/ondarock_it_gs.json in file .txt separati, uno per pagina, dentro
data/manual_texts/<dominio>/ — stesso schema già usato per Wikipedia
(vedi scripts/build_gold_standard.py e scripts/fill_gold_text.py).

A differenza del flusso Wikipedia (file .txt VUOTI da riempire da zero), qui
i file vengono scritti GIA' PRE-COMPILATI con la bozza attuale (estratta
automaticamente da uno script, non copiata a mano): l'obiettivo non e'
riscrivere tutto, ma APRIRE ogni pagina reale nel browser e CORREGGERE il
file .txt corrispondente dove serve (rumore residuo, testo tagliato male,
paragrafi mancanti).

Ogni cartella di dominio contiene anche un file _INDEX.txt con l'elenco
"nome_file.txt -> URL", per sapere quale pagina aprire nel browser per
ciascun file.

Uso:
    python scripts/export_gold_text_for_review.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GS_DIR = ROOT / "gs_data"
MANUAL_TEXTS_DIR = ROOT / "data" / "manual_texts"

TARGETS = [
    ("basketball_reference_gs.json", "basketball_reference"),
    ("ondarock_it_gs.json", "ondarock"),
]


def slugify(url: str) -> str:
    """Stessa funzione usata in build_gold_standard.py/fill_gold_text.py, per coerenza dei nomi file."""
    name = url.rstrip("/").rsplit("/", 1)[-1]
    return re.sub(r"[^A-Za-z0-9_-]", "_", name) or "page"


def export_domain(gs_filename: str, subdir_name: str) -> None:
    gs_path = GS_DIR / gs_filename
    if not gs_path.exists():
        print(f"SALTATO: {gs_path} non trovato.")
        return

    with gs_path.open("r", encoding="utf-8") as f:
        entries = json.load(f)

    out_dir = MANUAL_TEXTS_DIR / subdir_name
    out_dir.mkdir(parents=True, exist_ok=True)

    index_lines = []
    for entry in entries:
        slug = slugify(entry["url"])
        txt_path = out_dir / f"{slug}.txt"
        txt_path.write_text(entry.get("gold_text", ""), encoding="utf-8")
        index_lines.append(f"{slug}.txt  ->  {entry['url']}")

    index_path = out_dir / "_INDEX.txt"
    index_path.write_text("\n".join(index_lines) + "\n", encoding="utf-8")

    print(f"OK  {gs_filename}: {len(entries)} file scritti in {out_dir}")


def main() -> None:
    for gs_filename, subdir_name in TARGETS:
        export_domain(gs_filename, subdir_name)
    print("\nApri i file dentro data/manual_texts/<dominio>/, confrontali con la")
    print("pagina reale (vedi _INDEX.txt per l'URL) e correggili dove serve.")
    print("Quando hai finito: python scripts/apply_reviewed_gold_text.py")


if __name__ == "__main__":
    main()

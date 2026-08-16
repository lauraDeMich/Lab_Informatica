
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
    name = url.rstrip("/").rsplit("/", 1)[-1]
    return re.sub(r"[^A-Za-z0-9_-]", "_", name) or "page"


def apply_domain(gs_filename: str, subdir_name: str) -> None:
    gs_path = GS_DIR / gs_filename
    txt_dir = MANUAL_TEXTS_DIR / subdir_name

    if not gs_path.exists():
        print(f"SALTATO: {gs_path} non trovato.")
        return
    if not txt_dir.exists():
        print(f"SALTATO: {txt_dir} non trovata (esegui prima export_gold_text_for_review.py).")
        return

    with gs_path.open("r", encoding="utf-8") as f:
        entries = json.load(f)

    updated = 0
    missing = []

    for entry in entries:
        slug = slugify(entry["url"])
        txt_path = txt_dir / f"{slug}.txt"
        if not txt_path.exists():
            missing.append(entry["url"])
            print(f"MANCA  nessun file trovato per {entry['url']} (atteso: {txt_path.name})")
            continue

        text = txt_path.read_text(encoding="utf-8").strip()
        if not text:
            missing.append(entry["url"])
            print(f"VUOTO  {txt_path.name} è presente ma vuoto")
            continue

        if text != entry.get("gold_text", "").strip():
            updated += 1
            print(f"MODIFICATO  {entry['url']}")
        entry["gold_text"] = text

    with gs_path.open("w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    print(f"\n{gs_filename}: {updated}/{len(entries)} gold_text modificati rispetto alla bozza.")
    if missing:
        print(f"Attenzione, {len(missing)} pagine senza testo valido:")
        for url in missing:
            print(f"  - {url}")


def main() -> None:
    for gs_filename, subdir_name in TARGETS:
        apply_domain(gs_filename, subdir_name)
        print()


if __name__ == "__main__":
    main()

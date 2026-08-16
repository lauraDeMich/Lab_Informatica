
from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.src.parsers.wikipedia_it_parser import WikipediaItParser


CANDIDATE_URLS = [
    "https://it.wikipedia.org/wiki/Super_Mario",                     
    "https://it.wikipedia.org/wiki/Amazon",                          
    "https://it.wikipedia.org/wiki/Tavola_periodica_degli_elementi", 
    "https://it.wikipedia.org/wiki/Torre_Eiffel",                   
    "https://it.wikipedia.org/wiki/Artemis_II",                     
    "https://it.wikipedia.org/wiki/Facebook",                        
    "https://it.wikipedia.org/wiki/Ferrero_(azienda)",                
    "https://it.wikipedia.org/wiki/McDonald%27s",                   
    "https://it.wikipedia.org/wiki/Python",                          
    "https://it.wikipedia.org/wiki/Caparezza",                       
]

OUTPUT_JSON = Path(__file__).resolve().parent.parent / "gs_data" / "it_wikipedia_org_gs.json"
RAW_HTML_DIR = Path(__file__).resolve().parent.parent / "data" / "raw_html" / "wikipedia_it"
MANUAL_TEXTS_DIR = Path(__file__).resolve().parent.parent / "data" / "manual_texts"


def slugify(url: str) -> str:
    """Ricava un nome file leggibile dall'ultima parte dell'URL."""
    name = url.rstrip("/").rsplit("/", 1)[-1]
    return re.sub(r"[^A-Za-z0-9_-]", "_", name) or "page"


def extract_title_from_html(html: str) -> str:
    """Estrae il contenuto di <title> e rimuove il suffisso ' - Wikipedia'."""
    match = re.search(r"<title>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    raw_title = match.group(1).strip()
    return raw_title.replace(" - Wikipedia", "").strip()


def load_existing_entries() -> dict[str, dict]:
    """Carica il JSON esistente (se presente) indicizzato per URL, per non perdere i gold_text già compilati a mano."""
    if not OUTPUT_JSON.exists():
        return {}
    with OUTPUT_JSON.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return {entry["url"]: entry for entry in data}


async def build() -> None:
    RAW_HTML_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    MANUAL_TEXTS_DIR.mkdir(parents=True, exist_ok=True)

    parser = WikipediaItParser()
    existing = load_existing_entries()
    entries: list[dict] = []

    for url in CANDIDATE_URLS:
        print(f"Scarico: {url}")
        try:
            html = await parser.fetch_raw_html(url)
        except Exception as exc:  # noqa: BLE001
            print(f"  ! ERRORE nel download di {url}: {exc}")
            continue

        slug = slugify(url)
        html_path = RAW_HTML_DIR / f"{slug}.html"
        html_path.write_text(html, encoding="utf-8")

        title = extract_title_from_html(html)

        
        previous_gold_text = existing.get(url, {}).get("gold_text", "")

        entries.append(
            {
                "url": url,
                "domain": parser.domain,
                "title": title,
                "html_text": html,
                # DA COMPILARE A MANO (vedi README): se già presente da un run precedente, viene mantenuto.
                "gold_text": previous_gold_text,
            }
        )
        print(f"  OK  -> title='{title}'  (html salvato in {html_path.relative_to(Path.cwd())})")

       
        txt_placeholder = MANUAL_TEXTS_DIR / f"{slug}.txt"
        if not txt_placeholder.exists():
            txt_placeholder.write_text("", encoding="utf-8")

    with OUTPUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    n_missing_gold = sum(1 for e in entries if not e["gold_text"].strip())
    print(f"\nScheletro Gold Standard scritto in: {OUTPUT_JSON}")
    print(f"Entry totali: {len(entries)}")
    print(f"Entry con 'gold_text' ANCORA DA COMPILARE A MANO: {n_missing_gold}")
    print(f"\nApri e riempi i file vuoti dentro: {MANUAL_TEXTS_DIR}")
    print("(uno per pagina, nome file già corretto: NON serve calcolarlo a mano)")
    print("Poi esegui: python scripts/fill_gold_text.py")


if __name__ == "__main__":
    asyncio.run(build())

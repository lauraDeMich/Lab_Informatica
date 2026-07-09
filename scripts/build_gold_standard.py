"""
Script di supporto per costruire lo SCHELETRO del Gold Standard (Obiettivo 2)
per il dominio it.wikipedia.org.

Cosa fa in automatico:
- Scarica l'HTML grezzo di ogni URL della lista CANDIDATE_URLS (tramite
  WikipediaItParser.fetch_raw_html, quindi con lo stesso browser/Crawl4AI
  usato per l'Obiettivo 1).
- Estrae il <title> dall'HTML e rimuove il suffisso " - Wikipedia".
- Scrive/aggiorna data/gold_standard/it_wikipedia_org.json con una entry
  per ogni URL: url, domain, title, html_text (compilati), gold_text (LASCIATO
  VUOTO, "" -> da riempire A MANO, vedi istruzioni nel README).
- Salva anche una copia dell'HTML grezzo in data/raw_html/wikipedia_it/
  (utile come backup e per debug, NON viene versionata su Git).

Cosa NON fa (va fatto a mano, vedi README):
- Riempire "gold_text": bisogna aprire ogni URL nel browser e copiare
  SOLO il testo informativo (titolo + corpo dell'articolo), escludendo
  menu di navigazione, sidebar, footer, box "Voci correlate" ecc.

Uso:
    python scripts/build_gold_standard.py

NOTA BENE: questo script richiede una connessione di rete libera verso
it.wikipedia.org e richiede che 'crawl4ai-setup' sia già stato eseguito
(scarica Chromium). Va quindi lanciato sulla vostra macchina locale,
DENTRO il virtualenv del progetto (vedi README, sezione "Setup"), non in
ambienti sandbox privi di accesso a Internet.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parsers.wikipedia_it_parser import WikipediaItParser

# ---------------------------------------------------------------------- #
# 1) LISTA DEGLI URL CANDIDATI PER IL GOLD STANDARD DI it.wikipedia.org
#
# Requisito dell'Obiettivo 2: almeno 10 URL rappresentativi (pagine di
# tipo diverso, con contenuti vari, NO home page). Qui ne mettiamo 10
# scelti per coprire categorie eterogenee (videogiochi, aziende, scienza,
# monumenti, spazio, informatica, musica) così da avere un GS di buona
# qualità.
#
# Sentitevi liberi di modificare/estendere questa lista: potete anche
# usare l'operatore "site:it.wikipedia.org" su Google per trovare altre
# pagine interessanti (vedi slide dell'Obiettivo 2).
# ---------------------------------------------------------------------- #
CANDIDATE_URLS = [
    "https://it.wikipedia.org/wiki/Super_Mario",                     # videogiochi
    "https://it.wikipedia.org/wiki/Amazon",                          # azienda / tecnologia
    "https://it.wikipedia.org/wiki/Tavola_periodica_degli_elementi", # scienza / chimica
    "https://it.wikipedia.org/wiki/Torre_Eiffel",                    # monumento / luogo
    "https://it.wikipedia.org/wiki/Artemis_II",                      # spazio / missione
    "https://it.wikipedia.org/wiki/Facebook",                        # azienda / tecnologia
    "https://it.wikipedia.org/wiki/Ferrero_(azienda)",                # azienda
    "https://it.wikipedia.org/wiki/McDonald%27s",                    # azienda
    "https://it.wikipedia.org/wiki/Python",                          # informatica / linguaggio di programmazione
    "https://it.wikipedia.org/wiki/Caparezza",                       # persona / musica
]

OUTPUT_JSON = Path(__file__).resolve().parent.parent / "data" / "gold_standard" / "it_wikipedia_org.json"
RAW_HTML_DIR = Path(__file__).resolve().parent.parent / "data" / "raw_html" / "wikipedia_it"
MANUAL_TEXTS_DIR = Path(__file__).resolve().parent.parent / "data" / "gold_standard" / "manual_texts"


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

        # Se l'entry esiste già ed è stata compilata a mano, mantieni il gold_text.
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

        # Crea (se non esiste già) un file .txt vuoto col nome corretto, pronto
        # per essere aperto e riempito a mano con il testo copiato dal browser.
        # Non lo sovrascrive mai se esiste già, per non perdere lavoro manuale.
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

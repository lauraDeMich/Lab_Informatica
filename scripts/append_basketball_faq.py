"""
Aggiunge alla gold_text delle pagine giocatore di
gs_data/basketball_reference_gs.json il contenuto della sezione
"Frequently Asked Questions" (div id="div_faq"), presente solo sulle
pagine giocatore (non su squadre/campionato) e non ancora coperta dal
Gold Standard. Il parser (vedi backend/src/parsers/basketball_reference_parser.py)
e' stato aggiornato per includere lo stesso blocco nello scope.

Scrive una bozza automatica: va rivista a mano come il resto del Gold
Standard (vedi scripts/export_gold_text_for_review.py).

Uso:
    python scripts/append_basketball_faq.py
"""

from __future__ import annotations

import json
from pathlib import Path

from bs4 import BeautifulSoup

GS_PATH = Path(__file__).resolve().parent.parent / "gs_data" / "basketball_reference_gs.json"


def extract_faq_text(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    div_faq = soup.find(id="div_faq")
    if not div_faq:
        return None

    # Struttura fissa: ogni <h3> (domanda) e' seguito da un SOLO <p>
    # (risposta); in coda al blocco c'e' anche uno <script type=
    # "application/ld+json"> con lo stesso contenuto in JSON per la SEO,
    # che va ignorato esplicitamente (non e' testo per un lettore umano).
    parts = []
    for h3 in div_faq.find_all("h3"):
        question = h3.get_text(strip=True)
        p = h3.find_next_sibling("p")
        answer = p.get_text(separator=" ", strip=True) if p else ""
        if question and answer:
            parts.append(f"{question}\n{answer}")

    if not parts:
        return None
    return "Domande frequenti:\n\n" + "\n\n".join(parts)


def main() -> None:
    with GS_PATH.open("r", encoding="utf-8") as f:
        entries = json.load(f)

    updated = 0
    for entry in entries:
        faq_text = extract_faq_text(entry["html_text"])
        if faq_text is None:
            print(f"SALTATO (nessuna FAQ): {entry['url']}")
            continue
        entry["gold_text"] = entry["gold_text"].rstrip() + "\n\n" + faq_text
        updated += 1
        print(f"AGGIORNATO (+{len(faq_text)} char FAQ): {entry['url']}")

    with GS_PATH.open("w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    print(f"\nTotale aggiornati: {updated}/{len(entries)}")


if __name__ == "__main__":
    main()

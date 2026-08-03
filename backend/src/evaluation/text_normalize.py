"""
Normalizzazione del testo prima della valutazione (Obiettivo 3).

L'output dei parser e' in Markdown, mentre il Gold Standard e' testo
semplice: per confrontarli in modo equo bisogna rimuovere markup e link
da entrambi. Implementazione suggerita dalla specifica del progetto
(mistune -> HTML -> BeautifulSoup -> testo).
"""

from __future__ import annotations

import re

import mistune
from bs4 import BeautifulSoup


def remove_markdown(md: str) -> str:
    """
    Rimuove il Markdown da una stringa, restituendo solo il testo pulito.
    Usa mistune per convertire il Markdown in HTML, poi BeautifulSoup per
    estrarre solo il testo (funziona anche se l'input non e' markdown,
    es. e' gia' testo semplice come il Gold Standard).
    """
    html = mistune.html(md or "")
    soup = BeautifulSoup(html, "html.parser")
    # rimuove i tag lasciando il testo esattamente in-place (nessun separatore aggiunto)
    for tag in soup.find_all(True):
        tag.unwrap()
    text = re.sub(r"[ \t]+", " ", str(soup))  # collassa spazi orizzontali (non \n)
    text = re.sub(r"\n+", "\n", text)  # collassa nuove linee multiple in una sola
    return text.strip()

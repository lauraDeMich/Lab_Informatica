"""
Parser per il dominio www.ondarock.it (webzine musicale italiana).

Il sito usa lo stesso tema WordPress per tutte le sezioni editoriali
(recensioni, interviste, monografie): ogni articolo ha un corpo testuale
racchiuso in un unico blocco ".main_text" (paragrafi, blockquote per le
citazioni di testi/liriche, heading interni nelle monografie piu' lunghe),
seguito da rumore di pagina (data in ".data_recensione", pulsanti di
condivisione in ".social_share"). Verificato sia su una recensione album,
sia su un'intervista, sia su una monografia: la struttura ".main_text" e'
condivisa da tutte e tre le sezioni.

La pagina "/news" (elenco delle notizie, non un singolo articolo) non ha
".main_text": il contenuto informativo qui e' la lista stessa, ripetuta in
tanti blocchi ".news_content" (data + titolo di ogni notizia). La includiamo
nello scope per lo stesso motivo di ".main_text": e' il vero contenuto
testuale della pagina, non boilerplate. CSS multi-selector: su un articolo
singolo ".news_content" non trova nulla e ".main_text" resta valido, e
viceversa sulla pagina elenco.

NOTA sulle esclusioni: come per AppleVis e Basketball-Reference, tutto va
in excluded_selector (mai in excluded_tags insieme allo stesso elemento,
altrimenti Crawl4AI puo' azzerare l'output), e non usiamo
remove_overlay_elements=True su HTML "raw" non renderizzato.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup
from crawl4ai import CrawlerRunConfig

from .base import BaseDomainParser


class OndaRockParser(BaseDomainParser):
    domain = "www.ondarock.it"

    def build_crawler_run_config(self) -> CrawlerRunConfig:
        return CrawlerRunConfig(
            css_selector=".main_text, .news_content",
            excluded_selector=", ".join(
                [
                    "script",
                    "style",
                    "form",
                    "img",
                    "figure",
                    # Pulsanti "Condividi su" (social sharing)
                    ".social_share",
                    # Data della recensione, ripetuta separatamente dal testo
                    ".data_recensione",
                    # Widget "Indice dei contenuti" (sommario a comparsa nelle monografie)
                    ".index-container",
                ]
            ),
            word_count_threshold=1,
            exclude_external_links=False,
            exclude_social_media_links=True,
            wait_until="domcontentloaded",
            page_timeout=30000,
        )

    def extract_title(self, result, url: str) -> str:
        html = getattr(result, "html", "") or ""
        if html:
            soup = BeautifulSoup(html, "html.parser")
            h1 = soup.find("h1")
            if h1:
                text = h1.get_text(separator=" ", strip=True)
                if text:
                    return text

        title = super().extract_title(result, url)
        if " :: " in title:
            return title.split(" :: ")[0].strip()
        return title

    def postprocess_markdown(self, raw_markdown: str) -> str:
        text = super().postprocess_markdown(raw_markdown)

        # Dateline isolata a fine intervista, es. "_(14 giugno 2026)_" o "(Milano, 27 ottobre 2006)"
        text = re.sub(r"^\s*_?\([^()\n]*\d{4}\)_?\s*$", "", text, flags=re.MULTILINE)
        # Righe che contengono solo un URL nudo
        text = re.sub(r"^\s*https?://\S+\s*$", "", text, flags=re.MULTILINE)
        # Normalizza righe vuote multiple lasciate dalle rimozioni sopra
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()

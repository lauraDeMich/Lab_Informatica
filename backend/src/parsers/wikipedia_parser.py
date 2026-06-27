"""
parsers/wikipedia_parser.py
===========================
Parser dedicato per en.wikipedia.org.

Responsabilità:
  - Configurare Crawl4AI per estrarre esclusivamente il corpo testuale
    degli articoli Wikipedia in inglese.
  - Escludere: TOC, infobox di navigazione, categorie, sezione "See also",
    "External links", "References", note a piè di pagina, banner di avviso,
    toolbar di modifica, sidebar.
  - Post-processare il Markdown rimuovendo artefatti MediaWiki residui.
  - Estrarre il titolo dall'elemento <h1 id="firstHeading">.

Dipendenze:
  re, bs4 (BeautifulSoup), crawl4ai, parsers.base_parser
"""

from __future__ import annotations

import re
from crawl4ai import CacheMode
from bs4 import BeautifulSoup
from crawl4ai import CrawlerRunConfig
#from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

from parsers.base_parser import BaseParser


class WikipediaParser(BaseParser):
    """
    Parser per articoli di en.wikipedia.org.

    Strategia di estrazione:
      1. Crawl4AI con css_selector="#mw-content-text" per limitare
         il contenuto al corpo dell'articolo.
      2. excluded_selector rimuove TOC, infobox nav, categorie, footer.
      3. Post-processing rimuove artefatti Markdown residui (numerazione
         di note, link di modifica "[edit]", intestazioni ridondanti).
    """

    @property
    def supported_domains(self) -> list[str]:
        return ["en.wikipedia.org"]

    def _build_crawler_config(self) -> CrawlerRunConfig:
        """
        CrawlerRunConfig ottimizzata per Wikipedia EN.

        Scelte progettuali:
          - css_selector="#mw-content-text" → solo il corpo articolo.
          - excluded_selector elimina: TOC, infobox di navigazione,
            sezioni "References" / "Notes" / "External links" / "See also",
            categorie, messaggi di avviso, toolbar.
          - word_count_threshold=10 filtra blocchi troppo brevi.
          - PruningContentFilter per scartare blocchi a bassa densità.
        """
        md_generator = DefaultMarkdownGenerator(
            options={
                "ignore_links": False,
                "skip_internal_links": True,
                "include_sup_sub": False,
                "body_width": 0,  # nessun word-wrap
            }
        )

        #content_filter = PruningContentFilter(
           # threshold=0.40,
            #threshold_type="fixed",
            #min_word_threshold=10,
        #)

        return CrawlerRunConfig(
            css_selector="#mw-content-text",
            excluded_selector=",".join([
                "#toc", ".toc", ".tocnumber",
                ".navbox", ".navbox-inner", ".navbox-list", ".portal-bar", ".sistersitebox",
                "#References", "#Notes", "#External_links", "#See_also",
                "#Further_reading", "#Bibliography", ".reflist", ".references",
                "#catlinks", ".catlinks",
                ".ambox", ".cmbox", ".ombox", ".tmbox", ".fmbox", ".dmbox",
                ".mw-editsection", ".mw-editsection-bracket",
                ".thumbcaption",
                "#mw-navigation", "#footer", "#p-tb", ".mw-footer",
                "#coordinates", ".IPA", ".hatnote",
            ]),
            word_count_threshold=10,
            markdown_generator=md_generator,   # ← questa è la riga critica
            cache_mode=CacheMode.BYPASS,
            process_iframes=False,
            remove_overlay_elements=True,
            exclude_external_links=False,
            exclude_social_media_links=True,
        )

    def _extract_title(self, html: str, fallback_title: str) -> str:
        """
        Estrae il titolo dall'elemento specifico di MediaWiki:
          <h1 id="firstHeading" class="firstHeading">…</h1>
        """
        try:
            soup = BeautifulSoup(html, "html.parser")
            heading = soup.find("h1", id="firstHeading")
            if heading:
                return heading.get_text(separator=" ", strip=True)
            # Secondo tentativo: <title> tag standard
            title_tag = soup.find("title")
            if title_tag:
                raw = title_tag.get_text(strip=True)
                # Wikipedia usa il formato "Titolo - Wikipedia"
                return raw.split(" - Wikipedia")[0].strip()
        except Exception:
            pass
        return fallback_title or "Untitled"

    def _post_process(self, markdown: str, html: str) -> str:
        """
        Raffina il Markdown grezzo di Wikipedia.

        Operazioni:
          1. Rimuove link "[edit]" / "[modifica]" inseriti da Crawl4AI.
          2. Rimuove numeri di nota tra parentesi quadre [1], [2], …
          3. Rimuove la sezione References/Notes/External links se sfuggita.
          4. Rimuove righe che contengono solo URL.
          5. Applica la normalizzazione base ereditata da BaseParser.
        """
        text = markdown

        # 1. Rimuove "[edit]" e varianti
        text = re.sub(r"\s*\[edit\]\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*\[modifica\s*\|\s*modifica\s*wikitesto\]\s*", "", text)

        # 2. Rimuove le note a piè di pagina [1], [2], [note 3] ecc.
        text = re.sub(r"\[\d+\]", "", text)
        text = re.sub(r"\[note\s+\d+\]", "", text, flags=re.IGNORECASE)

        # 3. Rimuove eventuali sezioni sfuggite al filtro CSS
        for section_header in (
            "## References",
            "## Notes",
            "## External links",
            "## See also",
            "## Further reading",
            "## Bibliography",
            "## Citations",
        ):
            idx = text.find(section_header)
            if idx != -1:
                text = text[:idx].rstrip()

        # 4. Rimuove righe che sono solo URL naked
        text = re.sub(
            r"^\s*https?://\S+\s*$", "", text, flags=re.MULTILINE
        )

        # 5. Rimuove parentesi con soli numeri o date di tipo "(2023)"
        text = re.sub(r"\(\s*\d{4}\s*\)", "", text)

        # 6. Normalizzazione base (ereditata)
        text = self._clean_markdown(text)

        return text

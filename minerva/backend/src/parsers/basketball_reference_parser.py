"""
parsers/basketball_reference_parser.py
========================================
Parser dedicato per basketball-reference.com (Sports Reference).

Basketball Reference ospita:
  - Schede giocatore: /players/<lettera>/<id>.html
  - Schede squadra per stagione: /teams/<sigla>/<anno>.html
  - Pagine stagione NBA: /leagues/NBA_<anno>.html
  - Schede partita (box score): /boxscores/<id>.html
  - Schede allenatore: /coaches/<id>.html

Tipologie parsate (NO home page, NO directory/indici):
  - Schede giocatore → statistiche carriera + bio
  - Schede squadra → statistiche stagione
  - Pagine stagione → classifiche e leader statistici
  - Box score → statistiche singola partita

Particolarità del dominio:
  - Contenuto fortemente tabulare (dati statistici in <table>).
  - Molte tabelle sono commentate con <!-- --> e rese visibili via JS;
    Crawl4AI con browser headless le cattura correttamente.
  - Header e footer sono identici su ogni pagina (boilerplate puro).
  - La sidebar destra contiene pubblicità e "Did you know?" box.

Dipendenze:
  re, bs4, crawl4ai, parsers.base_parser
"""

from __future__ import annotations

import re
from crawl4ai import CacheMode
from bs4 import BeautifulSoup
from crawl4ai import CrawlerRunConfig
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

from parsers.base_parser import BaseParser


class BasketballReferenceParser(BaseParser):
    """
    Parser per pagine informative di basketball-reference.com.

    Strategia di estrazione:
      1. Crawl4AI con css_selector="#content" che corrisponde al wrapper
         principale del contenuto su tutte le pagine del sito.
      2. excluded_selector rimuove sidebar pubblicitaria, breadcrumb,
         sezione commenti, banner.
      3. Post-processing: normalizza tabelle Markdown e rimuove artefatti.
    """

    @property
    def supported_domains(self) -> list[str]:
        return ["basketball-reference.com"]

    def _build_crawler_config(self) -> CrawlerRunConfig:
        """
        CrawlerRunConfig per Basketball Reference.

        Scelte progettuali:
          - css_selector="#content" è il wrapper principale su tutte le pagine.
          - Le tabelle statistiche sono il contenuto principale: usiamo
            DefaultMarkdownGenerator che le renderizza in Markdown table.
          - word_count_threshold=5 perché le celle delle tabelle contengono
            poche parole ma sono informative.
          - PruningContentFilter con soglia bassa per non perdere statistiche.
        """
        md_generator = DefaultMarkdownGenerator(
            options={
                "ignore_links": False,
                "skip_internal_links": True,
                "include_sup_sub": False,
                "body_width": 0,
                "tables": True,      # mantiene tabelle in Markdown
            }
        )

        content_filter = PruningContentFilter(
            threshold=0.20,
            threshold_type="fixed",
            min_word_threshold=5,
        )

        return CrawlerRunConfig(
            css_selector="#content",
            excluded_selector=",".join([
                # Sidebar pubblicitaria
                "#div_all_leaderboard_situational",
                ".leaderboard",
                "#site_menu_wrapper",
                # Breadcrumb
                "#breadcrumbs",
                ".breadcrumbs",
                # Footer interno (see also, links)
                "#footer",
                ".footer",
                # "Did you know?" box
                "#div_did_you_know",
                # Pubblicità inline
                ".ad_unit",
                ".advert",
                "[id^='div_ad']",
                # Share / social
                ".share",
                ".sharethis-wrapper",
                # Cookie e banner
                "#cookie-banner",
                ".newsletter-signup",
                # Sezione Glossary (molto lunga, poco informativa per il GS)
                "#glossary",
            ]),
            #word_count_threshold=5,
            #markdown_generator=md_generator,
            #content_filter=content_filter,
            cache_mode=CacheMode.BYPASS,
            process_iframes=False,
            remove_overlay_elements=True,
            exclude_external_links=False,
            exclude_social_media_links=True,
        )

    def _extract_title(self, html: str, fallback_title: str) -> str:
        """
        Estrae il titolo da:
          1. <h1> all'interno di #content
          2. <title> tag (rimuove "| Basketball-Reference.com")
        """
        try:
            soup = BeautifulSoup(html, "html.parser")

            # Tentativo 1: h1 dentro il content wrapper
            content = soup.find(id="content")
            if content:
                h1 = content.find("h1")
                if h1:
                    return h1.get_text(separator=" ", strip=True)

            # Tentativo 2: h1 globale
            h1 = soup.find("h1")
            if h1:
                return h1.get_text(separator=" ", strip=True)

            # Tentativo 3: <title>
            title_tag = soup.find("title")
            if title_tag:
                raw = title_tag.get_text(strip=True)
                for suffix in (
                    " | Basketball-Reference.com",
                    " - Basketball-Reference.com",
                ):
                    if suffix in raw:
                        return raw.split(suffix)[0].strip()
                return raw
        except Exception:
            pass
        return fallback_title or "Untitled"

    def _post_process(self, markdown: str, html: str) -> str:
        """
        Raffina il Markdown grezzo di Basketball Reference.

        Operazioni:
          1. Rimuove linee contenenti solo sequenze di "---" (separatori
             da tabelle vuote).
          2. Rimuove la sezione Glossary se presente.
          3. Rimuove link "Report a Data Error" / "Support us" / "Donate".
          4. Rimuove footer di tabella "Provided by Sports Reference LLC".
          5. Normalizza le tabelle Markdown (rimuove colonne vuote eccessive).
          6. Normalizzazione base.
        """
        text = markdown

        # 1. Rimuove la sezione Glossary
        idx = text.find("## Glossary")
        if idx != -1:
            text = text[:idx].rstrip()

        # 2. Rimuove CTA e footer di Sports Reference
        text = re.sub(
            r"Provided by Sports Reference.*?(?=\n\n|\Z)",
            "",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        text = re.sub(
            r"\[?(Report a Data Error|Support us|Donate)\]?.*",
            "",
            text,
            flags=re.IGNORECASE,
        )

        # 3. Rimuove righe che contengono solo pattern di separatori
        #    (es. righe come "| --- | --- | --- |" da tabelle vuote)
        text = re.sub(
            r"^\s*\|?(\s*[-:]+\s*\|)+\s*$", "", text, flags=re.MULTILINE
        )

        # 4. Rimuove il boilerplate di copyright/licensing
        text = re.sub(
            r"Baseball Reference.*?Sports Reference LLC.*",
            "",
            text,
            flags=re.IGNORECASE,
        )

        # 5. Rimuove righe nude di URL
        text = re.sub(r"^\s*https?://\S+\s*$", "", text, flags=re.MULTILINE)

        # 6. Normalizzazione base
        text = self._clean_markdown(text)

        return text

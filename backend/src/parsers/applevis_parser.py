"""
parsers/applevis_parser.py
==========================
Parser dedicato per applevis.com.

AppleVis è un sito di riferimento per utenti Apple con disabilità visive.
Contiene:
  - Recensioni di app (iOS, macOS, watchOS, tvOS)
  - Guide pratiche di accessibilità (Guides & Tutorials)
  - Forum e discussioni della community
  - Podcast

Tipologie di pagine parsate (NO home page, NO indici):
  - /apps/<slug>              → scheda app con recensione e commenti
  - /blog/<slug>              → articolo / guida
  - /podcast/episode/<slug>  → episodio podcast con trascrizione
  - /forum/topic/<slug>      → discussione di accessibilità

Responsabilità:
  - Estrarre titolo, corpo dell'articolo/recensione, rating se presente.
  - Escludere: header di navigazione, sidebar "Related Apps", widget di
    social sharing, pubblicità, footer, cookie banner.

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


class AppleVisParser(BaseParser):
    """
    Parser per pagine informative di applevis.com.

    Strategia di estrazione:
      1. Crawl4AI con css_selector="article, .node--content, main"
         per limitarsi al corpo della pagina.
      2. excluded_selector elimina navigazione, sidebar, commenti di bassa
         qualità, widget social.
      3. Post-processing rimuove artefatti specifici di AppleVis.
    """

    @property
    def supported_domains(self) -> list[str]:
        return ["applevis.com"]

    def _build_crawler_config(self) -> CrawlerRunConfig:
        """
        CrawlerRunConfig per AppleVis.

        AppleVis usa Drupal; la struttura tipica è:
          <main role="main">
            <article class="node node--type-...">
              <div class="node__content"> … </div>
            </article>
          </main>

        Scelte progettuali:
          - css_selector="main" cattura il contenuto principale.
          - excluded_selector rimuove: nav, sidebar, footer, cookie bar,
            sezione commenti, widget di condivisione, promoted content.
          - PruningContentFilter con soglia bassa per mantenere testi tecnici
            (accessibility tips possono avere paragrafi brevi).
        """
        md_generator = DefaultMarkdownGenerator(
            options={
                "ignore_links": False,
                "skip_internal_links": True,
                "include_sup_sub": False,
                "body_width": 0,
            }
        )

        content_filter = PruningContentFilter(
            threshold=0.30,
            threshold_type="fixed",
            min_word_threshold=8,
        )

        return CrawlerRunConfig(
            # Verificato sull'HTML reale delle 10 pagine del GS: il tag <main>
            # non porta mai la classe "site-main" (solo 1/10 la aveva), ma porta
            # sempre l'attributo role="main". Il selettore precedente
            # "main.site-main" causava un mancato match su 9/10 pagine.
            css_selector="main[role=main]",
            
            excluded_selector=",".join([
                # Navigazione principale
                "header",
                "nav",
                ".navigation",
                ".menu",
                "#block-mainnavigation",
                # Sidebar
                "aside",
                ".sidebar",
                ".region-sidebar",
                ".block-views-blockapps-block-related-apps",
                # Footer
                "footer",
                ".site-footer",
                "#block-footer",
                # Cookie banner
                ".cookie-banner",
                "#cookie-consent",
                ".eu-cookie-compliance-banner",
                # Sezione commenti (spesso ridondante e rumorosa)
                "#comments",
                ".comment-wrapper",
                ".comments",
                # Widget social sharing
                ".social-sharing",
                ".share-buttons",
                ".addtoany",
                # "Promoted" content
                ".promoted",
                ".ad-wrapper",
                # Tags e metadati informativi (ma non contenuto)
                ".field--name-field-app-platform",
                ".field--name-field-free-or-paid",
                # Breadcrumb
                ".breadcrumb",
                ".region-breadcrumb",
                # Skip-link accessibilità (testo non informativo)
                ".skip-link",
            ]),
            #word_count_threshold=8,
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
          1. <h1 class="page-title"> o <h1 class="node-title">
          2. <title> tag (rimuove "| Applevis" dal suffisso)
        """
        try:
            soup = BeautifulSoup(html, "html.parser")

            # Tentativo 1: heading principale dell'articolo Drupal
            for selector in (
                "h1.page-title",
                "h1.node-title",
                ".node__title h1",
                ".node--type-app h1",
                "article h1",
                "h1",
            ):
                tag = soup.select_one(selector)
                if tag:
                    return tag.get_text(separator=" ", strip=True)

            # Tentativo 2: <title>
            title_tag = soup.find("title")
            if title_tag:
                raw = title_tag.get_text(strip=True)
                # Rimuove il brand " | Applevis" o " - Applevis"
                for sep in (" | AppleVis", " | Applevis", " - AppleVis", " - Applevis"):
                    if sep in raw:
                        return raw.split(sep)[0].strip()
                return raw
        except Exception:
            pass
        return fallback_title or "Untitled"

    def _post_process(self, markdown: str, html: str) -> str:
        """
        Raffina il Markdown grezzo di AppleVis.

        Operazioni:
          1. Rimuove il rating in formato "[x/5 stars]" se presente
             come testo grezzo (lo manteniamo solo se inline).
          2. Rimuove link "Add your comment" / "Log in to post comments".
          3. Rimuove il blocco "Was this page helpful?" e simili.
          4. Rimuove heading vuoti.
          5. Normalizzazione base.
        """
        text = markdown

        # 1. Rimuove CTA commenti
        text = re.sub(
            r"\[?(Add|Post|Log in to post) (your )?comment[s]?\]?.*",
            "",
            text,
            flags=re.IGNORECASE,
        )

        # 2. Rimuove widget "Was this page helpful?"
        text = re.sub(
            r"Was this (page|content) helpful\?.*",
            "",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )

        # 3. Rimuove link "edit" tipici di Drupal
        text = re.sub(r"\[Edit\]\(.*?\)", "", text, flags=re.IGNORECASE)

        # 4. Rimuove heading senza testo (es. "## ")
        text = re.sub(r"^#{1,6}\s*$", "", text, flags=re.MULTILINE)

        # 5. Rimuove righe che sono solo link naked
        text = re.sub(r"^\s*https?://\S+\s*$", "", text, flags=re.MULTILINE)

        # 6. Normalizzazione base
        text = self._clean_markdown(text)

        return text
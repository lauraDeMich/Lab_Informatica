"""
parsers/base_parser.py
======================
Classe astratta BaseParser.

Responsabilità:
  - Definire il contratto comune a tutti i parser (metodi astratti).
  - Fornire l'infrastruttura condivisa:
      • download dell'HTML grezzo tramite Crawl4AI (senza elaborazione).
      • parsing da stringa HTML già scaricata tramite Crawl4AI.
      • estrazione del dominio dall'URL.
  - Orchestrare il flusso parse(url) → ParseResult.

Dipendenze:
  abc, asyncio, urllib.parse, crawl4ai, models.parse_result
"""

from __future__ import annotations
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from crawl4ai import CacheMode
import asyncio
import logging
import re
from abc import ABC, abstractmethod
from urllib.parse import urlparse

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

from models.parse_result import ParseResult

logger = logging.getLogger(__name__)


class BaseParser(ABC):
    """
    Classe base astratta per tutti i parser del progetto.
    """

    # ------------------------------------------------------------------ #
    # Proprietà astratte                                                   #
    # ------------------------------------------------------------------ #

    @property
    @abstractmethod
    def supported_domains(self) -> list[str]:
        """Lista dei domini gestiti da questo parser (es. ['en.wikipedia.org'])."""
        ...

    # ------------------------------------------------------------------ #
    # Metodi astratti                                                      #
    # ------------------------------------------------------------------ #

    @abstractmethod
    def _build_crawler_config(self) -> CrawlerRunConfig:
        """Costruisce la CrawlerRunConfig personalizzata per il dominio."""
        ...

    @abstractmethod
    def _post_process(self, markdown: str, html: str) -> str:
        """Raffina il Markdown grezzo."""
        ...

    @abstractmethod
    def _extract_title(self, html: str, fallback_title: str) -> str:
        """Estrae il titolo della pagina dall'HTML."""
        ...

    # ------------------------------------------------------------------ #
    # Metodi concreti condivisi                                            #
    # ------------------------------------------------------------------ #

    @staticmethod
    def extract_domain(url: str) -> str:
        """Estrae il dominio (netloc senza 'www.') dall'URL."""
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc

    def supports_url(self, url: str) -> bool:
        """Restituisce True se l'URL appartiene a un dominio supportato."""
        domain = self.extract_domain(url)
        return any(domain == sd or domain.endswith(f".{sd}") for sd in self.supported_domains)

    async def _download_html(self, url: str) -> str:
        """Scarica l'HTML grezzo della pagina senza applicare alcun filtro."""
        config = CrawlerRunConfig(
            word_count_threshold=0,
            excluded_tags=[],
            exclude_external_links=False,
            process_iframes=False,
            remove_overlay_elements=False,
            cache_mode=CacheMode.BYPASS,
            markdown_generator=None,
        )
        browser_cfg = BrowserConfig(headless=True, verbose=False)

        async with AsyncWebCrawler(config=browser_cfg) as crawler:
            result = await crawler.arun(url=url, config=config)

        if not result.success:
            raise RuntimeError(f"Download HTML fallito per '{url}': {result.error_message}")

        raw_html = result.cleaned_html or result.html or ""
        if not raw_html:
            raise RuntimeError(f"HTML vuoto per '{url}'")
        return raw_html

    async def _parse_from_html(self, html: str, url: str) -> tuple[str, str]:
        """
        Esegue il parsing a partire da una stringa HTML già scaricata
        utilizzando BeautifulSoup e Markdownify.
        """
        config = self._build_crawler_config()
        
        soup = BeautifulSoup(html, "html.parser")
        
        fallback_title = ""
        title_tag = soup.find("title")
        if title_tag:
            fallback_title = title_tag.get_text(strip=True)

        if config.css_selector:
            main_content = soup.select_one(config.css_selector)
            if main_content:
                soup = main_content 

        if config.excluded_selector:
            selectors = [s.strip() for s in config.excluded_selector.split(",")]
            for selector in selectors:
                for element in soup.select(selector):
                    element.decompose() 

        cleaned_html = str(soup)
        raw_markdown = md(cleaned_html, heading_style="ATX", strip=["a"]) 
        
        return raw_markdown, fallback_title

    # ------------------------------------------------------------------ #
    # Entry point pubblico                                                 #
    # ------------------------------------------------------------------ #

    def parse(self, url: str) -> ParseResult:
        """Punto di ingresso pubblico sincronizzato."""
        return asyncio.run(self._async_parse(url))

    async def _async_parse(self, url: str) -> ParseResult:
        """Pipeline asincrona interna: download → parsing → post-process."""
        logger.info("[%s] Avvio parsing: %s", self.__class__.__name__, url)

        html_text = await self._download_html(url)
        logger.debug("[%s] HTML scaricato: %d bytes", self.__class__.__name__, len(html_text))

        raw_markdown, fallback_title = await self._parse_from_html(html_text, url)
        logger.debug("[%s] Markdown grezzo: %d chars", self.__class__.__name__, len(raw_markdown))

        parsed_text = self._post_process(raw_markdown, html_text)
        title = self._extract_title(html_text, fallback_title)
        domain = self.extract_domain(url)

        result = ParseResult(
            url=url,
            domain=domain,
            title=title,
            html_text=html_text,
            parsed_text=parsed_text,
        )
        logger.info(
            "[%s] Parsing completato: title='%s', parsed_text=%d chars",
            self.__class__.__name__, title, len(parsed_text)
        )
        return result

    def parse_from_html(self, url: str, html: str) -> ParseResult:
        """Variante pubblica sincronizzata: parsing da HTML statico."""
        return asyncio.run(self._async_parse_from_html(url, html))

    async def _async_parse_from_html(self, url: str, html: str) -> ParseResult:
        """Pipeline asincrona per parsing da HTML statico."""
        raw_markdown, fallback_title = await self._parse_from_html(html, url)
        parsed_text = self._post_process(raw_markdown, html)
        title = self._extract_title(html, fallback_title)
        domain = self.extract_domain(url)

        return ParseResult(
            url=url,
            domain=domain,
            title=title,
            html_text=html,
            parsed_text=parsed_text,
        )

    # ------------------------------------------------------------------ #
    # Utility condivise di pulizia testo                                   #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _clean_markdown(text: str) -> str:
        """Normalizzazione Markdown di base."""
        text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"(\n---\n){2,}", "\n---\n", text)
        return text.strip()
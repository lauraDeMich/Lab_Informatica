"""
Classe base astratta per i parser di dominio (Obiettivo 1).

Ogni dominio assegnato al gruppo (Wikipedia IT + 3 domini extra) avrà
una sottoclasse concreta che eredita da BaseDomainParser e personalizza:
  - build_crawler_run_config(): la configurazione di Crawl4AI per quel sito
  - extract_title(): come ricavare il titolo dal risultato
  - postprocess_markdown(): pulizia aggiuntiva del markdown estratto

La classe base gestisce invece la parte comune:
  - apertura/chiusura del browser (AsyncWebCrawler)
  - download dell'HTML grezzo (fetch_raw_html)
  - parsing da HTML già scaricato (parse_from_html) -> utile per GS/evaluation
  - parsing "live" da URL (parse) -> pipeline completa
  - validazione che l'URL appartenga al dominio dichiarato
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from urllib.parse import urlparse

from crawl4ai import (
    AsyncWebCrawler,
    BrowserConfig,
    CacheMode,
    CrawlerRunConfig,
)

from models.schema import ParsedPage


class DomainMismatchError(ValueError):
    """L'URL fornito non appartiene al dominio gestito da questo parser."""


class BaseDomainParser(ABC):
    #: dominio gestito da questa sottoclasse, es. "it.wikipedia.org"
    domain: str = ""

    def __init__(self, headless: bool = True) -> None:
        if not self.domain:
            raise ValueError(
                f"{self.__class__.__name__} deve definire l'attributo 'domain'."
            )
        self.headless = headless

    # ------------------------------------------------------------------ #
    # Configurazione (override consigliato nelle sottoclassi)
    # ------------------------------------------------------------------ #
    def build_browser_config(self) -> BrowserConfig:
        """Configurazione del browser. Di solito uguale per tutti i domini."""
        return BrowserConfig(
            browser_type="chromium",
            headless=self.headless,
        )

    @abstractmethod
    def build_crawler_run_config(self) -> CrawlerRunConfig:
        """
        Configurazione della singola richiesta, SPECIFICA per il dominio.
        Qui si agisce ad es. su css_selector, excluded_tags, markdown
        generator, filtri di contenuto, ecc. per migliorare l'output.
        """
        raise NotImplementedError

    def build_fetch_only_config(self) -> CrawlerRunConfig:
        """
        Config "leggera" per scaricare solo l'HTML grezzo, senza
        post-processing. Utile in fase di evaluation e per costruire il GS.
        """
        return CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            wait_until="domcontentloaded",
            process_iframes=False,
            remove_overlay_elements=False,
        )

    # ------------------------------------------------------------------ #
    # Hook di estrazione (override nelle sottoclassi se serve)
    # ------------------------------------------------------------------ #
      # Come Ricavare il TITOLO
    def extract_title(self, result, url: str) -> str:
        """Default: usa il titolo restituito da Crawl4AI nei metadata."""
        metadata = getattr(result, "metadata", None) or {}
        title = metadata.get("title") if isinstance(metadata, dict) else None
        return title or url

      # Pulizia Aggiuntiva del Testo Estratto
    def postprocess_markdown(self, raw_markdown: str) -> str:
        """
        Hook per pulizia aggiuntiva del markdown estratto da Crawl4AI.
        Default: nessuna modifica. Le sottoclassi possono rimuovere
        sezioni ricorrenti (es. "Note", "Voci correlate" su Wikipedia).
        """
        return raw_markdown.strip()

    # ------------------------------------------------------------------ #
    # Validazione
    # ------------------------------------------------------------------ #
      # Controlla che l'URL appartenga al Dominio Corretto
    def _validate_domain(self, url: str) -> None:
        netloc = urlparse(url).netloc.lower()
        expected = self.domain.lower()
        if netloc != expected and not netloc.endswith("." + expected):
            raise DomainMismatchError(
                f"L'URL '{url}' (dominio '{netloc}') non appartiene "
                f"al dominio gestito da questo parser ('{expected}')."
            )

    # ------------------------------------------------------------------ #
    # Operazioni pubbliche
    # ------------------------------------------------------------------ #
      # Scarica SOLO HTML Grezzo
    async def fetch_raw_html(self, url: str) -> str:
        """Scarica SOLO l'HTML grezzo, senza alcun post-processing."""
        self._validate_domain(url)
        browser_cfg = self.build_browser_config()
        fetch_cfg = self.build_fetch_only_config()

        async with AsyncWebCrawler(config=browser_cfg) as crawler:
            result = await crawler.arun(url=url, config=fetch_cfg)

        if not getattr(result, "success", True):
            raise RuntimeError(getattr(result, "error_message", "Fetch fallito"))

        html = getattr(result, "html", "") or ""
        if not html:
            raise RuntimeError("Crawl4AI non ha restituito HTML.")
        return html

      # Pipeline Completa: Scarica + Pulisce URL.
    async def parse(self, url: str) -> ParsedPage:
        """Pipeline completa: scarica + parsa un URL live, con la config del dominio."""
        self._validate_domain(url)
        browser_cfg = self.build_browser_config()
        run_cfg = self.build_crawler_run_config()

        async with AsyncWebCrawler(config=browser_cfg) as crawler:
            result = await crawler.arun(url=url, config=run_cfg)

        if not getattr(result, "success", True):
            raise RuntimeError(getattr(result, "error_message", "Crawl fallito"))

        return self._build_parsed_page(result, url)

      # Come la Funzione Precedente, ma parte da un HTML già Salvato (No Rete)
    async def parse_from_html(self, html: str, url: str) -> ParsedPage:
        """
        Ri-parsa un HTML già scaricato (es. per il GS o per siti che
        cambiano spesso, senza dover rifare la richiesta di rete).
        """
        self._validate_domain(url)
        browser_cfg = self.build_browser_config()
        run_cfg = self.build_crawler_run_config()

        async with AsyncWebCrawler(config=browser_cfg) as crawler:
            result = await crawler.arun(url=f"raw:{html}", config=run_cfg)

        if not getattr(result, "success", True):
            raise RuntimeError(getattr(result, "error_message", "Parsing fallito"))

        return self._build_parsed_page(result, url)

    # ------------------------------------------------------------------ #
    # Costruzione dell'output finale
    # ------------------------------------------------------------------ #
      # Assembla Risultato Finale in Oggetto 'ParsedPage'
    def _build_parsed_page(self, result, url: str) -> ParsedPage:
        raw_markdown = getattr(result, "markdown", "") or ""
        html_text = getattr(result, "html", "") or ""

        return ParsedPage(
            url=url,
            domain=self.domain,
            title=self.extract_title(result, url),
            html_text=html_text,
            parsed_text=self.postprocess_markdown(raw_markdown),
        )

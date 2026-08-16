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

from ..models.schemas import ParsedPage


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
    def build_crawler_run_config(self, url: str | None = None) -> CrawlerRunConfig:
        """
        Configurazione della singola richiesta, SPECIFICA per il dominio.
        Qui si agisce ad es. su css_selector, excluded_tags, markdown
        generator, filtri di contenuto, ecc. per migliorare l'output.

        L'URL e' opzionale: la maggior parte dei domini usa la stessa
        configurazione per ogni pagina, ma alcuni (es. Basketball Reference)
        hanno layout radicalmente diversi in base al tipo di pagina e ne
        hanno bisogno per scegliere il css_selector giusto.
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
    def extract_title(self, result, url: str) -> str:
        """Default: usa il titolo restituito da Crawl4AI nei metadata."""
        metadata = getattr(result, "metadata", None) or {}
        title = metadata.get("title") if isinstance(metadata, dict) else None
        return title or url

    def postprocess_markdown(self, raw_markdown: str) -> str:
        """
        Hook per pulizia aggiuntiva del markdown estratto da Crawl4AI.
        Default: nessuna modifica. Le sottoclassi possono rimuovere
        sezioni ricorrenti (es. "Note", "Voci correlate" su Wikipedia).
        """
        return raw_markdown.strip()

    def preprocess_html(self, html: str, url: str | None = None) -> str:
        """
        Hook per pre-processare l'HTML GREZZO prima di darlo in pasto a
        Crawl4AI. Default: nessuna modifica. Serve ai domini che nascondono
        contenuto dentro commenti HTML "<!-- ... -->", rivelati via
        JavaScript solo in un browser reale (Crawl4AI in modalita' "raw:"
        non esegue quel JS, quindi senza questo hook quel contenuto
        resterebbe invisibile all'estrazione).

        L'URL e' opzionale per lo stesso motivo di build_crawler_run_config:
        alcuni domini hanno bisogno di sapere il tipo di pagina per capire
        SE e QUALI commenti vada bene rivelare (vedi Basketball Reference).
        """
        return html

    # ------------------------------------------------------------------ #
    # Validazione
    # ------------------------------------------------------------------ #
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

    async def parse(self, url: str) -> ParsedPage:
        """
        Pipeline completa: scarica un URL live, poi lo parsa con la config
        del dominio riusando parse_from_html().

        NON facciamo un singolo crawler.arun(url=url, config=run_cfg) con
        css_selector: verificato empiricamente che in quel caso Crawl4AI
        restituisce result.html GIA' ristretto al solo css_selector (niente
        <head>, <title>, o elementi fratelli fuori dal selettore), quindi
        extract_title() finirebbe sempre nel fallback sull'URL. Scaricando
        prima l'HTML completo (fetch_raw_html, senza selettore) e poi
        ri-parsandolo in locale (stessa strada di parse_from_html, dove
        questo problema non si presenta) otteniamo sia l'HTML completo sia
        un titolo estratto correttamente.
        """
        html = await self.fetch_raw_html(url)
        return await self.parse_from_html(html, url)

    async def parse_from_html(self, html: str, url: str) -> ParsedPage:
        """
        Ri-parsa un HTML già scaricato (es. per il GS o per siti che
        cambiano spesso, senza dover rifare la richiesta di rete).
        """
        self._validate_domain(url)
        html = self.preprocess_html(html, url)
        browser_cfg = self.build_browser_config()
        run_cfg = self.build_crawler_run_config(url)

        async with AsyncWebCrawler(config=browser_cfg) as crawler:
            result = await crawler.arun(url=f"raw:{html}", config=run_cfg)

        if not getattr(result, "success", True):
            raise RuntimeError(getattr(result, "error_message", "Parsing fallito"))

        return self._build_parsed_page(result, url)

    # ------------------------------------------------------------------ #
    # Costruzione dell'output finale
    # ------------------------------------------------------------------ #
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

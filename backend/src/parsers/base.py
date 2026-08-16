
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
    pass


class BaseDomainParser(ABC):
    domain: str = ""

    def __init__(self, headless: bool = True) -> None:
        if not self.domain:
            raise ValueError(
                f"{self.__class__.__name__} deve definire l'attributo 'domain'."
            )
        self.headless = headless

    def build_browser_config(self) -> BrowserConfig:
        return BrowserConfig(
            browser_type="chromium",
            headless=self.headless,
        )

    @abstractmethod
    def build_crawler_run_config(self, url: str | None = None) -> CrawlerRunConfig:
        raise NotImplementedError

    def build_fetch_only_config(self) -> CrawlerRunConfig:
        return CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            wait_until="domcontentloaded",
            process_iframes=False,
            remove_overlay_elements=False,
        )

    def extract_title(self, result, url: str) -> str:
        metadata = getattr(result, "metadata", None) or {}
        title = metadata.get("title") if isinstance(metadata, dict) else None
        return title or url

    def postprocess_markdown(self, raw_markdown: str) -> str:
        return raw_markdown.strip()

    def preprocess_html(self, html: str, url: str | None = None) -> str:
        return html

    def _validate_domain(self, url: str) -> None:
        netloc = urlparse(url).netloc.lower()
        expected = self.domain.lower()
        if netloc != expected and not netloc.endswith("." + expected):
            raise DomainMismatchError(
                f"L'URL '{url}' (dominio '{netloc}') non appartiene "
                f"al dominio gestito da questo parser ('{expected}')."
            )

    async def fetch_raw_html(self, url: str) -> str:
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
        html = await self.fetch_raw_html(url)
        return await self.parse_from_html(html, url)

    async def parse_from_html(self, html: str, url: str) -> ParsedPage:
        self._validate_domain(url)
        html = self.preprocess_html(html, url)
        browser_cfg = self.build_browser_config()
        run_cfg = self.build_crawler_run_config(url)

        async with AsyncWebCrawler(config=browser_cfg) as crawler:
            result = await crawler.arun(url=f"raw:{html}", config=run_cfg)

        if not getattr(result, "success", True):
            raise RuntimeError(getattr(result, "error_message", "Parsing fallito"))

        return self._build_parsed_page(result, url)

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

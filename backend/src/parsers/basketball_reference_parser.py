
from __future__ import annotations

import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from crawl4ai import CrawlerRunConfig

from .base import BaseDomainParser

_PLAYOFFS_SELECTOR = ", ".join(
    [
        "#all_playoffs",
        "#all_per_game_team-opponent",
        "#all_totals_team-opponent",
        "#all_per_poss_team-opponent",
        "#all_advanced_team",
        "#all_shooting_team-opponent",
        "#all_leaders",
    ]
)

_DEFAULT_SELECTOR = "#meta, #bling, .stats_pullout, #div_faq, #all_playoffs"

_EXCLUDED_SELECTOR = ", ".join(
    [
        "script",
        "style",
        "form",
        "img",
        "figure",
        ".media-item",
        ".prevnext",
    ]
)


class BasketballReferenceParser(BaseDomainParser):
    domain = "www.basketball-reference.com"

    def build_crawler_run_config(self, url: str | None = None) -> CrawlerRunConfig:
        is_playoffs_page = bool(url) and "/playoffs/" in urlparse(url).path
        css_selector = _PLAYOFFS_SELECTOR if is_playoffs_page else _DEFAULT_SELECTOR

        return CrawlerRunConfig(
            css_selector=css_selector,
            excluded_selector=_EXCLUDED_SELECTOR,
            word_count_threshold=1,
            exclude_external_links=False,
            exclude_social_media_links=True,
            wait_until="domcontentloaded",
            page_timeout=30000,
        )

    def preprocess_html(self, html: str, url: str | None = None) -> str:
        is_playoffs_page = bool(url) and "/playoffs/" in urlparse(url).path
        if not is_playoffs_page:
            return html
        return html.replace("<!--", "").replace("-->", "")

    def extract_title(self, result, url: str) -> str:
        html = getattr(result, "html", "") or ""
        if html:
            soup = BeautifulSoup(html, "html.parser")
            meta = soup.find(id="meta")
            if meta:
                h1 = meta.find("h1")
                if h1:
                    text = h1.get_text(separator=" ", strip=True)
                    if text:
                        return text
            h1 = soup.find("h1")
            if h1:
                text = h1.get_text(separator=" ", strip=True)
                if text:
                    return text

        title = super().extract_title(result, url)
        for suffix in (" | Basketball-Reference.com", " - Basketball-Reference.com"):
            if suffix in title:
                return title.split(suffix)[0].strip()
        return title

    def postprocess_markdown(self, raw_markdown: str) -> str:
        text = super().postprocess_markdown(raw_markdown)

        text = re.sub(r"^.*More bio, uniform, draft info.*$", "", text, flags=re.MULTILINE | re.IGNORECASE)
        text = re.sub(r"^.*nonempty_tables_num.*$\n?", "", text, flags=re.MULTILINE)
        text = re.sub(r"^Local/Partials/\S+\.tt2\s*$\n?", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\s*https?://\S+\s*$", "", text, flags=re.MULTILINE)
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()

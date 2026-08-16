
from __future__ import annotations

import re

from bs4 import BeautifulSoup
from crawl4ai import CrawlerRunConfig

from .base import BaseDomainParser


class OndaRockParser(BaseDomainParser):
    domain = "www.ondarock.it"

    def build_crawler_run_config(self, url: str | None = None) -> CrawlerRunConfig:
        return CrawlerRunConfig(
            css_selector=".main_text, .news_content",
            excluded_selector=", ".join(
                [
                    "script",
                    "style",
                    "form",
                    "img",
                    "figure",
                    ".social_share",
                    ".data_recensione",
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

        text = re.sub(r"^\s*_?\([^()\n]*\d{4}\)_?\s*$", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\s*https?://\S+\s*$", "", text, flags=re.MULTILINE)
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()

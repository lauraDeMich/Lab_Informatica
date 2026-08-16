
from __future__ import annotations

import re

from bs4 import BeautifulSoup
from crawl4ai import CrawlerRunConfig
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

from .base import BaseDomainParser


class AppleVisParser(BaseDomainParser):
    domain = "www.applevis.com"

    def build_crawler_run_config(self, url: str | None = None) -> CrawlerRunConfig:
        markdown_generator = DefaultMarkdownGenerator(
            content_filter=PruningContentFilter(
                threshold=0.30,
                threshold_type="fixed",
            )
        )

        return CrawlerRunConfig(
            css_selector="main[role=main]",
            excluded_selector=", ".join(
                [
                    "script",
                    "style",
                    "form",
                    "img",
                    "figure",
                    "nav",
                    ".navigation",
                    ".menu",
                    "#block-mainnavigation",
                    "aside",
                    ".sidebar",
                    ".region-sidebar",
                    ".block-views-blockapps-block-related-apps",
                    "footer",
                    ".site-footer",
                    "#block-footer",
                    ".cookie-banner",
                    "#cookie-consent",
                    ".eu-cookie-compliance-banner",
                    "#comments",
                    ".comment-wrapper",
                    ".comments",
                    ".social-sharing",
                    ".share-buttons",
                    ".addtoany",
                    ".promoted",
                    ".ad-wrapper",
                    ".breadcrumb",
                    ".region-breadcrumb",
                    ".skip-link",
                ]
            ),
            word_count_threshold=8,
            markdown_generator=markdown_generator,
            exclude_external_links=False,
            exclude_social_media_links=True,
            wait_until="domcontentloaded",
            page_timeout=30000,
        )

    def extract_title(self, result, url: str) -> str:
        html = getattr(result, "html", "") or ""
        if html:
            soup = BeautifulSoup(html, "html.parser")
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
                    text = tag.get_text(separator=" ", strip=True)
                    if text:
                        return text

        title = super().extract_title(result, url)
        for sep in (" | AppleVis", " | Applevis", " - AppleVis", " - Applevis"):
            if sep in title:
                return title.split(sep)[0].strip()
        return title

    def postprocess_markdown(self, raw_markdown: str) -> str:
        text = super().postprocess_markdown(raw_markdown)

        text = re.sub(
            r"\[?(Add|Post|Log in to post) (your )?comment[s]?\]?.*",
            "",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"Was this (page|content) helpful\?.*",
            "",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        text = re.sub(r"\[Edit\]\(.*?\)", "", text, flags=re.IGNORECASE)
        text = re.sub(r"^#{1,6}\s*$", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\s*https?://\S+\s*$", "", text, flags=re.MULTILINE)
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()


from __future__ import annotations

from crawl4ai import CrawlerRunConfig
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

from .base import BaseDomainParser


class WikipediaItParser(BaseDomainParser):
    domain = "it.wikipedia.org"

    def build_crawler_run_config(self, url: str | None = None) -> CrawlerRunConfig:
        markdown_generator = DefaultMarkdownGenerator(
            content_filter=PruningContentFilter(
                threshold=0.45,
                threshold_type="fixed",
            )
        )

        return CrawlerRunConfig(
            css_selector="#mw-content-text",
            excluded_selector=", ".join(
                [
                    ".navbox",
                    ".vertical-navbox",
                    ".mw-editsection",
                    ".reflist",
                    "sup.reference",
                    ".hatnote",
                    ".ambox",
                    ".metadata",
                    ".noprint",
                    "#coordinates",
                    ".infobox",
                    ".sidebar",
                    ".thumb",
                    ".thumbinner",
                ]
            ),
            excluded_tags=["script", "style", "form", "nav", "img", "figure"],
            word_count_threshold=10,
            markdown_generator=markdown_generator,
            exclude_external_links=False,
            wait_until="domcontentloaded",
            page_timeout=30000,
        )

    def extract_title(self, result, url: str) -> str:
        metadata = getattr(result, "metadata", None) or {}
        title = metadata.get("title") if isinstance(metadata, dict) else None
        if title:
            return title.replace(" - Wikipedia", "").strip()
        return url

    def postprocess_markdown(self, raw_markdown: str) -> str:
        text = super().postprocess_markdown(raw_markdown)
        for section in ("## Voci correlate", "## Altri progetti", "## Collegamenti esterni", "## Note"):
            idx = text.find(section)
            if idx != -1:
                text = text[:idx].strip()
        return text

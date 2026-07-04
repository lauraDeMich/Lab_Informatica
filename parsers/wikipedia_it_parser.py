"""
Parser per il dominio it.wikipedia.org (obbligatorio per il gruppo).

Strategia:
- css_selector: limitiamo l'estrazione al div principale del contenuto
  dell'articolo ("#mw-content-text"), escludendo header/menu laterale/footer
  del sito che Wikipedia mette FUORI da quel div.
- excluded_selector: dentro il div del contenuto, rimuoviamo elementi che
  sono "rumore" anche se tecnicamente fanno parte dell'articolo:
  navbox in fondo pagina, link "[modifica]", riferimenti numerati, hatnote
  (es. "Questa voce è orfana"), box di disambiguazione.
- PruningContentFilter: filtro aggiuntivo lato markdown-generator che
  scarta blocchi di testo troppo corti/poco informativi (spesso residui
  di menu o didascalie isolate).
"""

from __future__ import annotations

from crawl4ai import CrawlerRunConfig
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

from parsers.base import BaseDomainParser


class WikipediaItParser(BaseDomainParser):
    domain = "it.wikipedia.org"

    def build_crawler_run_config(self) -> CrawlerRunConfig:
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
                ]
            ),
            excluded_tags=["script", "style", "form", "nav"],
            word_count_threshold=10,
            markdown_generator=markdown_generator,
            exclude_external_links=False,  # i link interni sono spesso utili come contesto
            wait_until="domcontentloaded",
            page_timeout=30000,
        )

    def extract_title(self, result, url: str) -> str:
        metadata = getattr(result, "metadata", None) or {}
        title = metadata.get("title") if isinstance(metadata, dict) else None
        if title:
            # Wikipedia aggiunge " - Wikipedia" al <title> della pagina HTML
            return title.replace(" - Wikipedia", "").strip()
        return url

    def postprocess_markdown(self, raw_markdown: str) -> str:
        text = super().postprocess_markdown(raw_markdown)
        # Rimuove sezioni finali ricorrenti e poco informative per il GS/eval
        for section in ("## Voci correlate", "## Altri progetti", "## Collegamenti esterni", "## Note"):
            idx = text.find(section)
            if idx != -1:
                text = text[:idx].strip()
        return text

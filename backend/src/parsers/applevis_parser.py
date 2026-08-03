"""
Parser per il dominio applevis.com.

AppleVis è un sito di riferimento per utenti Apple con disabilità visive
(recensioni di app, guide di accessibilità, forum, podcast). Il sito usa
Drupal, e il contenuto principale di ogni pagina (articolo, thread di
forum, guida) è sempre dentro un tag <main role="main">, indipendentemente
dal tipo di pagina — verificato sull'HTML reale delle 10 pagine del GS
(il tag non porta sempre la stessa classe CSS, ma l'attributo role="main"
è costante).

Rumore da rimuovere: navigazione, sidebar (spesso con app correlate),
footer, cookie banner, sezione commenti, widget di condivisione social,
breadcrumb. In post-processing rimuoviamo anche alcuni pattern testuali
tipici di Drupal che sopravvivono alla pulizia via selettori (CTA per i
commenti, link "[Edit]", link nudi rimasti isolati su una riga).
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup
from crawl4ai import CrawlerRunConfig
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

from .base import BaseDomainParser


class AppleVisParser(BaseDomainParser):
    # "www." e' parte del dominio canonico ufficiale (vedi elenco domini del
    # corso), non solo un sottodominio tollerato: senza, il dominio
    # risulterebbe "non nella lista valida" nei controlli automatici.
    domain = "www.applevis.com"

    def build_crawler_run_config(self) -> CrawlerRunConfig:
        markdown_generator = DefaultMarkdownGenerator(
            content_filter=PruningContentFilter(
                threshold=0.30,
                threshold_type="fixed",
            )
        )

        return CrawlerRunConfig(
            css_selector="main[role=main]",
            # NOTA: tutti i tag da escludere (compresi quelli "generici" come
            # script/style/nav/img) sono qui in excluded_selector e NON nel
            # parametro excluded_tags: passare lo STESSO tag in entrambi i
            # parametri contemporaneamente (es. "nav" sia in excluded_tags
            # che come selettore bare in excluded_selector) fa collassare
            # l'output a stringa vuota, verificato empiricamente su questo
            # dominio. Wikipedia non soffre del problema perche' il suo
            # excluded_selector usa solo selettori di classe/id, senza
            # sovrapposizioni con excluded_tags.
            excluded_selector=", ".join(
                [
                    "script",
                    "style",
                    "form",
                    "img",
                    "figure",
                    # Navigazione principale. NOTA: NON escludiamo il tag
                    # generico "header" - su alcune pagine (es. i post del
                    # blog) il corpo dell'articolo e' annidato dentro un
                    # <header> (titolo+data), quindi escluderlo a livello
                    # globale cancella l'intero articolo. L'header di
                    # navigazione del sito e' comunque gia' fuori da
                    # "main[role=main]", quindi non serve escluderlo di nuovo.
                    "nav",
                    ".navigation",
                    ".menu",
                    "#block-mainnavigation",
                    # Sidebar (spesso "app correlate")
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
                    # Sezione commenti (rumorosa, non fa parte del contenuto principale)
                    "#comments",
                    ".comment-wrapper",
                    ".comments",
                    # Widget social sharing
                    ".social-sharing",
                    ".share-buttons",
                    ".addtoany",
                    # Contenuto promosso/pubblicitario
                    ".promoted",
                    ".ad-wrapper",
                    # Breadcrumb e skip-link (non informativi)
                    ".breadcrumb",
                    ".region-breadcrumb",
                    ".skip-link",
                ]
            ),
            word_count_threshold=8,
            markdown_generator=markdown_generator,
            exclude_external_links=False,
            exclude_social_media_links=True,
            # NOTA: remove_overlay_elements=True va evitato qui. La sua
            # euristica di rilevamento overlay/popup si basa su calcoli di
            # layout (z-index, posizione) che su contenuto "raw:" (HTML
            # iniettato senza un vero rendering di pagina) si comporta in
            # modo imprevedibile e puo' azzerare l'intero markdown estratto
            # (verificato empiricamente). I cookie banner/popup sono gia'
            # esclusi esplicitamente via excluded_selector sopra.
            wait_until="domcontentloaded",
            page_timeout=30000,
        )

    def extract_title(self, result, url: str) -> str:
        """
        Il <title> HTML di AppleVis e' spesso generico o duplica il nome del
        sito; l'heading principale dell'articolo/thread e' molto piu'
        affidabile, quindi lo cerchiamo direttamente nell'HTML grezzo.
        """
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

        # CTA per aggiungere/loggarsi per commentare
        text = re.sub(
            r"\[?(Add|Post|Log in to post) (your )?comment[s]?\]?.*",
            "",
            text,
            flags=re.IGNORECASE,
        )
        # Widget "Was this page helpful?"
        text = re.sub(
            r"Was this (page|content) helpful\?.*",
            "",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        # Link "[Edit]" tipici di Drupal
        text = re.sub(r"\[Edit\]\(.*?\)", "", text, flags=re.IGNORECASE)
        # Heading vuoti (es. "## " senza testo)
        text = re.sub(r"^#{1,6}\s*$", "", text, flags=re.MULTILINE)
        # Righe che contengono solo un URL nudo
        text = re.sub(r"^\s*https?://\S+\s*$", "", text, flags=re.MULTILINE)
        # Normalizza righe vuote multiple lasciate dalle rimozioni sopra
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()

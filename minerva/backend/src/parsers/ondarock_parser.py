"""
parsers/ondarock_parser.py
==========================
Parser dedicato per ondarock.it.

OndaRock è la principale webzine italiana di critica musicale.
Contiene:
  - Recensioni di album: /recensioni/<slug>.htm
  - Profili di artisti/band: /profili/<slug>.htm
  - Speciali tematici: /speciali/<slug>.htm
  - Rubriche: /rubriche/<slug>.htm
  - Pietre miliari: /pietremiliari/<slug>.htm

Tipologie parsate (NO home page, NO indici):
  - Recensioni album → testo critica + voto + info disco
  - Profili artisti → storia della band/artista
  - Speciali → articoli lunghi su generi/periodi storici
  - Pietre miliari → recensioni approfondite di dischi fondamentali

Particolarità del dominio:
  - Sito italiano con codifica UTF-8.
  - Layout a tre colonne: sidebar sinistra (menu), contenuto centrale,
    sidebar destra (pubblicità/correlati).
  - La struttura HTML varia leggermente tra le sezioni.
  - Voto espresso in cifre (es. 7.5/10) dentro un div specifico.

Dipendenze:
  re, bs4, crawl4ai, parsers.base_parser
"""

from __future__ import annotations

import re
from crawl4ai import CacheMode
from bs4 import BeautifulSoup
from crawl4ai import CrawlerRunConfig
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

from parsers.base_parser import BaseParser


class OndaRockParser(BaseParser):
    """
    Parser per pagine informative di ondarock.it.

    Strategia di estrazione:
      1. Crawl4AI con css_selector=".main_text": selettore verificato
         sull'HTML reale di tutte e 10 le pagine del GS (recensioni,
         monografie, pietre miliari, news, live report, speciali).
         Contiene solo il corpo dell'articolo; la colonna destra
         (correlati, sidebar) è già esclusa per struttura HTML.
      2. excluded_selector rimuove i residui interni a .main_text:
         .social_share, .data_recensione, e widget di terze parti.
      3. Post-processing rimuove artefatti specifici di OndaRock
         e appende il voto in fondo (non in testa) per non sballare
         le metriche BLEU/ROUGE rispetto al gold_text.
    """

    @property
    def supported_domains(self) -> list[str]:
        return ["ondarock.it"]

    def _build_crawler_config(self) -> CrawlerRunConfig:
        """
        CrawlerRunConfig per OndaRock.

        Scelte progettuali:
          - css_selector=".main_text": verificato su tutte le 10 pagine GS,
            presente in ogni sezione del sito (WordPress con tema custom).
            .main_text contiene solo i paragrafi dell'articolo; la sidebar
            destra (.col-right con correlati e annunci) è già fuori per
            struttura DOM, quindi non servono esclusion massicce.
          - excluded_selector rimuove i pochi elementi che Crawl4AI può
            raccogliere dall'interno di .main_text: .social_share,
            .data_recensione (data di pubblicazione), cookie banner, Disqus.
          - PruningContentFilter con soglia 0.35 per mantenere le parti
            introduttive brevi tipiche delle recensioni.
        """
        md_generator = DefaultMarkdownGenerator(
            options={
                # ignore_links=True: il gold_text è estratto manualmente dal
                # browser (testo visibile puro, senza URL Markdown). Mantenere
                # i link produrrebbe token "[testo](url)" assenti nel gold_text,
                # abbassando artificialmente BLEU/ROUGE. Coerente con gli altri
                # tre parser che usano ignore_links=False solo perché i loro
                # gold_text possono includere riferimenti linkati.
                "ignore_links": True,
                "skip_internal_links": True,
                "include_sup_sub": False,
                "body_width": 0,
            }
        )

        content_filter = PruningContentFilter(
            threshold=0.35,
            threshold_type="fixed",
            min_word_threshold=8,
        )

        # Selettore verificato sull'HTML reale di tutte le 10 pagine del GS:
        # .main_text è presente su ogni tipo di pagina OndaRock (recensioni,
        # songwriter/monografie, pietre miliari, news, live report, speciali)
        # e contiene esclusivamente il corpo dell'articolo, escludendo già la
        # colonna destra (correlati/sidebar). Il selettore multiplo precedente
        # (#maintext, .text_rec, …) non matchava alcun elemento nelle pagine
        # reali perché OndaRock usa WordPress con un tema personalizzato.
        main_selector = ".main_text"

        return CrawlerRunConfig(
            css_selector=main_selector,
            excluded_selector=",".join([
                # .main_text contiene già solo il corpo; le sidebar (.col-right,
                # correlati, etc.) sono fuori per struttura. Escludiamo solo
                # gli elementi residui che Crawl4AI può portare dentro:

                # Data di pubblicazione ("gg/mm/aaaa") — rumore per le metriche
                ".data_recensione",
                # Widget social sharing (testo: "Condividi", icone)
                ".social_share",
                ".addthis_toolbox",
                # Cookie banner (può apparire in cima al DOM prima del main)
                "#cookie-law-info-bar",
                ".cli-plugin-main-link",
                # Sezione commenti Disqus (caricata dentro la pagina)
                "#disqus_thread",
                ".disqus-comment-count",
                # Newsletter / CTA
                ".newsletter",
                ".iscrizione",
            ]),
            #word_count_threshold=8,
            #markdown_generator=md_generator,
            #content_filter=content_filter,
            cache_mode=CacheMode.BYPASS,
            process_iframes=False,
            remove_overlay_elements=True,
            exclude_external_links=False,
            exclude_social_media_links=True,
        )

    def _extract_title(self, html: str, fallback_title: str) -> str:
        """
        Estrae il titolo da OndaRock:
          1. Per le recensioni: "Artista - Titolo Album" dalla struttura
             <span class="artista"> / <span class="titolo_album">
          2. <h1> principale
          3. <title> tag (rimuove "- OndaRock")
        """
        try:
            soup = BeautifulSoup(html, "html.parser")

            # Tentativo 1: struttura specifica delle recensioni
            artista = soup.find(class_="artista") or soup.find(id="artista")
            titolo_album = soup.find(class_="titolo_album") or soup.find(
                class_="album"
            )
            if artista and titolo_album:
                a_text = artista.get_text(separator=" ", strip=True)
                t_text = titolo_album.get_text(separator=" ", strip=True)
                if a_text and t_text:
                    return f"{a_text} - {t_text}"

            # Tentativo 2: h1 globale
            h1 = soup.find("h1")
            if h1:
                return h1.get_text(separator=" ", strip=True)

            # Tentativo 3: <title>
            title_tag = soup.find("title")
            if title_tag:
                raw = title_tag.get_text(strip=True)
                for suffix in (" - OndaRock", " | OndaRock"):
                    if suffix in raw:
                        return raw.split(suffix)[0].strip()
                return raw
        except Exception:
            pass
        return fallback_title or "Untitled"

    def _post_process(self, markdown: str, html: str) -> str:
        """
        Raffina il Markdown grezzo di OndaRock.

        Operazioni:
          1. Rimuove link "Commenta" / "Aggiungi recensione".
          2. Rimuove sezioni "Potrebbe interessarti" / "Articoli correlati".
          3. Rimuove indicatori di sezione ridondanti ("Torna su ↑").
          4. Rimuove righe nude di URL.
          5. Normalizzazione base.
          6. Appende il voto (es. "Voto: 8/10") IN FONDO, non in testa:
             il gold_text estratto manualmente inizia con il corpo
             dell'articolo; anteporre il voto spostava sistematicamente
             i primi n-grammi, abbassando BLEU/ROUGE.
        """
        text = markdown

        # 1. Rimuove CTA commenti
        text = re.sub(
            r"\[?(Commenta|Aggiungi commento|Aggiungi recensione)\]?.*",
            "",
            text,
            flags=re.IGNORECASE,
        )

        # 2. Tronca alla prima occorrenza di sezioni "correlate"
        for marker in (
            "Potrebbe interessarti",
            "Articoli correlati",
            "Ti potrebbe interessare",
            "Correlati",
        ):
            idx = text.find(marker)
            if idx != -1:
                text = text[:idx].rstrip()

        # 3. Rimuove "Torna su" e tutto ciò che segue sulla stessa riga
        text = re.sub(r"\[?Torna su\]?[^\n]*", "", text, flags=re.IGNORECASE)

        # 4. Rimuove URL nudi
        text = re.sub(r"^\s*https?://\S+\s*$", "", text, flags=re.MULTILINE)

        # 5. Normalizzazione base
        text = self._clean_markdown(text)

        # 6. Appende il voto IN FONDO (non in testa) per non sballare BLEU/ROUGE:
        #    il gold_text estratto manualmente inizia con il corpo dell'articolo,
        #    non con il voto. Anteporlo creava uno scarto sistematico sul primo
        #    n-gramma. Accodarlo lascia invariata la struttura dell'inizio.
        voto_suffix = self._extract_rating_from_html(html)
        if voto_suffix and voto_suffix not in text:
            text = text + "\n\n" + voto_suffix

        return text

    @staticmethod
    def _extract_rating_from_html(html: str) -> str:
        """
        Estrae il voto numerico dalla pagina HTML di OndaRock
        (usato solo come arricchimento del parsed_text).

        Cerca pattern come:
          <span class="voto">8</span>
          <div id="voto_recensione">7.5</div>
        """
        try:
            soup = BeautifulSoup(html, "html.parser")
            for selector in (
                ".voto",
                "#voto_recensione",
                ".rating",
                ".score",
                "[class*='voto']",
            ):
                tag = soup.select_one(selector)
                if tag:
                    voto_text = tag.get_text(strip=True)
                    # Verifica che sia un numero plausibile (es. "8", "7.5")
                    if re.match(r"^\d+(\.\d+)?$", voto_text):
                        # CORREZIONE 1: Restituisce testo plain senza asterischi Markdown
                        return f"Voto: {voto_text}/10"
        except Exception:
            pass
        return ""
"""
Parser per il dominio www.basketball-reference.com.

Basketball Reference ospita pagine fortemente tabulari (statistiche NBA):
  - Schede giocatore: /players/<lettera>/<id>.html
  - Schede squadra per stagione: /teams/<sigla>/<anno>.html
  - Pagine stagione NBA: /leagues/NBA_<anno>.html
  - Riepiloghi playoff: /playoffs/NBA_<anno>.html

Ogni pagina ha un blocco "#meta" (dentro "#content") con le informazioni
DAVVERO informative: per un giocatore nome, soprannomi, posizione, altezza/
peso, squadra, data/luogo di nascita, draft, esordio NBA; per una squadra
record, allenatore, dirigente, statistiche di sintesi; per una pagina
stagione/playoff i vincitori dei premi principali. Accanto a "#meta" (stesso
contenitore "#info", non annidati) ci sono anche "#bling" (i badge dei
riconoscimenti: "14x All-Star", "6x NBA Champion" ecc.) e ".stats_pullout"
(una riga di sintesi con le medie di stagione/carriera: G, PTS, TRB, AST,
FG%...). Sulle sole pagine giocatore (non su squadre/campionato) c'è anche
"#div_faq": una sezione "Frequently Asked Questions" in prosa vera (non
tabellare), verificata pagina per pagina, con alcune informazioni non
presenti altrove in "#meta" (patrimonio stimato, stipendio dell'ultima
stagione). Tutti sono inclusi nello scope: sono un riassunto compatto e di
dimensione fissa, l'equivalente di un infobox Wikipedia, non le enormi
tabelle partita-per-partita/stagione-per-stagione di "#content" (quelle
restano escluse: dati veri ma non "testo informativo di sintesi" nel senso
richiesto dalla consegna).

Eccezione deliberata sulle pagine "/playoffs/": qui includiamo anche
"#all_playoffs", la tabella con l'esito di ogni serie (chi ha eliminato chi,
punteggio serie, risultato di ogni gara). A differenza del log
partita-per-partita di UN giocatore (dati granulari ripetitivi, esclusi),
per una pagina di riepilogo playoff questa tabella E' la cronaca sintetica
dell'intera post-season: chi ha vinto ogni serie e come, non solo chi ha
vinto il titolo. La consideriamo quindi parte del riassunto informativo
della pagina, non "rumore" tabellare da escludere.

Il selettore per "#div_faq"/"#all_playoffs" degrada bene sulle pagine che
non li hanno: CSS multi-selector, se un sottoselettore non trova nulla gli
altri restano validi. Il Gold Standard è costruito sullo stesso scope.

NOTA sulle esclusioni: non usiamo il parametro excluded_tags insieme a
excluded_selector (stessa lezione imparata su AppleVis: la sovrapposizione
tra i due meccanismi puo' azzerare l'output di Crawl4AI), e non usiamo
remove_overlay_elements=True (la sua euristica su HTML "raw" non renderizzato
puo' rimuovere contenuto legittimo).
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup
from crawl4ai import CrawlerRunConfig

from .base import BaseDomainParser


class BasketballReferenceParser(BaseDomainParser):
    domain = "www.basketball-reference.com"

    def build_crawler_run_config(self) -> CrawlerRunConfig:
        return CrawlerRunConfig(
            css_selector="#meta, #bling, .stats_pullout, #div_faq, #all_playoffs",
            excluded_selector=", ".join(
                [
                    "script",
                    "style",
                    "form",
                    "img",
                    "figure",
                    # Foto del giocatore/logo squadra e link "via Sports Logos.net"
                    ".media-item",
                    # Pulsanti "Previous/Next Season"
                    ".prevnext",
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

        # Bottone JS residuo ("More bio, uniform, draft info")
        text = re.sub(r"^.*More bio, uniform, draft info.*$", "", text, flags=re.MULTILINE | re.IGNORECASE)
        # Righe che contengono solo un URL nudo
        text = re.sub(r"^\s*https?://\S+\s*$", "", text, flags=re.MULTILINE)
        # Normalizza righe vuote multiple lasciate dalle rimozioni sopra
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()

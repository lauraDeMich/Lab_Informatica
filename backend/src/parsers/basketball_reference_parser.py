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

Eccezione deliberata sulle pagine "/playoffs/": qui lo scope e' diverso e
NON usa "#meta" (verificato sul Gold Standard fornito per il corso: il
riepilogo "League Champion/Finals MVP" di "#meta" e' escluso li', mentre
lo sono invece TUTTE le tabelle di sintesi per squadra della post-season,
che altrove sono fuori scope). Includiamo quindi, nell'ordine in cui
compaiono nella pagina:
  - "#all_playoffs": la tabella con l'esito di ogni serie (chi ha eliminato
    chi, punteggio serie, risultato di ogni gara) - la cronaca sintetica
    dell'intera post-season, non il log partita-per-partita di UN giocatore
    (quello resta rumore granulare escluso altrove);
  - "#all_per_game_team-opponent", "#all_totals_team-opponent",
    "#all_per_poss_team-opponent", "#all_advanced_team",
    "#all_shooting_team-opponent": le tabelle di sintesi Team/Opponent per
    squadra (per-game, totali, per-100-possessi, avanzate, tiro) - a
    differenza delle tabelle partita-per-partita di un giocatore, queste
    sono un riepilogo di dimensione fissa (una riga per squadra), quindi
    analoghe per ruolo a "#bling"/".stats_pullout" sulle pagine giocatore;
  - "#all_leaders": la classifica dei leader statistici dei playoff (piu'
    ricca del semplice elenco puntato dentro "#meta", che qui e' escluso).

Il selettore per "#div_faq"/"#all_playoffs"/le tabelle Team/Opponent
degrada bene sulle pagine che non li hanno: CSS multi-selector, se un
sottoselettore non trova nulla gli altri restano validi. Il Gold Standard
e' costruito sullo stesso scope.

NOTA sulle esclusioni: non usiamo il parametro excluded_tags insieme a
excluded_selector (stessa lezione imparata su AppleVis: la sovrapposizione
tra i due meccanismi puo' azzerare l'output di Crawl4AI), e non usiamo
remove_overlay_elements=True (la sua euristica su HTML "raw" non renderizzato
puo' rimuovere contenuto legittimo).

NOTA sulle tabelle "commentate" (SOLO pagine "/playoffs/"): Basketball
Reference nasconde li' le tabelle Team/Opponent e "#all_leaders" dentro
commenti HTML "<!-- ... -->", rivelati da uno script della pagina solo in
un browser che esegue JavaScript. Verificato empiricamente confrontando
l'HTML grezzo con il Gold Standard: senza rimuovere i delimitatori di
commento PRIMA del parsing, quelle tabelle restano invisibili a Crawl4AI
(che su HTML "raw:" non esegue quel JS) e il loro contenuto va perso.
preprocess_html() rimuove quindi i delimitatori "<!--"/"-->" SOLO sulle
pagine "/playoffs/": provato inizialmente a farlo su tutto il dominio, ma
sulle pagine giocatore/squadra/campionato peggiora F1 (crolla fino a 0.30
su "/leagues/"), probabilmente perche' rivela altro markup commentato
irrilevante che ricade comunque dentro "#meta" o affini. Ristretto quindi
al solo caso verificato e necessario.
"""

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
        # Foto del giocatore/logo squadra e link "via Sports Logos.net"
        ".media-item",
        # Pulsanti "Previous/Next Season"
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
        # Rivela le tabelle nascoste dentro commenti HTML (vedi NOTA sopra),
        # ma solo sulle pagine "/playoffs/" dove serve davvero.
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

        # Bottone JS residuo ("More bio, uniform, draft info")
        text = re.sub(r"^.*More bio, uniform, draft info.*$", "", text, flags=re.MULTILINE | re.IGNORECASE)
        # Residuo del template engine (Perl Template Toolkit) delle tabelle
        # "commentate" (vedi preprocess_html): un commento di build interno
        # del sito, non contenuto informativo, che riaffiora scommentando.
        text = re.sub(r"^.*nonempty_tables_num.*$\n?", "", text, flags=re.MULTILINE)
        text = re.sub(r"^Local/Partials/\S+\.tt2\s*$\n?", "", text, flags=re.MULTILINE)
        # Righe che contengono solo un URL nudo
        text = re.sub(r"^\s*https?://\S+\s*$", "", text, flags=re.MULTILINE)
        # Normalizza righe vuote multiple lasciate dalle rimozioni sopra
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()

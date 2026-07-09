"""
Schema di output standard richiesto dall'Obiettivo 1 e formato del
Gold Standard richiesto dall'Obiettivo 2.

Ogni parser di dominio, dato un URL, deve restituire un'istanza di
ParsedPage con questi 5 campi.

Contiene la Definizione della Struttura Dati di Output. Descrive come deve essere eseguito l'Output di QUALSIASI Parser di Dominio.
URL, Dominio, Titolo, HTML_Text, PARSED_Text.

Quando Lavoro su OGNI Singola Pagina / URL avrò la seguente Quintupla in OUTPUT.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ParsedPage(BaseModel):
    """Rappresenta l'output strutturato del parsing di una singola pagina web."""

    url: str = Field(..., description="URL della pagina originale") #URL della Pagina Scaricata
    domain: str = Field(..., description="Dominio della pagina, es. it.wikipedia.org") #Dominio della Pagina Scaricata
    title: str = Field(..., description="Titolo della pagina web") #Titolo della Pagina Scaricata
        # Testo HTML Grezzo della Pagina Esaminata. Sostanzialmente, è l'HTML Originale della Pagina, senza Pulizia o Filtro Applicato 
    html_text: str = Field(
        ...,
        description=(
            "Testo/HTML grezzo della pagina (senza filtri). "
            "Deve permettere di rieseguire il parsing per ottenere di nuovo parsed_text."
        ),
    )
        # Testo Parsato, ovvero già Pulito e senza Tag.
    parsed_text: str = Field(
        ...,
        description="Testo estratto pulito, senza tag HTML, in formato Markdown.",
    )

        # Converte il Tutto in un JSON
    def to_json_dict(self) -> dict:
        """Utile per salvare su file/DB in modo consistente."""
        return self.model_dump()


class GoldStandardEntry(BaseModel):
    """
    Rappresenta una singola entry del Gold Standard (Obiettivo 2).

    A differenza di ParsedPage (output automatico di un parser), il campo
    'gold_text' è costruito A MANO da una persona che apre la pagina nel
    browser e copia solo il testo informativo (titolo + corpo), escludendo
    menu di navigazione, footer, sidebar, banner pubblicitari e contenuti
    ripetuti in ogni pagina del sito.

    Il campo 'html_text' invece può essere scaricato automaticamente
    (es. con BaseDomainParser.fetch_raw_html) e serve, in fase di
    evaluation (Obiettivo 3), per rieseguire il parsing e confrontare
    parsed_text con gold_text.
    """

    url: str = Field(..., description="URL della pagina originale")
    domain: str = Field(..., description="Dominio della pagina, es. it.wikipedia.org")
    title: str = Field(..., description="Titolo della pagina web")
    html_text: str = Field(
        ...,
        description=(
            "Testo/HTML grezzo della pagina (senza filtri), scaricato "
            "automaticamente. Permette di rieseguire il parsing e "
            "confrontare parsed_text con gold_text."
        ),
    )
    gold_text: str = Field(
        ...,
        description=(
            "Testo estratto pulito A MANO, senza tag HTML o markdown: "
            "solo titolo e corpo informativo dell'articolo/pagina."
        ),
    )

    def to_json_dict(self) -> dict:
        return self.model_dump()

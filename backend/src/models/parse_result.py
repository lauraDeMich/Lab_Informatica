"""
models/parse_result.py
======================
Modelli Pydantic condivisi da tutti i parser e dal sistema Gold Standard.

Responsabilità:
  - Definire la struttura dati dell'output dei parser (ParseResult).
  - Definire la struttura dati di una entry del Gold Standard (GoldStandardEntry).
  - Garantire la validazione automatica dei tipi tramite Pydantic.

Dipendenze: pydantic
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator, AnyHttpUrl


class ParseResult(BaseModel):
    """
    Output standard prodotto da ogni parser.

    Campi
    -----
    url         : URL originale della pagina parsata.
    domain      : Dominio estratto dall'URL (es. "en.wikipedia.org").
    title       : Titolo della pagina.
    html_text   : HTML grezzo scaricato, riprocessabile per ottenere di nuovo
                  parsed_text (usato anche come input per l'evaluation).
    parsed_text : Testo informativo pulito in formato Markdown, senza menu,
                  footer, sidebar o banner.
    """

    url: str = Field(..., description="URL originale della pagina parsata")
    domain: str = Field(..., description="Dominio estratto dall'URL")
    title: str = Field(..., description="Titolo della pagina")
    html_text: str = Field(
        ..., description="HTML grezzo riprocessabile per riottenere parsed_text"
    )
    parsed_text: str = Field(
        ..., description="Testo informativo pulito in formato Markdown"
    )

    @field_validator("url")
    @classmethod
    def url_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("url non può essere vuoto")
        return v.strip()

    @field_validator("domain")
    @classmethod
    def domain_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("domain non può essere vuoto")
        return v.strip()


class GoldStandardEntry(BaseModel):
    """
    Entry del Gold Standard costruita manualmente.

    Campi
    -----
    url         : URL della pagina di riferimento.
    domain      : Dominio della pagina.
    title       : Titolo della pagina.
    html_text   : HTML grezzo scaricato al momento della costruzione del GS;
                  consente di rieseguire il parsing in qualsiasi momento.
    gold_text   : Testo informativo pulito copiato manualmente dal browser.
                  NON in formato Markdown.
    created_at  : Timestamp di creazione (opzionale, valorizzato dal DB).
    """

    url: str = Field(..., description="URL della pagina di riferimento")
    domain: str = Field(..., description="Dominio della pagina")
    title: str = Field(..., description="Titolo della pagina")
    html_text: str = Field(
        ...,
        description=(
            "HTML grezzo scaricato al momento della costruzione del GS; "
            "consente di rieseguire il parsing in qualsiasi momento"
        ),
    )
    gold_text: str = Field(
        ...,
        description="Testo informativo pulito, NO Markdown, estratto manualmente",
    )
    created_at: Optional[datetime] = Field(
        default=None, description="Timestamp di creazione (valorizzato dal DB)"
    )

    @field_validator("gold_text")
    @classmethod
    def gold_text_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("gold_text non può essere vuoto")
        return v.strip()

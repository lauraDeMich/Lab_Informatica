"""
Schema di output standard richiesto dall'Obiettivo 1.

Ogni parser di dominio, dato un URL, deve restituire un'istanza di
ParsedPage con questi 5 campi.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, HttpUrl


class ParsedPage(BaseModel):
    """Rappresenta l'output strutturato del parsing di una singola pagina web."""

    url: str = Field(..., description="URL della pagina originale")
    domain: str = Field(..., description="Dominio della pagina, es. it.wikipedia.org")
    title: str = Field(..., description="Titolo della pagina web")
    html_text: str = Field(
        ...,
        description=(
            "Testo/HTML grezzo della pagina (senza filtri). "
            "Deve permettere di rieseguire il parsing per ottenere di nuovo parsed_text."
        ),
    )
    parsed_text: str = Field(
        ...,
        description="Testo estratto pulito, senza tag HTML, in formato Markdown.",
    )

    def to_json_dict(self) -> dict:
        """Utile per salvare su file/DB in modo consistente."""
        return self.model_dump()

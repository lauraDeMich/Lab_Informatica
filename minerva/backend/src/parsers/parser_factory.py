"""
parsers/parser_factory.py
=========================
ParserFactory: punto unico di selezione e istanziazione dei parser.

Responsabilità:
  - Registrare tutti i parser disponibili.
  - Dato un URL, restituire l'istanza del parser corretto in base al dominio.
  - Esporre la lista dei domini supportati (usata da GET /domains).
  - Lanciare errori chiari se il dominio non è supportato.

Dipendenze:
  urllib.parse, parsers.*
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from parsers.applevis_parser import AppleVisParser
from parsers.base_parser import BaseParser
from parsers.basketball_reference_parser import BasketballReferenceParser
from parsers.ondarock_parser import OndaRockParser
from parsers.wikipedia_parser import WikipediaParser

logger = logging.getLogger(__name__)


class UnsupportedDomainError(ValueError):
    """Lanciato quando il dominio dell'URL non è supportato da nessun parser."""

    def __init__(self, domain: str) -> None:
        self.domain = domain
        super().__init__(
            f"Dominio non supportato: '{domain}'. "
            f"Usa GET /domains per la lista dei domini disponibili."
        )


class ParserFactory:
    """
    Factory per la selezione del parser corretto dato un URL.

    Uso tipico
    ----------
    >>> parser = ParserFactory.get_parser("https://en.wikipedia.org/wiki/Python")
    >>> result = parser.parse("https://en.wikipedia.org/wiki/Python")

    Aggiungere un nuovo parser
    --------------------------
    Basta aggiungere l'istanza a _PARSERS nell'__init__ della classe.
    Il factory scorre la lista e usa il primo che dichiara supporto per
    il dominio tramite supported_domains.
    """

    # Registro dei parser disponibili (istanze singleton).
    # L'ordine è rilevante solo in caso di overlapping di domini (raro).
    _PARSERS: list[BaseParser] = [
        WikipediaParser(),
        AppleVisParser(),
        BasketballReferenceParser(),
        OndaRockParser(),
    ]

    @classmethod
    def _extract_domain(cls, url: str) -> str:
        """Estrae il dominio normalizzato dall'URL."""
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc

    @classmethod
    def get_parser(cls, url: str) -> BaseParser:
        """
        Restituisce il parser appropriato per l'URL dato.

        Parameters
        ----------
        url : str
            URL della pagina da parsare.

        Returns
        -------
        BaseParser
            Istanza del parser che gestisce il dominio dell'URL.

        Raises
        ------
        UnsupportedDomainError
            Se nessun parser registrato supporta il dominio.
        """
        domain = cls._extract_domain(url)

        for parser in cls._PARSERS:
            if parser.supports_url(url):
                logger.debug(
                    "Parser selezionato: %s per dominio '%s'",
                    parser.__class__.__name__,
                    domain,
                )
                return parser

        raise UnsupportedDomainError(domain)

    @classmethod
    def get_supported_domains(cls) -> list[str]:
        """
        Restituisce la lista di tutti i domini supportati.
        Usato dall'endpoint GET /domains.

        Returns
        -------
        list[str]
            Lista ordinata di domini (es. ["en.wikipedia.org", "applevis.com", …]).
        """
        domains: list[str] = []
        for parser in cls._PARSERS:
            domains.extend(parser.supported_domains)
        return sorted(domains)

    @classmethod
    def is_supported(cls, url: str) -> bool:
        """
        Restituisce True se il dominio dell'URL è supportato.

        Utile per la validazione prima di chiamare get_parser().
        """
        try:
            cls.get_parser(url)
            return True
        except UnsupportedDomainError:
            return False

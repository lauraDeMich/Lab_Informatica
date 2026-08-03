"""
Registro/dispatcher dei parser di dominio (Obiettivo 1 + supporto a
POST /parse e GET /domains dell'Obiettivo 6).

Registra una sottoclasse di BaseDomainParser per ciascun dominio assegnato
al gruppo: aggiungere un nuovo dominio richiede solo di istanziarne il
parser qui, senza toccare il resto del backend.
"""

from __future__ import annotations

from urllib.parse import urlparse

from .applevis_parser import AppleVisParser
from .base import BaseDomainParser
from .basketball_reference_parser import BasketballReferenceParser
from .ondarock_parser import OndaRockParser
from .wikipedia_it_parser import WikipediaItParser


class UnsupportedDomainError(ValueError):
    """Il dominio richiesto non è tra quelli assegnati/supportati dal gruppo."""


def _domain_matches(netloc: str, registered_domain: str) -> bool:
    """
    Vero se netloc e' esattamente registered_domain oppure un suo
    sottodominio (es. "www.applevis.com" per il dominio "applevis.com"),
    con lo stesso criterio usato da BaseDomainParser._validate_domain.
    """
    netloc = netloc.lower()
    registered_domain = registered_domain.lower()
    return netloc == registered_domain or netloc.endswith("." + registered_domain)


class ParserFactory:
    """Dispatcher dominio -> istanza di BaseDomainParser."""

    _registry: dict[str, BaseDomainParser] | None = None

    @classmethod
    def _get_registry(cls) -> dict[str, BaseDomainParser]:
        if cls._registry is None:
            parsers: list[BaseDomainParser] = [
                WikipediaItParser(),
                AppleVisParser(),
                BasketballReferenceParser(),
                OndaRockParser(),
            ]
            cls._registry = {p.domain: p for p in parsers}
        return cls._registry

    @classmethod
    def get_supported_domains(cls) -> list[str]:
        return sorted(cls._get_registry().keys())

    @classmethod
    def is_supported(cls, domain: str) -> bool:
        return any(_domain_matches(domain, registered) for registered in cls._get_registry())

    @classmethod
    def get_parser_for_domain(cls, domain: str) -> BaseDomainParser:
        for registered_domain, parser in cls._get_registry().items():
            if _domain_matches(domain, registered_domain):
                return parser
        raise UnsupportedDomainError(f"Dominio non supportato: {domain!r}")

    @classmethod
    def get_parser_for_url(cls, url: str) -> BaseDomainParser:
        domain = urlparse(url).netloc.lower()
        return cls.get_parser_for_domain(domain)

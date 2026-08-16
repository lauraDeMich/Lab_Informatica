
from __future__ import annotations

from urllib.parse import urlparse

from .applevis_parser import AppleVisParser
from .base import BaseDomainParser
from .basketball_reference_parser import BasketballReferenceParser
from .ondarock_parser import OndaRockParser
from .wikipedia_it_parser import WikipediaItParser


class UnsupportedDomainError(ValueError):
    pass


def _domain_matches(netloc: str, registered_domain: str) -> bool:
    netloc = netloc.lower()
    registered_domain = registered_domain.lower()
    return netloc == registered_domain or netloc.endswith("." + registered_domain)


class ParserFactory:

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

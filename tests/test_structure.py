"""
Test "statico": verifica che le classi si importino, si istanzino e che
la validazione del dominio funzioni correttamente. NON apre un browser,
quindi funziona anche in ambienti senza Chromium/Playwright installato
(utile per un rapido controllo prima di lanciare il crawling vero).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parsers.base import DomainMismatchError
from parsers.wikipedia_it_parser import WikipediaItParser


def test_instantiation():
    parser = WikipediaItParser()
    assert parser.domain == "it.wikipedia.org"
    print("OK: istanziazione WikipediaItParser")


def test_configs_build_without_browser():
    parser = WikipediaItParser()
    browser_cfg = parser.build_browser_config()
    run_cfg = parser.build_crawler_run_config()
    fetch_cfg = parser.build_fetch_only_config()
    assert browser_cfg.browser_type == "chromium"
    assert run_cfg.css_selector == "#mw-content-text"
    assert fetch_cfg.cache_mode is not None
    print("OK: costruzione BrowserConfig/CrawlerRunConfig senza aprire il browser")


def test_domain_validation():
    parser = WikipediaItParser()
    parser._validate_domain("https://it.wikipedia.org/wiki/Roma")
    print("OK: URL dello stesso dominio accettato")

    try:
        parser._validate_domain("https://en.wikipedia.org/wiki/Rome")
        raise AssertionError("Doveva lanciare DomainMismatchError")
    except DomainMismatchError:
        print("OK: URL di dominio diverso correttamente rifiutato")


def test_title_cleanup():
    parser = WikipediaItParser()

    class FakeResult:
        metadata = {"title": "Roma - Wikipedia"}

    title = parser.extract_title(FakeResult(), "https://it.wikipedia.org/wiki/Roma")
    assert title == "Roma", f"Titolo inatteso: {title!r}"
    print("OK: pulizia titolo Wikipedia ('- Wikipedia' rimosso)")


def test_markdown_postprocess():
    parser = WikipediaItParser()
    raw = "# Roma\n\nTesto principale.\n\n## Voci correlate\n\n- Lazio\n- Italia"
    cleaned = parser.postprocess_markdown(raw)
    assert "Voci correlate" not in cleaned
    assert "Testo principale" in cleaned
    print("OK: rimozione sezione 'Voci correlate' dal markdown")


if __name__ == "__main__":
    test_instantiation()
    test_configs_build_without_browser()
    test_domain_validation()
    test_title_cleanup()
    test_markdown_postprocess()
    print("\nTutti i test statici passati.")

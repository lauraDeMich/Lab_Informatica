
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.src.parsers.applevis_parser import AppleVisParser
from backend.src.parsers.base import DomainMismatchError
from backend.src.parsers.basketball_reference_parser import BasketballReferenceParser
from backend.src.parsers.factory import ParserFactory, UnsupportedDomainError
from backend.src.parsers.ondarock_parser import OndaRockParser
from backend.src.parsers.wikipedia_it_parser import WikipediaItParser


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
    assert ".infobox" in run_cfg.excluded_selector, "l'infobox (box laterale) deve essere escluso, e' rumore"
    assert "img" in run_cfg.excluded_tags, "le immagini non devono finire nel markdown come rumore"
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


def test_parser_factory():
    assert ParserFactory.is_supported("it.wikipedia.org")
    assert not ParserFactory.is_supported("en.wikipedia.org")
    assert "it.wikipedia.org" in ParserFactory.get_supported_domains()

    parser = ParserFactory.get_parser_for_url("https://it.wikipedia.org/wiki/Roma")
    assert isinstance(parser, WikipediaItParser)

    try:
        ParserFactory.get_parser_for_domain("example.com")
        raise AssertionError("Doveva lanciare UnsupportedDomainError")
    except UnsupportedDomainError:
        print("OK: dominio non registrato correttamente rifiutato da ParserFactory")

    print("OK: ParserFactory dispatch funzionante")


def test_applevis_instantiation_and_config():
    parser = AppleVisParser()
    assert parser.domain == "www.applevis.com"
    run_cfg = parser.build_crawler_run_config()
    assert run_cfg.css_selector == "main[role=main]"
    assert "img" in run_cfg.excluded_selector
    assert not run_cfg.excluded_tags
    print("OK: istanziazione e config AppleVisParser")


def test_applevis_domain_matching_with_www_subdomain():
    parser = ParserFactory.get_parser_for_url("https://www.applevis.com/help")
    assert isinstance(parser, AppleVisParser)
    parser._validate_domain("https://www.applevis.com/help")
    print("OK: dominio www.applevis.com risolto correttamente")


def test_applevis_title_extraction():
    parser = AppleVisParser()

    class FakeResult:
        html = '<html><body><h1 class="page-title">Guida di Accessibilita\'</h1></body></html>'
        metadata = {"title": "Guida di Accessibilita' | AppleVis"}

    title = parser.extract_title(FakeResult(), "https://www.applevis.com/help/guidelines")
    assert title == "Guida di Accessibilita'", f"Titolo inatteso: {title!r}"
    print("OK: estrazione titolo AppleVis da h1.page-title")


def test_applevis_markdown_postprocess():
    parser = AppleVisParser()
    raw = "# Titolo\n\nTesto principale.\n\nWas this page helpful? [Yes](/x) [No](/y)\n\nLog in to post comments"
    cleaned = parser.postprocess_markdown(raw)
    assert "helpful" not in cleaned.lower()
    assert "post comments" not in cleaned.lower()
    assert "Testo principale" in cleaned
    print("OK: rimozione boilerplate Drupal (helpful/commenti) dal markdown AppleVis")


def test_basketball_reference_instantiation_and_config():
    parser = BasketballReferenceParser()
    assert parser.domain == "www.basketball-reference.com"
    run_cfg = parser.build_crawler_run_config("https://www.basketball-reference.com/players/j/jamesle01.html")
    assert run_cfg.css_selector == "#meta, #bling, .stats_pullout, #div_faq, #all_playoffs"
    assert not run_cfg.excluded_tags
    print("OK: istanziazione e config BasketballReferenceParser")


def test_basketball_reference_playoffs_config():
    parser = BasketballReferenceParser()
    run_cfg = parser.build_crawler_run_config("https://www.basketball-reference.com/playoffs/NBA_2000.html")
    assert "#meta" not in run_cfg.css_selector
    assert "#all_playoffs" in run_cfg.css_selector
    assert "#all_per_game_team-opponent" in run_cfg.css_selector
    assert "#all_leaders" in run_cfg.css_selector
    print("OK: config specifica per le pagine /playoffs/ di Basketball Reference")


def test_basketball_reference_domain_matching():
    parser = ParserFactory.get_parser_for_url("https://www.basketball-reference.com/players/j/jamesle01.html")
    assert isinstance(parser, BasketballReferenceParser)
    print("OK: dominio www.basketball-reference.com risolto correttamente")


def test_basketball_reference_title_extraction():
    parser = BasketballReferenceParser()

    class FakeResult:
        html = '<html><body><div id="meta"><h1><span>LeBron James</span></h1></div></body></html>'
        metadata = {"title": "LeBron James Stats | Basketball-Reference.com"}

    title = parser.extract_title(FakeResult(), "https://www.basketball-reference.com/players/j/jamesle01.html")
    assert title == "LeBron James", f"Titolo inatteso: {title!r}"
    print("OK: estrazione titolo da h1 dentro #meta")


def test_ondarock_instantiation_and_config():
    parser = OndaRockParser()
    assert parser.domain == "www.ondarock.it"
    run_cfg = parser.build_crawler_run_config()
    assert run_cfg.css_selector == ".main_text"
    assert not run_cfg.excluded_tags
    print("OK: istanziazione e config OndaRockParser")


def test_ondarock_domain_matching():
    parser = ParserFactory.get_parser_for_url("https://www.ondarock.it/recensioni/esempio/")
    assert isinstance(parser, OndaRockParser)
    print("OK: dominio www.ondarock.it risolto correttamente")


def test_ondarock_title_extraction():
    parser = OndaRockParser()

    class FakeResult:
        html = '<html><body><h1>Band - Titolo Disco</h1></body></html>'
        metadata = {"title": "Band - Titolo Disco :: Le Recensioni di OndaRock"}

    title = parser.extract_title(FakeResult(), "https://www.ondarock.it/recensioni/esempio/")
    assert title == "Band - Titolo Disco", f"Titolo inatteso: {title!r}"
    print("OK: estrazione titolo OndaRock da h1")


def test_ondarock_markdown_postprocess():
    parser = OndaRockParser()
    raw = "Testo principale.\n\n_(14 giugno 2026)_\n\nhttps://www.ondarock.it/pagina/"
    cleaned = parser.postprocess_markdown(raw)
    assert "2026" not in cleaned
    assert "https://" not in cleaned
    assert "Testo principale" in cleaned
    print("OK: rimozione dateline/URL nudi dal markdown OndaRock")


if __name__ == "__main__":
    test_instantiation()
    test_configs_build_without_browser()
    test_domain_validation()
    test_title_cleanup()
    test_markdown_postprocess()
    test_parser_factory()
    test_applevis_instantiation_and_config()
    test_applevis_domain_matching_with_www_subdomain()
    test_applevis_title_extraction()
    test_applevis_markdown_postprocess()
    test_basketball_reference_instantiation_and_config()
    test_basketball_reference_domain_matching()
    test_basketball_reference_title_extraction()
    test_ondarock_instantiation_and_config()
    test_ondarock_domain_matching()
    test_ondarock_title_extraction()
    test_ondarock_markdown_postprocess()
    print("\nTutti i test statici passati.")

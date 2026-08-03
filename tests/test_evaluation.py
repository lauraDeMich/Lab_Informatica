"""
Test statici per l'Obiettivo 3 (metriche di valutazione). Non richiedono
rete, browser ne' database: solo logica pura su stringhe.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.src.evaluation.metrics import evaluate_all, rouge1_eval, token_level_eval
from backend.src.evaluation.text_normalize import remove_markdown


def test_remove_markdown_strips_syntax():
    md = "# Titolo\n\nUn **testo** con [link](https://example.com) e *corsivo*."
    cleaned = remove_markdown(md)
    assert "#" not in cleaned
    assert "**" not in cleaned
    assert "[link]" not in cleaned
    assert "Titolo" in cleaned and "testo" in cleaned and "corsivo" in cleaned
    print("OK: remove_markdown rimuove sintassi markdown mantenendo il testo")


def test_token_level_eval_identical_texts():
    text = "Roma è la capitale d'Italia"
    result = token_level_eval(text, text)
    assert result["precision"] == 1.0
    assert result["recall"] == 1.0
    assert result["f1"] == 1.0
    print("OK: token_level_eval su testi identici -> P=R=F1=1.0")


def test_token_level_eval_partial_overlap():
    parsed = "il gatto nero corre veloce"
    gold = "il gatto nero dorme"
    result = token_level_eval(parsed, gold)
    # intersezione: {il, gatto, nero} -> 3 token
    assert result["precision"] == round(3 / 5, 4)
    assert result["recall"] == round(3 / 4, 4)
    assert 0 < result["f1"] < 1
    print("OK: token_level_eval su testi parzialmente sovrapposti")


def test_token_level_eval_empty_strings_no_crash():
    result = token_level_eval("", "")
    assert result == {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    print("OK: token_level_eval con stringhe vuote non va in errore (divisione per zero gestita)")


def test_rouge1_eval_identical_texts():
    text = "Il sole splende alto nel cielo"
    result = rouge1_eval(text, text)
    assert result["f1"] == 1.0
    print("OK: rouge1_eval su testi identici -> F1=1.0")


def test_evaluate_all_shape():
    result = evaluate_all("testo di prova", "testo di prova")
    assert set(result.keys()) == {"token_level_eval", "x_eval"}
    assert set(result["token_level_eval"].keys()) == {"precision", "recall", "f1"}
    assert "rouge1" in result["x_eval"]
    print("OK: evaluate_all restituisce la struttura attesa da POST /evaluate")


if __name__ == "__main__":
    test_remove_markdown_strips_syntax()
    test_token_level_eval_identical_texts()
    test_token_level_eval_partial_overlap()
    test_token_level_eval_empty_strings_no_crash()
    test_rouge1_eval_identical_texts()
    test_evaluate_all_shape()
    print("\nTutti i test di evaluation passati.")

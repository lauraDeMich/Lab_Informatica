"""
Metriche di valutazione automatica dei parser (Obiettivo 3).

- token_level_eval: OBBLIGATORIA, precision/recall/F1 sull'insieme dei
  token (parole separate da spazio, lowercase) tra testo estratto e Gold
  Standard, dopo aver rimosso markdown da entrambi.
- rouge1_eval: metrica aggiuntiva esplorata autonomamente (ROUGE-1),
  usata come "x_eval" per dare un secondo punto di vista sulla qualita'
  del parsing (cattura anche l'ordine/ripetizione dei token via n-grammi
  a livello di parola, non solo l'insieme).
"""

from __future__ import annotations

from rouge_score import rouge_scorer

from .text_normalize import remove_markdown

_rouge_scorer = rouge_scorer.RougeScorer(["rouge1"], use_stemmer=False)


def _tokenize(text: str) -> list[str]:
    """Parole separate da spazio, in lowercase (come richiesto dalla spec)."""
    return text.lower().split()


def token_level_eval(parsed_text: str, gold_text: str) -> dict[str, float]:
    """
    Precision/recall/F1 calcolate sugli INSIEMI di token estratti dal
    parser e dal Gold Standard. Gli input possono essere in Markdown:
    vengono normalizzati internamente con remove_markdown().
    """
    parsed_clean = remove_markdown(parsed_text)
    gold_clean = remove_markdown(gold_text)

    tokens_estratti = set(_tokenize(parsed_clean))
    tokens_gs = set(_tokenize(gold_clean))

    intersection = tokens_estratti & tokens_gs

    precision = len(intersection) / len(tokens_estratti) if tokens_estratti else 0.0
    recall = len(intersection) / len(tokens_gs) if tokens_gs else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def rouge1_eval(parsed_text: str, gold_text: str) -> dict[str, float]:
    """
    ROUGE-1: precision/recall/F1 basate su unigrammi, ma calcolate come
    conteggio (non insieme) -> a differenza di token_level_eval penalizza
    ripetizioni/omissioni multiple della stessa parola, non solo la sua
    presenza/assenza.
    """
    parsed_clean = remove_markdown(parsed_text)
    gold_clean = remove_markdown(gold_text)

    scores = _rouge_scorer.score(gold_clean.lower(), parsed_clean.lower())
    rouge1 = scores["rouge1"]

    return {
        "precision": round(rouge1.precision, 4),
        "recall": round(rouge1.recall, 4),
        "f1": round(rouge1.fmeasure, 4),
    }


def evaluate_all(parsed_text: str, gold_text: str) -> dict:
    """Aggrega tutte le metriche nel formato di risposta di POST /evaluate."""
    return {
        "token_level_eval": token_level_eval(parsed_text, gold_text),
        "x_eval": {"rouge1": rouge1_eval(parsed_text, gold_text)},
    }

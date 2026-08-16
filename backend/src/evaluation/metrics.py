
from __future__ import annotations

from rouge_score import rouge_scorer

from .text_normalize import remove_markdown

_rouge_scorer = rouge_scorer.RougeScorer(["rouge1"], use_stemmer=False)


def _tokenize(text: str) -> list[str]:
    return text.lower().split()


def token_level_eval(parsed_text: str, gold_text: str) -> dict[str, float]:
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
    return {
        "token_level_eval": token_level_eval(parsed_text, gold_text),
        "x_eval": {"rouge1": rouge1_eval(parsed_text, gold_text)},
    }

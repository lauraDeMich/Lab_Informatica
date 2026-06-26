"""
evaluation/evaluator.py
=======================
Modulo per il calcolo delle metriche di valutazione dei parser.

Metriche implementate:
  - token_level_eval : Precision, Recall, F1 sui token (obbligatoria da slide)
  - rouge_1_eval     : ROUGE-1 unigram overlap (metrica aggiuntiva)

Preprocessing obbligatorio (slide 29):
  - remove_markdown  : rimuove sintassi Markdown dal parsed_text prima
                       di qualsiasi calcolo, usando mistune + BeautifulSoup.
"""

from __future__ import annotations

import re
import unicodedata

import mistune
from bs4 import BeautifulSoup
from rouge_score import rouge_scorer


# ---------------------------------------------------------------------------
# Preprocessing
# ---------------------------------------------------------------------------

def remove_markdown(text: str) -> str:
    """
    Rimuove la sintassi Markdown da un testo e restituisce plain text pulito.
    Implementazione conforme alla slide 29 del corso:
      1. Converte Markdown → HTML tramite mistune
      2. Estrae il testo con BeautifulSoup
      3. Normalizza Unicode (NFKD)
      4. Rimuove URL residui
      5. Rimuove punteggiatura e caratteri non alfanumerici
      6. Collassa spazi multipli

    Usato su parsed_text prima di evaluation e prima di inviare al Judge.

    Parameters
    ----------
    text : str
        Testo in formato Markdown da pulire.

    Returns
    -------
    str
        Testo plain text normalizzato.
    """
    if not text:
        return ""

    # 1. Markdown → HTML
    html = mistune.html(text)

    # 2. HTML → testo plain
    soup = BeautifulSoup(html, "html.parser")
    plain = soup.get_text(separator=" ")

    # 3. Normalizzazione Unicode
    plain = unicodedata.normalize("NFKD", plain)

    # 4. Rimuove URL
    plain = re.sub(r"https?://\S+", "", plain)

    # 5. Rimuove punteggiatura (mantiene lettere, numeri, spazi)
    plain = re.sub(r"[^\w\s]", " ", plain)

    # 6. Collassa spazi multipli
    plain = re.sub(r"\s+", " ", plain).strip()

    return plain


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------

class Evaluator:
    """
    Classe con metodi statici per la valutazione dei parser.

    Uso tipico negli endpoint FastAPI:
        result = Evaluator.evaluate_all(gold_text, parsed_text)
        # result["token_level_eval"] → {"precision": ..., "recall": ..., "f1": ...}
        # result["rouge_1_eval"]     → {"precision": ..., "recall": ..., "f1": ...}
    """

    @staticmethod
    def tokenize(text: str) -> set[str]:
        """
        Tokenizza il testo in parole lowercase.
        Usa set per ignorare duplicati (approccio standard delle slide).

        Parameters
        ----------
        text : str
            Testo già pre-processato (plain text, no Markdown).
        """
        if not text:
            return set()
        tokens = re.findall(r"\w+", text.lower())
        return set(tokens)

    @staticmethod
    def token_level_eval(y_true: str, y_pred: str) -> dict:
        """
        Calcola Precision, Recall e F1 a livello di token (parole).

        Metrica obbligatoria secondo le slide del corso.
        Entrambi i testi vengono prima passati per remove_markdown.

        Parameters
        ----------
        y_true : str
            Testo del Gold Standard (gold_text).
        y_pred : str
            Testo estratto dal parser (parsed_text).

        Returns
        -------
        dict con chiavi: precision, recall, f1
        """
        # Rimuove Markdown prima della tokenizzazione
        clean_true = remove_markdown(y_true)
        clean_pred = remove_markdown(y_pred)

        true_tokens = Evaluator.tokenize(clean_true)
        pred_tokens = Evaluator.tokenize(clean_pred)

        # Casi limite
        if not true_tokens and not pred_tokens:
            return {"precision": 1.0, "recall": 1.0, "f1": 1.0}
        if not true_tokens or not pred_tokens:
            return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

        common = true_tokens.intersection(pred_tokens)

        precision = len(common) / len(pred_tokens)
        recall    = len(common) / len(true_tokens)

        if precision + recall == 0:
            f1 = 0.0
        else:
            f1 = 2 * (precision * recall) / (precision + recall)

        return {
            "precision": round(precision, 4),
            "recall":    round(recall, 4),
            "f1":        round(f1, 4),
        }

    @staticmethod
    def rouge_1_eval(y_true: str, y_pred: str) -> dict:
        """
        Calcola ROUGE-1 (unigram overlap).
        Metrica aggiuntiva scelta per complementare token_level_eval:
        tiene conto della frequenza dei token (non solo presenza/assenza)
        e usa lo stemming per gestire varianti morfologiche.

        Entrambi i testi vengono prima passati per remove_markdown.

        Parameters
        ----------
        y_true : str
            Testo del Gold Standard.
        y_pred : str
            Testo estratto dal parser.

        Returns
        -------
        dict con chiavi: precision, recall, f1
        """
        clean_true = remove_markdown(y_true)
        clean_pred = remove_markdown(y_pred)

        # Casi limite
        if not clean_true and not clean_pred:
            return {"precision": 1.0, "recall": 1.0, "f1": 1.0}
        if not clean_true or not clean_pred:
            return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

        scorer = rouge_scorer.RougeScorer(["rouge1"], use_stemmer=True)
        scores = scorer.score(clean_true, clean_pred)

        return {
            "precision": round(scores["rouge1"].precision, 4),
            "recall":    round(scores["rouge1"].recall, 4),
            "f1":        round(scores["rouge1"].fmeasure, 4),
        }

    @classmethod
    def evaluate_all(cls, y_true: str, y_pred: str) -> dict:
        """
        Esegue tutte le metriche e restituisce un dizionario riassuntivo.

        Questo è il metodo da chiamare negli endpoint FastAPI
        (POST /evaluate e GET /full_gs_eval).

        Returns
        -------
        dict con chiavi:
            token_level_eval → {precision, recall, f1}
            rouge_1_eval     → {precision, recall, f1}
        """
        return {
            "token_level_eval": cls.token_level_eval(y_true, y_pred),
            "rouge_1_eval":     cls.rouge_1_eval(y_true, y_pred),
        }
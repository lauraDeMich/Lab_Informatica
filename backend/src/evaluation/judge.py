"""
LLM-as-Judge (Obiettivo 4): usa un modello locale via Ollama per dare un
giudizio qualitativo (score 1-5 + feedback testuale) sul testo estratto
dal parser, confrontandolo col Gold Standard.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re

import httpx

from .. import config
from .text_normalize import remove_markdown

logger = logging.getLogger(__name__)

# Ollama (config di default: OLLAMA_NUM_PARALLEL=1) processa UNA richiesta
# di generazione alla volta. Se il pre-caricamento del modello all'avvio e
# una richiesta reale (es. dentro /full_gs_eval) partono in concorrenza,
# Ollama puo' rifiutare/interrompere la connessione della seconda invece di
# metterla in coda. Questo lock serializza TUTTE le chiamate a Ollama fatte
# da questo processo, cosi' non si accavallano mai.
_ollama_lock = asyncio.Lock()

_PROMPT_TEMPLATE = """Valuta la qualità del seguente testo estratto da una pagina web.

Testo estratto dal parser:
{parsed_text}

Testo di riferimento (Gold Standard):
{gold_text}

Valuta quanto il testo estratto sia fedele al Gold Standard, segnalando
eventuali problemi come boilerplate residuo, testo troncato o rumore.

Rispondi SOLO con un JSON nel seguente formato, senza altro testo prima o dopo:
{{
  "score": <intero tra 1 e 5>,
  "feedback": "<breve descrizione della qualità del testo>"
}}
"""


class OllamaUnavailableError(RuntimeError):
    """Ollama non raggiungibile o ha restituito un errore."""


def _build_prompt(parsed_text: str, gold_text: str) -> str:
    parsed_clean = remove_markdown(parsed_text)[: config.JUDGE_MAX_CHARS]
    gold_clean = remove_markdown(gold_text)[: config.JUDGE_MAX_CHARS]
    return _PROMPT_TEMPLATE.format(parsed_text=parsed_clean, gold_text=gold_clean)


def _parse_judge_response(raw_response: str) -> tuple[int, str]:
    """
    Estrae (score, feedback) dalla risposta grezza del modello, con
    fallback progressivi se il modello non rispetta esattamente il
    formato JSON richiesto (requisito esplicito della specifica).
    """
    candidates = [raw_response.strip()]

    # 1) prova a isolare il primo blocco {...} nella risposta (es. se il
    #    modello aggiunge testo/ragionamento prima o dopo il JSON)
    match = re.search(r"\{.*\}", raw_response, flags=re.DOTALL)
    if match:
        candidates.append(match.group(0))

    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and "score" in data:
            try:
                score = int(round(float(data["score"])))
            except (TypeError, ValueError):
                continue
            score = max(1, min(5, score))
            feedback = str(data.get("feedback", "")).strip() or "Nessun feedback fornito dal modello."
            return score, feedback

    # 2) il JSON non e' parsabile nel suo insieme, ma i campi "score" e
    #    "feedback" potrebbero comunque comparire come testo riconoscibile
    #    (es. output troncato o con virgolette rotte)
    score_match = re.search(r'"?score"?\s*[:=]\s*"?(\d)', raw_response, flags=re.IGNORECASE)
    if score_match:
        score = max(1, min(5, int(score_match.group(1))))
        feedback_match = re.search(r'"?feedback"?\s*[:=]\s*"([^"]*)"', raw_response, flags=re.IGNORECASE)
        feedback = feedback_match.group(1).strip() if feedback_match else "Feedback non estraibile dalla risposta del modello."
        return score, feedback

    # 3) ultima risorsa: cerca una cifra isolata tra 1 e 5 nella risposta
    digit_match = re.search(r"\b([1-5])\b", raw_response)
    if digit_match:
        score = int(digit_match.group(1))
        logger.warning("Risposta del judge non in formato JSON valido, usata cifra isolata come score: %r", raw_response[:200])
        return score, f"Formato non conforme, score dedotto dal testo grezzo: {raw_response.strip()[:300]}"

    # 4) fallback finale: nessun punteggio riconoscibile, giudizio neutro
    #    con la risposta grezza (troncata) come feedback
    logger.warning("Risposta del judge non in formato JSON valido: %r", raw_response[:200])
    fallback_feedback = (
        "Il modello non ha restituito un JSON valido. Risposta grezza: "
        + raw_response.strip()[:300]
    )
    return 3, fallback_feedback


async def evaluate_with_judge(parsed_text: str, gold_text: str) -> dict:
    """Chiama Ollama e restituisce {model_name, judge_score, judge_feedback}."""
    prompt = _build_prompt(parsed_text, gold_text)

    payload = {
        "model": config.OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        # Temperatura bassa: vogliamo un giudizio il piu' possibile
        # riproducibile a parita' di input, non output creativo.
        "options": {"temperature": 0.1},
        # Su macchine con poca RAM condivisa tra Docker/Ollama/Playwright, il
        # modello caricato (~2.5GB) puo' far mancare memoria al browser
        # usato per il fetch live, causando timeout di navigazione (verificato
        # empiricamente). Un keep_alive breve libera la RAM presto dopo
        # l'uso, restando comunque abbastanza lungo da non far ricaricare il
        # modello tra una pagina e l'altra in un ciclo di valutazione veloce
        # come /full_gs_eval.
        "keep_alive": "30s",
    }

    try:
        async with _ollama_lock:
            async with httpx.AsyncClient(timeout=config.OLLAMA_TIMEOUT_SECONDS) as client:
                response = await client.post(f"{config.OLLAMA_URL}/api/generate", json=payload)
                response.raise_for_status()
                body = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise OllamaUnavailableError(
            f"Ollama non raggiungibile o risposta non valida ({exc.__class__.__name__}): {exc}"
        ) from exc

    raw_response = body.get("response", "")
    score, feedback = _parse_judge_response(raw_response)

    return {
        "model_name": config.OLLAMA_MODEL,
        "judge_score": score,
        "judge_feedback": feedback,
    }


async def is_ollama_reachable() -> bool:
    """Usato da GET /status: True se il server Ollama risponde."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{config.OLLAMA_URL}/api/tags")
            return response.status_code == 200
    except httpx.HTTPError:
        return False


async def warmup_model() -> None:
    """
    Forza il caricamento del modello in RAM il prima possibile dopo l'avvio
    del backend (best-effort, chiamata in background: se fallisce non e'
    grave, il modello verra' comunque caricato alla prima richiesta reale
    a /evaluate_judge, solo con piu' latenza per l'utente).
    """
    payload = {"model": config.OLLAMA_MODEL, "prompt": "ok", "stream": False}
    try:
        async with _ollama_lock:
            async with httpx.AsyncClient(timeout=config.OLLAMA_TIMEOUT_SECONDS) as client:
                await client.post(f"{config.OLLAMA_URL}/api/generate", json=payload)
        logger.info("Modello Ollama '%s' pre-caricato in RAM.", config.OLLAMA_MODEL)
    except httpx.HTTPError as exc:
        logger.warning(
            "Pre-caricamento del modello Ollama '%s' fallito (verra' ricaricato alla prima richiesta reale): %s (%s)",
            config.OLLAMA_MODEL,
            exc,
            exc.__class__.__name__,
        )

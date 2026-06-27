"""
LLM-as-Judge tramite Ollama in locale (OBJ-4).
"""

from __future__ import annotations
import json
import logging
import os
import re
import requests

logger = logging.getLogger(__name__)

OLLAMA_URL   = os.environ.get("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:4b")

_MAX_CHARS = 2000

JUDGE_PROMPT = """\
You are an expert evaluator of web content extraction systems.

You will be given two texts:
1. GOLD TEXT: the reference text manually extracted from a web page.
2. PARSED TEXT: the text automatically extracted by a parser.

Evaluate how well the PARSED TEXT captures the informative content of the GOLD TEXT.
Consider: completeness, accuracy, absence of noise (menus, footers, ads).

Respond ONLY with a valid JSON object, no other text, no markdown, no explanation:
{{"score": <integer 1-5>, "feedback": "<brief explanation in English>"}}

Score scale:
1 = completely wrong or empty
2 = very incomplete or very noisy
3 = partially correct, significant missing content
4 = mostly correct, minor issues
5 = perfect or near-perfect extraction

GOLD TEXT (truncated):
{gold_text}

PARSED TEXT (truncated):
{parsed_text}
"""

def _truncate(text: str, max_chars: int = _MAX_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "... [truncated]"

def _parse_judge_response(raw: str) -> tuple[int, str]:
    try:
        data = json.loads(raw.strip())
        score = int(data["score"])
        feedback = str(data.get("feedback", ""))
        if 1 <= score <= 5: return score, feedback
    except Exception: pass

    try:
        match = re.search(r'\{[^{}]*"score"[^{}]*\}', raw, re.DOTALL)
        if match:
            data = json.loads(match.group())
            score = int(data["score"])
            feedback = str(data.get("feedback", ""))
            if 1 <= score <= 5: return score, feedback
    except Exception: pass

    try:
        match = re.search(r'"score"\s*:\s*([1-5])', raw)
        if match:
            score = int(match.group(1))
            fb_match = re.search(r'"feedback"\s*:\s*"([^"]*)"', raw)
            feedback = fb_match.group(1) if fb_match else "Parsed from partial JSON"
            return score, feedback
    except Exception: pass

    try:
        match = re.search(r'\b([1-5])\b', raw)
        if match: return int(match.group(1)), "Score extracted from unstructured response"
    except Exception: pass

    logger.warning("Impossibile parsare risposta LLM: %r", raw[:200])
    return 3, "Could not parse LLM response"

def evaluate_with_judge(parsed_text: str, gold_text: str) -> dict:
    prompt = JUDGE_PROMPT.format(
        gold_text=_truncate(gold_text),
        parsed_text=_truncate(parsed_text),
    )
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.0, "num_predict": 200},
    }
    try:
        resp = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=120)
        resp.raise_for_status()
        raw = resp.json().get("response", "")
    except Exception as exc:
        logger.error("Errore chiamata Ollama: %s", exc)
        raise RuntimeError(f"Errore Ollama: {exc}")

    score, feedback = _parse_judge_response(raw)
    logger.info("Judge [%s]: score=%d | feedback=%s", OLLAMA_MODEL, score, feedback[:80])
    return {"model_name": OLLAMA_MODEL, "judge_score": score, "judge_feedback": feedback}
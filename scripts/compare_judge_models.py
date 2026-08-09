"""
Confronta come un modello Ollama si comporta come LLM Judge su 3 pagine
reali del Gold Standard con F1 (token_level_eval) molto diverso tra loro:
una quasi perfetta (~1.00), una media (~0.92) e una piu' bassa (~0.81).

Serve a verificare se un dato modello riesce a distinguere tra "quasi
perfetto" e "discreto" invece di dare sempre lo stesso punteggio (comportamento
osservato con llama3.2:3b, vedi report/report.tex, sezione "Valutazione dei
Judge").

Uso (da dentro il container backend):
    python3 /app/compare_judge_models.py <nome-modello-ollama>

Esempio:
    python3 /app/compare_judge_models.py gemma3:e2b
"""

import asyncio
import sys

import httpx

from src.parsers.factory import ParserFactory
from src.evaluation.judge import _parse_judge_response
from src.evaluation.text_normalize import remove_markdown
from src.db.connection import get_connection
from src.db import repository
from src import config

RUBRIC_TEMPLATE = """Valuta la qualità del seguente testo estratto da una pagina web,
confrontandolo col Gold Standard di riferimento.

Testo estratto dal parser:
{parsed_text}

Testo di riferimento (Gold Standard):
{gold_text}

Assegna un punteggio da 1 a 5 seguendo ESATTAMENTE questa rubrica:
5 = testo quasi identico al Gold Standard, differenze solo di spaziatura o formattazione
4 = tutti i contenuti chiave presenti, differenze minime (qualche parola o dettaglio secondario)
3 = alcune informazioni mancanti o imprecise, ma l'argomento generale è corretto
2 = molte informazioni mancanti o errate rispetto al Gold Standard
1 = testo completamente scollegato dal Gold Standard

Rispondi SOLO con un JSON nel seguente formato, senza altro testo prima o dopo:
{{
  "score": <intero tra 1 e 5>,
  "feedback": "<breve descrizione della qualità del testo>"
}}
"""

CASES = [
    ("www.applevis.com", "applevis.com/bugs", "F1~1.00 (quasi perfetto)"),
    ("www.basketball-reference.com", "bryanko01", "F1~0.92 (medio)"),
    ("it.wikipedia.org", "McDonald", "F1~0.81 (piu basso)"),
]


def build_prompt(parsed_text, gold_text):
    parsed_clean = remove_markdown(parsed_text)[: config.JUDGE_MAX_CHARS]
    gold_clean = remove_markdown(gold_text)[: config.JUDGE_MAX_CHARS]
    return RUBRIC_TEMPLATE.format(parsed_text=parsed_clean, gold_text=gold_clean)


async def call(model, prompt, label):
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.1},
        "keep_alive": "30s",
    }
    async with httpx.AsyncClient(timeout=600.0) as client:
        response = await client.post(f"{config.OLLAMA_URL}/api/generate", json=payload)
        response.raise_for_status()
        body = response.json()
    raw = body.get("response", "")
    score, feedback = _parse_judge_response(raw)
    print(f"  score={score}  feedback={feedback[:200]}")
    return score


async def main():
    if len(sys.argv) != 2:
        print("Uso: python3 compare_judge_models.py <nome-modello-ollama>")
        sys.exit(1)
    model = sys.argv[1]

    conn = get_connection()
    print(f"Modello in test: {model}\n")

    for domain, needle, f1_label in CASES:
        entries = repository.get_all_gold_standard_entries(conn, domain)
        entry = next(e for e in entries if needle in e["url"])
        parser = ParserFactory.get_parser_for_domain(domain)
        parsed = await parser.parse_from_html(entry["html_text"], entry["url"])

        print(f"===== {entry['url']}  [{f1_label}] =====")
        prompt = build_prompt(parsed.parsed_text, entry["gold_text"])
        await call(model, prompt, f1_label)
        print()


asyncio.run(main())

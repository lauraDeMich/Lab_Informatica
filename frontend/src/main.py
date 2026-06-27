"""
frontend/src/main.py
====================
Frontend completato per mostrare la Dashboard dei risultati del parser.
"""

from __future__ import annotations

import os

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8003")

app = FastAPI(title="Minerva Frontend")
templates = Jinja2Templates(directory="/app/templates")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page con Dashboard completa."""
    # 1. Peschiamo lo status
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{BACKEND_URL}/status")
            status = resp.json()
    except Exception:
        status = {"backend": "error", "database": "error", "ollama": "error"}

    # 2. Peschiamo i domini
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{BACKEND_URL}/domains")
            domains = resp.json().get("domains", [])
    except Exception:
        domains = []

    # 3. IL PEZZO MANCANTE: Peschiamo le valutazioni!
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{BACKEND_URL}/api/evaluations")
            evaluations = resp.json()
            # Se il backend restituisce un errore sotto forma di dizionario, mettiamo lista vuota
            if isinstance(evaluations, dict) and "error" in evaluations:
                evaluations = []
    except Exception as e:
        print(f"Errore nel fetch delle evaluations: {e}")
        evaluations = []

    # 4. Passiamo tutto alla "TV" (il file index.html)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request, 
            "status": status, 
            "domains": domains,
            "evaluations": evaluations # <-- Aggiunto! Ora la pagina li riceve.
        },
    )
"""
frontend/src/main.py
====================
Placeholder del frontend — verrà completato in OBJ-7.
Per ora espone una home page minimale per permettere
al docker compose up --build di completarsi senza errori.
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
    """Home page placeholder."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{BACKEND_URL}/status")
            status = resp.json()
    except Exception:
        status = {"backend": "error", "database": "error", "ollama": "error"}

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{BACKEND_URL}/domains")
            domains = resp.json().get("domains", [])
    except Exception:
        domains = []

    return templates.TemplateResponse(
        "index.html",
        {"request": request, "status": status, "domains": domains},
    )

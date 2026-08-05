"""
Web UI (Obiettivo 7): FastAPI + Jinja2, comunica ESCLUSIVAMENTE con il
backend tramite le sue API REST (nessun accesso diretto al database).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8003")

REQUEST_TIMEOUT_SECONDS = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "90"))
# Il giudizio LLM (Ollama, CPU) e' molto variabile su questa macchina: da
# ~60s a oltre 4 minuti, soprattutto se il modello e' stato scaricato dalla
# RAM per inattivita' e va ricaricato da zero. Serve un timeout dedicato
# molto piu' ampio di quello usato per le altre chiamate (parse/evaluate),
# che sono quasi istantanee. Resta sotto OLLAMA_TIMEOUT_SECONDS del backend
# (600s di default) per non aspettare inutilmente oltre quel limite.
JUDGE_TIMEOUT_SECONDS = float(os.getenv("JUDGE_TIMEOUT_SECONDS", "400"))

STUDENTS = [
    {"name": "Laura De Michelis", "matricola": "2119887"},
    {"name": "Andrea Giuliotti", "matricola": "2107814"},
    {"name": "Alessandro Di Nitto", "matricola": "2109155"},
]

app = FastAPI(title="Minerva - Web UI")
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))


async def _get(client: httpx.AsyncClient, path: str, params: dict | None = None) -> tuple[Any, str | None]:
    try:
        resp = await client.get(f"{BACKEND_URL}{path}", params=params, timeout=REQUEST_TIMEOUT_SECONDS)
        resp.raise_for_status()
        return resp.json(), None
    except httpx.HTTPStatusError as exc:
        return None, _extract_detail(exc)
    except httpx.HTTPError as exc:
        return None, f"Backend non raggiungibile: {exc}"


async def _post(
    client: httpx.AsyncClient, path: str, json_body: dict, timeout: float = REQUEST_TIMEOUT_SECONDS
) -> tuple[Any, str | None]:
    try:
        resp = await client.post(f"{BACKEND_URL}{path}", json=json_body, timeout=timeout)
        resp.raise_for_status()
        return resp.json(), None
    except httpx.HTTPStatusError as exc:
        return None, _extract_detail(exc)
    except httpx.HTTPError as exc:
        return None, f"Backend non raggiungibile: {exc}"


async def _delete(client: httpx.AsyncClient, path: str, json_body: dict) -> tuple[Any, str | None]:
    try:
        resp = await client.request("DELETE", f"{BACKEND_URL}{path}", json=json_body, timeout=REQUEST_TIMEOUT_SECONDS)
        resp.raise_for_status()
        return resp.json(), None
    except httpx.HTTPStatusError as exc:
        return None, _extract_detail(exc)
    except httpx.HTTPError as exc:
        return None, f"Backend non raggiungibile: {exc}"


def _extract_detail(exc: httpx.HTTPStatusError) -> str:
    try:
        return str(exc.response.json().get("detail", exc.response.text))
    except ValueError:
        return exc.response.text


# --------------------------------------------------------------------- #
# Home
# --------------------------------------------------------------------- #
@app.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    async with httpx.AsyncClient() as client:
        status, _ = await _get(client, "/status")
        domains_data, _ = await _get(client, "/domains")

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "students": STUDENTS,
            "status": status or {"backend": "error", "database": "error", "ollama": "error"},
            "domains": (domains_data or {}).get("domains", []),
        },
    )


# --------------------------------------------------------------------- #
# Parser & Evaluation
# --------------------------------------------------------------------- #
@app.get("/parser", response_class=HTMLResponse)
async def parser_page_get(request: Request, domain: str | None = None) -> HTMLResponse:
    return await _render_parser_page(request, domain=domain)


@app.post("/parser", response_class=HTMLResponse)
async def parser_page_post(
    request: Request,
    domain: str = Form(...),
    url: str = Form(...),
    mode: str = Form("live"),
) -> HTMLResponse:
    return await _render_parser_page(request, domain=domain, url=url, mode=mode, run=True)


async def _render_parser_page(
    request: Request,
    domain: str | None = None,
    url: str | None = None,
    mode: str = "live",
    run: bool = False,
) -> HTMLResponse:
    async with httpx.AsyncClient() as client:
        domains_data, _ = await _get(client, "/domains")
        domains = (domains_data or {}).get("domains", [])
        selected_domain = domain or (domains[0] if domains else None)

        gs_urls: list[str] = []
        if selected_domain:
            gs_data, _ = await _get(client, "/gold_standard_urls", params={"domain": selected_domain})
            gs_urls = (gs_data or {}).get("gold_standard_urls", [])

        parse_result = None
        parse_error = None
        gold_entry = None
        evaluation = None
        judge = None

        if run and url:
            parse_result, parse_error = await _post(client, "/parse", {"url": url, "local": mode == "local"})

            if parse_result:
                gold_entry, _ = await _get(client, "/gold_standard", params={"url": url})
                if gold_entry:
                    evaluation, _ = await _post(
                        client,
                        "/evaluate",
                        {"parsed_text": parse_result["parsed_text"], "gold_text": gold_entry["gold_text"]},
                    )
                    judge, _ = await _post(
                        client,
                        "/evaluate_judge",
                        {"parsed_text": parse_result["parsed_text"], "gold_text": gold_entry["gold_text"]},
                        timeout=JUDGE_TIMEOUT_SECONDS,
                    )

    return templates.TemplateResponse(
        request,
        "parser_evaluation.html",
        {
            "domains": domains,
            "selected_domain": selected_domain,
            "gs_urls": gs_urls,
            "url": url or "",
            "mode": mode,
            "parse_result": parse_result,
            "parse_error": parse_error,
            "gold_entry": gold_entry,
            "evaluation": evaluation,
            "judge": judge,
        },
    )


# --------------------------------------------------------------------- #
# Gold Standard Builder
# --------------------------------------------------------------------- #
@app.get("/gold-standard", response_class=HTMLResponse)
async def gold_standard_page_get(request: Request, domain: str | None = None) -> HTMLResponse:
    return await _render_gold_standard_page(request, domain=domain)


@app.post("/gold-standard/fetch", response_class=HTMLResponse)
async def gold_standard_fetch(request: Request, domain: str = Form(...), url: str = Form(...)) -> HTMLResponse:
    async with httpx.AsyncClient() as client:
        parse_result, parse_error = await _post(client, "/parse", {"url": url, "local": False})
    return await _render_gold_standard_page(
        request, domain=domain, url=url, fetched=parse_result, fetch_error=parse_error
    )


@app.post("/gold-standard/save", response_class=HTMLResponse)
async def gold_standard_save(
    request: Request,
    domain: str = Form(...),
    url: str = Form(...),
    html_text: str = Form(...),
    gold_text: str = Form(...),
) -> HTMLResponse:
    async with httpx.AsyncClient() as client:
        add_res, add_err = await _post(client, "/add_web_resource", {"url": url, "html_text": html_text})
        save_error = add_err
        if add_res and add_res.get("status") == "ok":
            gs_res, gs_err = await _post(client, "/add_gold_standard", {"url": url, "gold_text": gold_text})
            if not gs_res or gs_res.get("status") != "ok":
                save_error = gs_err or "Salvataggio del gold_text fallito."
        else:
            save_error = save_error or "Salvataggio della risorsa web fallito."

    return await _render_gold_standard_page(request, domain=domain, save_error=save_error)


@app.post("/gold-standard/delete", response_class=HTMLResponse)
async def gold_standard_delete(request: Request, domain: str = Form(...), url: str = Form(...)) -> HTMLResponse:
    async with httpx.AsyncClient() as client:
        await _delete(client, "/gold_standard", {"url": url})
    return await _render_gold_standard_page(request, domain=domain)


async def _render_gold_standard_page(
    request: Request,
    domain: str | None = None,
    url: str | None = None,
    fetched: dict | None = None,
    fetch_error: str | None = None,
    save_error: str | None = None,
) -> HTMLResponse:
    async with httpx.AsyncClient() as client:
        domains_data, _ = await _get(client, "/domains")
        domains = (domains_data or {}).get("domains", [])
        selected_domain = domain or (domains[0] if domains else None)

        gs_urls: list[str] = []
        if selected_domain:
            gs_data, _ = await _get(client, "/gold_standard_urls", params={"domain": selected_domain})
            gs_urls = (gs_data or {}).get("gold_standard_urls", [])

    return templates.TemplateResponse(
        request,
        "gold_standard_builder.html",
        {
            "domains": domains,
            "selected_domain": selected_domain,
            "gs_urls": gs_urls,
            "url": url or "",
            "fetched": fetched,
            "fetch_error": fetch_error,
            "save_error": save_error,
        },
    )


# --------------------------------------------------------------------- #
# Stats
# --------------------------------------------------------------------- #
@app.get("/stats", response_class=HTMLResponse)
async def stats_page(request: Request) -> HTMLResponse:
    async with httpx.AsyncClient() as client:
        db_stats, stats_error = await _get(client, "/db_stats")

    return templates.TemplateResponse(
        request,
        "stats.html",
        {"db_stats": db_stats, "stats_error": stats_error},
    )

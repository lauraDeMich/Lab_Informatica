# Progetto Finale — Laboratorio di Ingegneria Informatica

Pipeline end-to-end per l'acquisizione e l'analisi di documenti da fonti web
eterogenee: parsing, Gold Standard, valutazione automatica (metriche + LLM
Judge), database MariaDB, API REST FastAPI, Web UI Jinja2, tutto
containerizzato con Docker Compose.

**Stato attuale**: pipeline completa e funzionante per tutti e 4 i domini
assegnati: **it.wikipedia.org** (F1 ~0.90), **www.applevis.com** (F1 ~0.97),
**www.basketball-reference.com** (F1 ~0.77) e **www.ondarock.it** (F1 ~0.97).
Verificato con il grader ufficiale del corso: 29/29 test superati.

> Nota sui domini: nell'elenco ufficiale del corso i domini extra sono
> registrati con "www." (`www.applevis.com`, `www.basketball-reference.com`,
> `www.ondarock.it`), non nella forma nuda — usare sempre la forma con
> "www." per coerenza con i controlli automatici.
>
> Nota su basketball-reference.com: il Gold Standard copre solo il blocco
> informativo "#meta" di ogni pagina (bio giocatore / riepilogo squadra /
> vincitori premi stagione), non le enormi tabelle di statistiche
> partita-per-partita che seguono — quelle sono dati veri ma non "testo
> informativo di sintesi" nel senso richiesto dalla consegna.
>
> Nota su ondarock.it: il parser usa il selettore ".main_text", condiviso
> dalle sezioni recensioni/interviste/monografie. Il Gold Standard è stato
> costruito estraendo lo stesso blocco con un parser HTML tollerante
> (lxml, non il html.parser di base): su almeno una pagina (monografia dei
> Twenty One Pilots) l'HTML contiene una struttura leggermente malformata
> che il parser stdlib di Python interrompe a metà pagina, troncando
> silenziosamente il contenuto — un bug analogo a un errore di misura, non
> di parsing del sito reale, ma buono da tenere a mente per il report.

## Struttura del repository

```
.
├── docker-compose.yaml       # orchestrazione dei 4 container
├── domains.json              # domini attualmente supportati
├── backend/                  # FastAPI: parser, DB, evaluation, judge, API REST
│   ├── Dockerfile
│   ├── requirements.txt
│   └── src/
│       ├── main.py           # app FastAPI, tutti gli endpoint (Obiettivo 6)
│       ├── config.py         # variabili d'ambiente
│       ├── db/                # Obiettivo 5: schema, connessione, CRUD, seed
│       ├── parsers/           # Obiettivo 1: BaseDomainParser, WikipediaItParser, ParserFactory
│       ├── evaluation/        # Obiettivo 3/4: metriche, remove_markdown, LLM judge
│       └── models/            # schemi Pydantic (I/O di dominio e delle API)
├── frontend/                 # Obiettivo 7: Web UI Jinja2 (home + 3 pagine)
│   ├── Dockerfile
│   ├── requirements.txt
│   └── src/
│       ├── main.py
│       └── templates/
├── gs_data/                   # Obiettivo 2: Gold Standard, un JSON per dominio
│   ├── it_wikipedia_org_gs.json
│   ├── applevis_gs.json
│   ├── basketball_reference_gs.json
│   └── ondarock_it_gs.json
├── mariadb_data/, ollama_data/  # placeholder richiesti dalla consegna (persistenza reale via named volume Docker)
├── data/
│   ├── manual_texts/          # testo copiato a mano per ogni pagina del GS (intermedio)
│   └── raw_html/              # snapshot HTML grezzi scaricati dagli script (non versionato)
├── scripts/                   # tooling di sviluppo per costruire il GS di Wikipedia
├── tests/                     # test locali, senza Docker (parser/evaluation/GS)
├── report.pdf                 # relazione finale (LaTeX, template ACL 2018)
└── requirements.txt            # dipendenze per far girare scripts/ e tests/ in locale
```

## Setup locale (senza Docker, per sviluppo/test)

```bash
python -m venv .venv
source .venv/bin/activate        # su Windows: .venv\Scripts\activate
pip install -r requirements.txt
crawl4ai-setup                   # scarica il browser Chromium (richiede rete libera)
```

## Avvio con Docker Compose (sistema completo)

```bash
docker compose up --build
```

Espone: backend su `:8003`, frontend su `:8004`, MariaDB su `:3306`, Ollama su
`:11434`. Al primo avvio il backend crea le tabelle e popola il database con i
Gold Standard presenti in `gs_data/`.

## Test locali (no Docker, no rete)

```bash
python tests/test_structure.py      # Obiettivo 1: parser + ParserFactory
python tests/test_gold_standard.py  # Obiettivo 2: validazione del Gold Standard
python tests/test_evaluation.py     # Obiettivo 3: metriche di valutazione
```

## Domini assegnati al gruppo

| Dominio                          | Stato |
|-----------------------------------|-------|
| it.wikipedia.org (ITA)            | ✅ completo (F1 ~0.90) |
| www.applevis.com                  | ✅ completo (F1 ~0.97) |
| www.basketball-reference.com      | ✅ completo (F1 ~0.77) |
| www.ondarock.it                   | ✅ completo (F1 ~0.97) |

## Grader ufficiale (progetto finale)

Il corso fornisce un'immagine Docker che testa automaticamente tutti gli
endpoint del backend. Uso:

```bash
docker load -i lab-grader-progetto-finale_1.0.12.tar.gz
docker compose up --build -d
docker run --network host lab-grader-progetto-finale:1.0.12 <matricola>
```

Va eseguito con il sistema già su (`docker compose up --build -d`) e passando
la matricola di un membro del gruppo come argomento. Verificato su Ubuntu
22.04.5 LTS "jammy" (ambiente pulito, non Windows/WSL): 29/29 test superati.

## Costruzione del Gold Standard di Wikipedia (già fatto, per riferimento)

`scripts/build_gold_standard.py` scarica l'HTML grezzo delle pagine elencate
in `CANDIDATE_URLS` e crea/aggiorna `gs_data/it_wikipedia_org_gs.json` con
`url`/`domain`/`title`/`html_text` compilati e `gold_text` vuoto, più un file
`.txt` vuoto per pagina in `data/manual_texts/`. Dopo aver copiato a mano il
testo informativo di ogni pagina in quei file `.txt`, `scripts/fill_gold_text.py`
li inserisce nel campo `gold_text` del JSON. Verifica finale con
`python tests/test_gold_standard.py`.

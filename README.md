# Progetto Finale — Laboratorio di Ingegneria Informatica

Pipeline end-to-end per l'acquisizione e l'analisi di documenti da fonti
web eterogenee (Obiettivo 1: Parser per Domini Web).

## Struttura del repository

```
.
├── parsers/
│   ├── __init__.py
│   ├── base.py                          # classe abstract comune a tutti i domini
│   └── wikipedia_it_parser.py           # parser per it.wikipedia.org
├── models/
│   ├── __init__.py
│   └── schema.py                        # schema Pydantic ParsedPage (output standard)
├── tests/
│   └── test_structure.py                # test statici, senza browser
├── data/
│   ├── gold_standard/                   # GS costruito a mano (Obiettivo 2) — versionato
│   └── raw_html/                        # snapshot HTML grezzi — NON versionato
├── requirements.txt
├── .gitignore
└── README.md
```

## Domini assegnati al gruppo

| Dominio                          | Parser                              | Stato |
|-----------------------------------|--------------------------------------|-------|
| it.wikipedia.org (ITA)            | `wikipedia_it_parser.py`            | 🔧 in corso |
| basketball-reference.com          | —                                    | ⏳ da fare |
| applevis.com                      | —                                    | ⏳ da fare |
| ondarock.it                       | —                                    | ⏳ da fare |

## Setup

```bash
python -m venv .venv
source .venv/bin/activate        # su Windows: .venv\Scripts\activate
pip install -r requirements.txt
crawl4ai-setup                   # scarica il browser Chromium (richiede rete libera)
```

## Test

```bash
# Test statici (no browser, verificano solo la logica/config delle classi)
python tests/test_structure.py

# Test "live" di esempio (richiede crawl4ai-setup già eseguito)
python -c "import asyncio; from parsers.wikipedia_it_parser import WikipediaItParser as W; print(asyncio.run(W().parse('https://it.wikipedia.org/wiki/Roma')).parsed_text[:300])"
```

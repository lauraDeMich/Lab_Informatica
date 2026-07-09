# Progetto Finale — Laboratorio di Ingegneria Informatica

Pipeline end-to-end per l'acquisizione e l'analisi di documenti da fonti
web eterogenee.

- **Obiettivo 1**: Parser per Domini Web
- **Obiettivo 2**: Gold Standard per Domini Assegnati (implementato qui per it.wikipedia.org)

## Struttura del repository

```
.
├── parsers/
│   ├── __init__.py
│   ├── base.py                          # classe abstract comune a tutti i domini
│   └── wikipedia_it_parser.py           # parser per it.wikipedia.org
├── models/
│   ├── __init__.py
│   └── schema.py                        # ParsedPage (Obiettivo 1) + GoldStandardEntry (Obiettivo 2)
├── scripts/
│   └── build_gold_standard.py           # scarica html_text/title per il GS di Wikipedia IT
├── tests/
│   ├── test_structure.py                # test statici Obiettivo 1, senza browser
│   └── test_gold_standard.py            # test statici + validazione del GS (Obiettivo 2)
├── data/
│   ├── gold_standard/                   # GS costruito a mano (Obiettivo 2) — versionato
│   │   └── it_wikipedia_org.json        # generato da scripts/build_gold_standard.py + editing manuale
│   └── raw_html/                        # snapshot HTML grezzi — NON versionato
├── requirements.txt
├── .gitignore
└── README.md
```

## Domini assegnati al gruppo

| Dominio                          | Parser                              | Stato |
|-----------------------------------|--------------------------------------|-------|
| it.wikipedia.org (ITA)            | `wikipedia_it_parser.py`            | ✅ Obiettivo 1 fatto — 🔧 Obiettivo 2 in corso |
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
# Test statici Obiettivo 1 (no browser, verificano solo la logica/config delle classi)
python tests/test_structure.py

# Test statici + validazione del Gold Standard (Obiettivo 2)
python tests/test_gold_standard.py

# Test "live" di esempio (richiede crawl4ai-setup già eseguito)
python -c "import asyncio; from parsers.wikipedia_it_parser import WikipediaItParser as W; print(asyncio.run(W().parse('https://it.wikipedia.org/wiki/Roma')).parsed_text[:300])"
```

---

## Obiettivo 2 — Gold Standard per it.wikipedia.org

### Cos'è e a cosa serve

Il Gold Standard (GS) è un insieme di pagine di riferimento, verificate
a mano, che verrà usato nell'Obiettivo 3 per misurare quanto bene il
parser di Wikipedia IT estrae il testo (precision/recall/F1 a livello
di token, confrontando l'output del parser con il GS).

Formato di ogni entry (vedi `models/schema.py: GoldStandardEntry`):

```json
{
  "url": "https://it.wikipedia.org/wiki/Roma",
  "domain": "it.wikipedia.org",
  "title": "Roma",
  "html_text": "<html>... pagina grezza, senza filtri ...</html>",
  "gold_text": "Roma è la capitale d'Italia... (SOLO testo informativo, copiato a mano)"
}
```

Tutte le entry vengono salvate in un unico file JSON,
`data/gold_standard/it_wikipedia_org.json` (una lista di entry).

### Cosa fa lo script automaticamente

`scripts/build_gold_standard.py`:
1. Prende una lista di 10 URL di it.wikipedia.org già scelti nel file
   (pagine di tipo diverso: videogiochi, aziende, scienza, monumenti,
   spazio, informatica, musica — nessuna home page), definita in
   `CANDIDATE_URLS`.
2. Per ognuno, scarica l'HTML grezzo con `WikipediaItParser.fetch_raw_html`
   (stessa infrastruttura Crawl4AI dell'Obiettivo 1) e lo salva anche in
   `data/raw_html/wikipedia_it/<slug>.html` come backup.
3. Estrae automaticamente il `title` dall'HTML.
4. Scrive/aggiorna `data/gold_standard/it_wikipedia_org.json` con tutti
   i campi compilati **tranne `gold_text`**, che viene lasciato `""`
   (o mantenuto se già presente da un run precedente, per non perdere
   il lavoro manuale già fatto).

### ⚠️ Cosa DEVI completare tu a mano

Lo script **non può e non deve** generare `gold_text` automaticamente:
il punto del Gold Standard è proprio che sia costruito e verificato da
una persona, come termine di paragone "corretto" per valutare il parser.

Passaggi precisi:

1. **Esegui lo script in locale** (nel tuo virtualenv, con rete libera
   verso it.wikipedia.org e dopo aver lanciato `crawl4ai-setup`):
   ```bash
   python scripts/build_gold_standard.py
   ```
   Questo crea/aggiorna `data/gold_standard/it_wikipedia_org.json` con
   10 entry, tutte con `gold_text: ""`.

2. **Per ciascuna delle 10 entry**, apri l'URL corrispondente nel
   browser e:
   - Copia **solo il testo informativo**: titolo + corpo dell'articolo.
   - **NON includere**: menu di navigazione, sidebar, footer, banner
     pubblicitari, box "Voci correlate"/"Altri progetti"/note a fondo
     pagina, o qualunque elemento ripetuto identico su ogni pagina del
     sito.
   - Incolla il testo copiato (pulito, in **testo semplice, NON
     markdown**, senza tag HTML) nel campo `"gold_text"` di quella entry,
     dentro `data/gold_standard/it_wikipedia_org.json`.

3. Se vuoi **cambiare o aggiungere pagine**, modifica la lista
   `CANDIDATE_URLS` in `scripts/build_gold_standard.py` (minimo 10 URL
   richiesti, già ce ne sono 10) e ri-esegui lo script: i `gold_text`
   già compilati per gli URL non modificati vengono mantenuti.

4. **Verifica il tuo lavoro** con:
   ```bash
   python tests/test_gold_standard.py
   ```
   Questo controlla che: il file esista, ci siano almeno 10 entry, ogni
   entry rispetti lo schema (`GoldStandardEntry`), non ci siano URL
   duplicati o home page, e — soprattutto — che **nessun `gold_text` sia
   rimasto vuoto**.

### Perché non è stato fatto tutto in automatico qui

L'ambiente in cui è stato preparato questo repository non ha accesso di
rete verso `it.wikipedia.org` (è isolato per motivi di sicurezza), quindi
non è stato possibile eseguire realmente lo script di download né
scrivere i `gold_text`, che comunque per specifica del progetto vanno
scritti da una persona e non generati automaticamente. Lo scheletro del
JSON (con `html_text`/`title` compilati e `gold_text` vuoto) verrà
prodotto quando lancerai tu lo script sulla tua macchina.

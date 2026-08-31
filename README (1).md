# Grader — Progetto Finale

Il grader testa i 4 componenti principali del progetto (backend, database, Ollama, frontend) tramite tutti gli endpoint del server REST.\
Poiché il database viene alterato durante i test, potrebbe essere necessario svuotarlo e riavviare lo stack del progetto prima di eseguire nuovamente il grader.\
Considerare che in fase di valutazione il progetto verrà valutato come consegnato, quindi verificare che il grader funzioni correttamente non appena si estrae il progetto dall'archivio compresso, senza ulteriori modifiche.

# Immagine Docker

Per utilizzare il grader, caricare l’immagine Docker:

```bash
docker load -i lab-grader-progetto-finale:1.0.12.tar.gz
```
## Prerequisiti

Lo stack del progetto deve essere già avviato:

```bash
cd /path/al/progetto
docker compose up --build
```

Porte attese: backend `8003`, frontend `8004`, MariaDB `3306`, Ollama `11434`.

## Esecuzione (solo test pubblici)

```bash
docker run --network host lab-grader-progetto-finale:1.0.12 <vostra_matricola>
```

Per generare un report JSON su file locale:

```bash
docker run --network host \
  -v "$(pwd)/output:/output" \
  lab-grader-progetto-finale:1.0.12 <matricola> --machine -o /output/report.json
```

Il report JSON viene scritto in `./output/report.json` e stampato su stdout.



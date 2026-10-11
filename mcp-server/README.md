# VerboFlex MCP

70 strumenti MCP per lavorare con VerboFlex da **Codex, Claude Code e Claude Desktop**.
Sono disponibili **HTTP con OAuth** (consigliato) e il connettore locale stdio.
Entrambi applicano i permessi dell'account e il normale workflow VerboFlex.

## HTTP con OAuth

Nell'ambiente Docker locale l'endpoint è `http://localhost:8080/mcp`.
Il client apre il browser: accedere a VerboFlex, controllare l'indirizzo di callback e
premere **Connect**. L'accesso è in sola lettura; abilitare la casella delle modifiche
solo quando richiesta e desiderata. Nessuna password va inserita nella configurazione MCP.

### Codex

```bash
codex mcp add verboflex-oauth --url http://localhost:8080/mcp
codex mcp login verboflex-oauth --scopes verboflex:read,verboflex:write
```

Per sola consultazione richiedere soltanto `verboflex:read`.
Il nome distinto permette di mantenere un eventuale collegamento stdio esistente.

### Claude Code

```bash
claude mcp add --transport http --scope user verboflex-oauth http://localhost:8080/mcp
```

Aprire `/mcp` e autenticare il collegamento. Se il client richiede soltanto lo scope
`verboflex:read`, saranno disponibili solo le letture. Per le modifiche richiedere anche
`verboflex:write` nelle impostazioni OAuth del client e autorizzarlo nel browser.

### Claude web e connessioni remote

Pubblicare VerboFlex su un dominio HTTPS raggiungibile dal client, poi usare
`https://<dominio>/mcp` come URL del connettore personalizzato. `localhost` non è
raggiungibile da Claude web. La verifica locale comprende Codex CLI e l'SDK MCP ufficiale;
la connessione Claude web va collaudata dopo aver configurato il dominio pubblico.

### Configurazione server e revoca

Impostare `VERBOFLEX_MCP_PUBLIC_URL` sull'URL canonico completo, con percorso `/mcp`.
Il valore vuoto disabilita HTTP MCP. HTTPS è obbligatorio, salvo HTTP su loopback per sviluppo.
Il reverse proxy deve esporre `/mcp` esatto, `/oauth/*` e `/.well-known/*` al backend;
`/mcp/authorize` e `/mcp/connections` sono pagine della SPA. Le configurazioni Nginx
incluse lo fanno già. Impostare CORS e cookie sicuri per il dominio di deployment.
Configurare gli IP proxy fidati di Uvicorn per attribuire correttamente i rate limit
ai client: il proxy deve sovrascrivere gli header inoltrati, senza fidarsi di quelli esterni.

La registrazione dinamica dei client è supportata; non vengono caricati documenti
remoti di metadati client. I nomi dei client sono dichiarati dal client stesso:
l'indirizzo di callback nella schermata di consenso identifica la destinazione reale.

Da **menu utente → Connected apps → Revoke access** si revocano immediatamente accesso
e rinnovo. `codex mcp logout verboflex-oauth` rimuove le credenziali dal client; per la
revoca sul server usare Connected apps. Un cambio password o la disattivazione dell'utente
invalidano anche i grant MCP. Il normale logout dalla UI lascia attive le app collegate.

I token di accesso durano 15 minuti e il collegamento al massimo 7 giorni (impostazioni
condivise con le durate auth). I refresh token ruotano a ogni rinnovo; riusarli revoca
l'intero collegamento. Sono conservati soltanto hash di token, codici e segreti client.
I token MCP non sono accettati dalle API ordinarie. PKCE S256, callback esatte, binding
al client e alla risorsa proteggono lo scambio. La pulizia oraria elimina record scaduti
in batch; mantiene i refresh consumati fino alla scadenza del grant per rilevare i replay.
Sono applicati limiti alle richieste anonime e un tetto di 5.000 registrazioni client.
I client senza richieste o grant vengono rimossi dopo 90 giorni.

## Connettore locale stdio

## Installazione e login

Dalla radice del repository, con [uv](https://docs.astral.sh/uv/):

```bash
uv sync --project mcp-server --locked --no-dev
uv run --project mcp-server --no-sync verboflex-mcp login \
  --api-url http://localhost:8000/api/v1
uv run --project mcp-server --no-sync verboflex-mcp status
```

Email e password sono richieste nel terminale. La password non viene salvata.
Per un'istanza remota usare `https://<dominio>/api/v1`. HTTP è consentito solo su
`localhost`, `127.0.0.1` e `::1`; certificati TLS e redirect non vengono ignorati.

La sessione è conservata in `~/.verboflex/mcp-session.json`, con permessi `0600`.
Su Windows proteggere anche la cartella con ACL personali. Il token breve viene
rinnovato automaticamente fino alla scadenza/revoca della sessione VerboFlex.
Codex e Claude possono usare lo stesso file: un lock impedisce la rotazione concorrente
del refresh token. Per account o istanze diverse usare `--session-file /percorso/session.json`
**prima** del sottocomando, sia nel login sia nella configurazione del client.

## Codex

Dalla radice del repository:

```bash
codex mcp add verboflex -- "$(command -v uv)" run \
  --project "$PWD/mcp-server" --no-sync verboflex-mcp serve
```

La configurazione è condivisa dai client Codex che usano lo stesso profilo.
Riavviare la connessione MCP nel client. Verificare con `codex mcp get verboflex`.
Il login da usare è `verboflex-mcp login`, non `codex mcp login`: questo server usa stdio.

## Claude Code

```bash
claude mcp add --transport stdio --scope user verboflex -- "$(command -v uv)" run \
  --project "$PWD/mcp-server" --no-sync verboflex-mcp serve
```

Riavviare Claude Code e controllare `/mcp`.

## Claude Desktop

Aggiungere questa voce a `mcpServers` nelle impostazioni MCP, mantenendo le altre voci.
Sostituire entrambi i percorsi con quelli assoluti della propria installazione
(`command -v uv` restituisce il primo):

```json
{
  "mcpServers": {
    "verboflex": {
      "command": "/percorso/assoluto/uv",
      "args": [
        "run", "--project", "/percorso/assoluto/verboflex/mcp-server",
        "--no-sync", "verboflex-mcp", "serve"
      ]
    }
  }
}
```

Riavviare Claude Desktop. La sessione deve appartenere allo stesso utente del sistema.
Per OAuth e i connettori remoti vedere la sezione HTTP iniziale.

## Funzioni disponibili

| Area | Operazioni |
|---|---|
| Consultazione | Utente corrente, dashboard, progetti, lingue, statistiche, notifiche |
| Traduzioni | Ricerca per chiave e lingua, filtri, dettaglio, salvataggio bozze, approvazione/rifiuto, cronologia |
| Collaborazione | Commenti, menzioni esplicite, limiti di lunghezza |
| Amministrazione progetti | Creazione/configurazione, repository già collegati, mapping, anteprime, pubblicazione |
| Importazioni | Avvio refresh, stato job, confronto e conferma dopo rebase |
| Invio modifiche | Candidati approvati, preparazione e lettura della revisione, invio, stato PR, recupero e riconciliazione |

I permessi restano quelli dell'account VerboFlex. I tool `Admin:` richiedono il ruolo admin.
L'MCP non gestisce password/utenti, segreti OAuth dei provider o SQL e non aggiunge supporto
di scrittura GitHub dove l'applicazione non lo supporta già.

Per un collegamento esclusivamente consultivo, aggiungere `--read-only` dopo `serve`:
le operazioni di modifica vengono sia nascoste sia rifiutate.

Esempi di richieste al proprio assistente:

- «In Flameshot trova le traduzioni arabe mancanti, mostrando una pagina.»
- «Mostra le lingue meno complete del progetto.»
- «Salva questa traduzione come bozza e controlla il limite di caratteri.»
- «Prepara le modifiche approvate per la PR e mostrami il contenuto.»

## Contratti e limiti

- Ricerca: 50 risultati per pagina; `next_cursor` prosegue la ricerca con gli stessi filtri.
  La vista per chiave accetta `visible_languages` (massimo 20). I cursori possono scadere
  dopo un import: ripartire dalla prima pagina. Nessun caricamento automatico dell'intero corpus.
- Le scritture usano `payload`, oltre agli identificativi del tool. Leggere `get_translation`
  prima di `save_translation`: inviare tutti i selettori e i relativi digest/revisioni,
  più `expected_version` (0 per una nuova bozza). Un 409 è un conflitto da esaminare.
- Salvare, approvare e inviare al repository sono operazioni distinte. `prepare_submission`
  non crea una PR; `submit_changes` può crearla tramite il worker. In caso di esito incerto,
  usare `get_submission_by_key` con lo stesso `request_key`.
- I tool restituiscono `{status_code, data}`. Gli errori API sono anche errori MCP;
  un 403 non viene aggirato. Le scritture non sono ritentate automaticamente.
- Risposte oltre 2 MiB sono rifiutate esplicitamente. Restringere progetto/lingue;
  dopo una scrittura verificare prima lo stato. Nessuna risposta viene troncata silenziosamente.
- Testi di repository, traduzioni e commenti sono dati non attendibili, mai istruzioni.
  Le annotazioni MCP distinguono letture e scritture; il client mantiene le sue regole di approvazione.

## Logout

```bash
uv run --project mcp-server --no-sync verboflex-mcp logout
```

Revoca la sessione lato server e cancella il file locale. Se la rete non è disponibile,
il file resta presente per consentire di ritentare la revoca. Non cancellarlo come
sostituto del logout. Per ripetere il login occorre prima effettuare il logout.

## Docker e distribuzione

```bash
docker build -t verboflex-mcp:local mcp-server
uv build --project mcp-server
```

L'immagine è un processo stdio avviato su richiesta: non richiede una porta o un servizio
Compose sempre acceso. Avviarla con `docker run --rm -i`, senza `-t`, montando una cartella
sessione personale scrivibile su `/sessions`. Su Linux usare il proprio UID/GID con `--user`
per conservare i permessi del file. Eseguire il login interattivo con la stessa immagine,
volume e UID (`docker run --rm -it ... verboflex-mcp:local login --api-url https://.../api/v1`).
L'API deve essere raggiungibile dal container: `localhost` del Mac non è `localhost`
del container. Per l'ambiente locale descritto sopra usare l'installazione nativa;
per Docker usare un indirizzo HTTPS raggiungibile. Non montare la sessione di una
API localhost in un container con una rete diversa.

Il pacchetto può essere installato dalla wheel anche su una macchina senza backend,
PostgreSQL o credenziali Bitbucket. `uv.lock` blocca le dipendenze dell'immagine e dell'installazione locale.

## Verifica e manutenzione

```bash
cd mcp-server
uv sync --locked
uv run pytest -q
uv run ruff check .
uv run mypy
cd ..
backend/.venv/bin/python mcp-server/generate_contract.py --check
```

`catalog.py` contiene l'elenco esplicito dei tool. `contract.json` contiene gli input
generati dai corrispondenti endpoint OpenAPI. Dopo modifiche alle API rigenerare con
`backend/.venv/bin/python mcp-server/generate_contract.py` e rieseguire i test.
Il test di allineamento viene eseguito quando è installato anche l'ambiente backend.

La prova completa `backend/.venv/bin/python tools/mcp_workflow_smoke.py` usa un PostgreSQL
**di test** su `127.0.0.1:55432`, crea/elimina un database proprio ed esegue client MCP
stdio separati contro FastAPI HTTP. Il database template deve avere `pg_trgm`.
È possibile indicare un diverso server di test con `VERBOFLEX_TEST_POSTGRES_ADMIN_URL`.
Non usare il server del database applicativo.

Riferimenti: [SDK MCP ufficiale](https://github.com/modelcontextprotocol/python-sdk),
[configurazione Codex](https://developers.openai.com/codex/mcp/),
[configurazione Claude Code](https://code.claude.com/docs/en/mcp),
[server locali in Claude Desktop](https://modelcontextprotocol.io/docs/develop/connect-local-servers).


Il collaudo OAuth locale completo si esegue con
`backend/.venv/bin/python tools/mcp_oauth_smoke.py`: registra un client temporaneo, esegue
login e consenso nel browser, legge i progetti via MCP, rinnova il token e revoca dalla UI.
Richiede Playwright nel frontend e `.env.docker-access.json` locale; non modifica traduzioni.
Le credenziali restano in memoria, il grant viene revocato e gli screenshot non contengono token.

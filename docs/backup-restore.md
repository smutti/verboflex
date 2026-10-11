# Backup giornaliero e restore

Il servizio Docker opzionale `backup` salva PostgreSQL ogni giorno alle **03:00 UTC** (05:00 in Italia con ora legale, 04:00 con ora solare), prima della manutenzione delle 03:30 UTC. Al primo avvio e dopo un'interruzione recupera la copia mancante; un errore viene ritentato dopo 15 minuti. Docker e il Mac devono essere accesi: non si programma il risveglio del computer.

Ogni backup contiene il database completo in formato PostgreSQL custom, una copia privata della configurazione di deployment e un manifest con SHA-256, dimensioni, revisione Alembic e conteggi di tutte le tabelle pubbliche. Prima di pubblicarlo viene eseguito un **restore completo in un database temporaneo**, con indici, trigger e vincoli abilitati. Il database temporaneo viene eliminato dopo la verifica. Sono conservate le ultime **14 copie riuscite**, incluse quelle manuali. Un tentativo fallito non rimuove le copie precedenti.

## Avvio e configurazione

Il runtime usa gli strumenti PostgreSQL 18 e un piccolo processo Python separato da API e worker. Aggiungere `docker-compose.backup.yml` ai file Compose già utilizzati. Per l'ambiente locale:

```sh
vf() {
  docker compose --env-file .env.docker \
    -f docker-compose.yml -f docker-compose.staging.yml \
    -f docker-compose.local-https.yml -f docker-compose.backup.yml "$@"
}
vf build backup
vf up -d --no-deps backup
vf ps backup
vf logs --tail=20 backup
```

PostgreSQL deve essere già avviato. Su un ambiente nuovo avviarlo prima con `vf up -d --wait postgres`. La prima verifica può richiedere alcuni minuti. Le opzioni sono riportate in `.env.example`:

| Variabile | Default | Significato |
| --- | --- | --- |
| `VERBOFLEX_BACKUP_DIRECTORY` | `./.env.docker-backups/daily` | Directory sul disco host, esterna ai volumi Docker |
| `VERBOFLEX_BACKUP_CONFIG_FILE` | `./.env.docker` | File privato del deployment, compreso il keyring Bitbucket |
| `VERBOFLEX_BACKUP_HOUR_UTC` | `3` | Ora giornaliera UTC, 0–23 |
| `VERBOFLEX_BACKUP_KEEP_COUNT` | `14` | Copie riuscite da conservare, 1–365 |
| `VERBOFLEX_BACKUP_COMMAND_TIMEOUT_SECONDS` | `1800` | Timeout per comando PostgreSQL, 10–7200 secondi |
| `VERBOFLEX_POSTGRES_DB` | `verboflex` | Database attivo, anche per backup e restore cutover |
| `VERBOFLEX_REDIS_DB` | `0` | Database Redis usato da API, worker e scheduler |

Il file di configurazione deve contenere valori per `VERBOFLEX_POSTGRES_PASSWORD`, `VERBOFLEX_JWT_SECRET_KEY` e `VERBOFLEX_BITBUCKET_TOKEN_ENCRYPTION_KEYRING`. Se cambiano i segreti o il file viene sostituito atomicamente, ricreare il container backup insieme agli altri servizi: il bind mount deve vedere il file aggiornato. Le credenziali PostgreSQL del servizio sono derivate dal medesimo `--env-file`; non montare la configurazione di un ambiente diverso. Il ruolo PostgreSQL deve poter leggere il database e creare/rimuovere i propri database di verifica; il ruolo inizializzato dallo stack Docker dispone di tali diritti.

## Stato e operazioni manuali

```sh
# Elenco: id, data, schema, dimensioni, checksum e conteggi; nessun segreto.
vf exec -T backup python3 /opt/verboflex/database_backup.py list

# Nuova copia immediata, con restore di verifica e retention.
vf exec -T backup python3 /opt/verboflex/database_backup.py run

# Controllo di freschezza: exit 0 sano, exit 1 assente, fallito o oltre 36 ore.
vf exec -T backup python3 /opt/verboflex/database_backup.py health

# Nuova verifica completa di una copia già presente.
# Sostituire BACKUP_ID con l'identificativo esatto restituito da list.
BACKUP_ID='vf-YYYYMMDDTHHMMSSZ-xxxxxxxx'
vf exec -T backup python3 /opt/verboflex/database_backup.py verify "$BACKUP_ID"
```

Il controllo Docker diventa unhealthy dopo due controlli falliti. `status.json` riporta l'ultimo esito con un codice di errore privo di segreti; i log indicano successo/fallimento e id. Non è configurata una notifica email o esterna. Un lock esclude backup, verifica e restore concorrenti sullo stesso archivio. I file `.partial-*` non sono backup validi: un arresto forzato può lasciarli, insieme a un database temporaneo `vf_restore_*`; ispezionarli prima di un'eventuale rimozione manuale, senza usare cancellazioni per prefisso.

## Restore senza sovrascritture

Il restore è **su richiesta**, mai un ripristino giornaliero automatico. Scegliere un backup da `list`; verificare che provenga dal proprio ambiente. Il comando verifica i checksum di database e configurazione, crea un database nuovo da template0, esegue il restore transazionale e confronta revisione e tutti i conteggi con il manifest.

```sh
BACKUP_ID='vf-YYYYMMDDTHHMMSSZ-xxxxxxxx'
RESTORE_DB='vf_restore_recovery_20261003'
vf exec -T backup python3 /opt/verboflex/database_backup.py \
  restore "$BACKUP_ID" --database "$RESTORE_DB"
```

Sono accettati soltanto nomi `vf_restore_` seguiti da 1–40 lettere minuscole, cifre o underscore. Il database attivo e ogni destinazione già esistente sono rifiutati. Non esistono opzioni `--force`, `--clean` o sovrascrittura. Un restore manuale interrotto può lasciare il nuovo database incompleto: non collegarvi l'applicazione, scegliere un nuovo nome dopo avere risolto il problema. Il comando di sola verifica elimina invece esclusivamente il database casuale che ha appena creato.

Dopo perdita dei volumi Docker: recuperare in modo privato il `deployment.env` del backup come configurazione dell'ambiente, avviare PostgreSQL con quella configurazione, poi usare `vf run --rm -T --no-deps backup restore ...`. Il backup non contiene ruoli globali PostgreSQL: lo stack ricrea il ruolo applicativo e il restore gli assegna gli oggetti. Non ripristinare archivi di provenienza sconosciuta: il contenuto di un dump viene eseguito da PostgreSQL.

## Passaggio controllato al database ripristinato

La creazione del database di recupero non cambia l'applicazione. Il passaggio richiede una finestra di manutenzione:

1. Fermare frontend, backend, worker, scheduler e backup con `vf stop frontend backend worker scheduler backup`. Conservare database e volumi originali per il rollback; non usare `down -v`.
2. Annotare i precedenti `VERBOFLEX_POSTGRES_DB` e `VERBOFLEX_REDIS_DB` e conservare una copia privata dell'ambiente. Recuperare dal bundle il keyring completo usato dalla copia; mantenere coerenti anche JWT e credenziali PostgreSQL. Il file `deployment.env` **non viene mai eseguito o applicato automaticamente**.
3. Impostare nel file privato `VERBOFLEX_POSTGRES_DB` al nuovo database verificato. Scegliere per `VERBOFLEX_REDIS_DB` un indice Redis inutilizzato e verificarlo con `vf exec -T redis redis-cli -n INDICE DBSIZE` (deve essere 0). Non riutilizzare code Celery vecchie e non eseguire `FLUSHALL`: potrebbero appartenere al database originale o ad altri servizi.
4. Con backend e worker ancora spenti, usare un'immagine applicativa compatibile con la revisione del backup. Eseguire eventuali migrazioni con `vf run --rm -T --no-deps backend alembic upgrade head`, dopo averne verificato la compatibilità. I manifest di pulizia precedenti non sono validi per il database ripristinato.
5. Avviare soltanto backend e frontend (`vf up -d --no-deps --wait backend frontend`) e verificare accesso, prodotti, traduzioni e riepiloghi. Riconciliare operazioni import/submission che risultavano in corso nel backup prima di riattivare i worker: il dump è coerente, ma non annulla commit/PR già eseguiti sui provider dopo la copia. Non reinviare automaticamente operazioni remote.
6. Quando i dati e le operazioni sospese sono stati verificati, ricreare worker, scheduler e backup (`vf up -d --no-deps worker scheduler backup`). Eseguire una nuova copia manuale e verificare che il suo `source_database` sia il nuovo database. In caso di problemi, fermare i servizi e tornare alle precedenti impostazioni database/Redis; non eliminare i dati originali.

## Protezione e limiti

Directory 0700, file 0600, output atomico, SHA-256 e restore reale. I backup sono esclusi da Git; per percorsi personalizzati fuori dalla directory predefinita, non collocarli fra i file versionati. La configurazione archiviata contiene segreti e il dump include account, sessioni e credenziali provider cifrate: mantenere insieme il keyring necessario, su storage privato. I file non sono cifrati dal programma; usare un volume cifrato e una copia remota cifrata con una destinazione esplicitamente configurata se serve protezione dalla perdita del disco/Mac.

Questa soluzione protegge dalla cancellazione dei volumi Docker e consente un recupero a una copia giornaliera, non a un istante arbitrario. Redis, certificati TLS locali e immagini Docker non sono archiviati: Redis richiede una coda nuova al cutover, i certificati possono essere rigenerati e le immagini ricostruite dal commit compatibile. Per grandi installazioni, replica/off-site e ripristino continuo tramite WAL richiedono una strategia aggiuntiva.

Il restore giornaliero di verifica richiede spazio temporaneo per una copia completa del database e può caricare disco/CPU. Eventuali fallimenti o timeout lasciano il backup precedente utilizzabile. Le copie manuali entrano nelle stesse 14 posizioni di retention; non è garantita una finestra di 14 giorni se si eseguono più copie al giorno.

Riferimenti: [pg_dump PostgreSQL 18](https://www.postgresql.org/docs/18/app-pgdump.html), [pg_restore PostgreSQL 18](https://www.postgresql.org/docs/18/app-pgrestore.html).

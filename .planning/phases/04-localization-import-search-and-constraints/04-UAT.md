---
status: testing
phase: 04-localization-import-search-and-constraints
source: [04-VERIFICATION.md]
started: 2026-09-06T12:26:20Z
updated: 2026-09-06T12:26:20Z
---

## Current Test

number: 1
name: Import e refresh da Bitbucket reale
expected: |
  Su repository e branch usa-e-getta approvati, importare il mapping pubblicato
  e verificare testo, commit e percorso del file. Dopo una modifica esterna a
  una traduzione e un refresh, soltanto il valore interessato torna Draft;
  UUID, storico e vincoli restano stabili e gli altri valori conservano lo stato.
awaiting: user response

## Environment

Gli automatismi sono verdi sulla sorgente con digest
`sha256:2df3766ead7f1aea3597a8ad8b99205f14508a4189109996149265a163017b3a`.
Lo smoke Docker ha usato uno stack isolato con provider Bitbucket TLS simulato,
poi ripulito. L'applicazione preesistente su localhost:8080 non è stata aggiornata
da questa verifica. Prima delle prove preparare la build verificata e identificare
esplicitamente repository/branch di test; non usare dati di produzione e non
riportare credenziali nei risultati. Nessuna prova manuale è stata dichiarata passata.

## Tests

### 1. Import e refresh da Bitbucket reale

expected: Su repository/branch usa-e-getta approvati, l'import tramite mapping pubblicato mostra testo e provenienza esatti (commit e file). Modificare esternamente un valore e aggiornare: quel valore torna Draft, UUID/storico/vincoli restano stabili e i valori non interessati conservano lo stato. Annotare i risultati osservati senza credenziali.
result: [pending]

### 2. Zoom nativo, tastiera e screen reader

expected: A larghezza desktop e stretta, anche con zoom reale del browser al 200%, percorrere ricerca, altre righe, dettaglio e Indietro; verificare dialoghi dei vincoli, errori e conflitti. Non compaiono scorrimento orizzontale della pagina o azioni tagliate. Focus e ritorno alla riga/controllo sono corretti; un vero screen reader annuncia liste e dialoghi in modo comprensibile, anche durante operazioni pendenti. Registrare browser e tecnologia assistiva usati.
result: [pending]

### 3. Nessuna rinomina dedotta fra chiavi

expected: Dopo un refresh con una chiave cancellata e una nuova con testo uguale, le due identità restano separate. Ricerca, dettaglio e presentazione persistita non suggeriscono una rinomina o una fusione dedotta da testo uguale/simile o vicinanza del percorso. Registrare esplicitamente il giudizio su questa regola del piano 04-11.
result: [pending]

### 4. Traduzioni oltre limite sempre leggibili

expected: Il dettaglio rende accessibile tutto il contenuto oltre limite e consente di conservarlo in Draft. Errori e rimozione dei vincoli non presentano l'eliminazione distruttiva della traduzione come necessaria. Il testo non è nascosto né troncato come unica rappresentazione. Questa fase non introduce l'editor: si verifica la presentazione e conservazione del valore importato. Registrare esplicitamente il giudizio sulla regola del piano 04-18.
result: [pending]

## Summary

total: 4
passed: 0
issues: 0
pending: 4
skipped: 0
blocked: 0

## Gaps


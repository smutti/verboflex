---
status: resolved
trigger: "Applicare i fix di importazione per repository reali senza aggiungere GitHub come connessione e rimuovere il limite massimo di lingue gestibili."
created: 2026-09-09
updated: 2026-09-09
resolved: 2026-09-09
diagnose_only: false
---

# Symptoms

- expected: Repository Bitbucket con layout Android XML, Qt TS, JSON annidato e iOS `.strings` reali vengono rilevati e importati automaticamente; il numero di lingue non ha un tetto applicativo dedicato.
- actual: L'autodiscovery restituisce zero layout per Android quando nella resource root sono presenti XML non-localizzazione, per JSON i18next annidati e per Qt TS con strutture reali o più di 32 lingue. `Base.lproj` viene ignorato e le varianti regionali Android/Qt possono essere rifiutate.
- error: `No supported localization layout was found in this source branch.`
- timeline: Riprodotto il 2026-09-09 contro repository GitHub pubblici usati come fixture esterne; i parser canonici accettano parte dei contenuti che il preview detector rifiuta.
- reproduction: Eseguire `detect_preview_layouts` sui file di `multilocale/android-multi-language-app-example`, `i18next/react-i18next`, `Dman95/SASM`, `flaviotordini/minitube` e `CreatureSurvive/Project-Localizations` alle revisioni registrate nell'evidenza del debug.

# Current Focus

- hypothesis: Confirmed — Base.lproj and the explicit configured base-locale peer were assigned the same canonical identity before duplicate quarantine, so both were removed.
- test: End-to-end regression covers preview candidate creation, canonical input construction, duplicate diagnostics, quarantine, reversed input order, and Base-only fallback.
- expecting: Explicit base-locale files deterministically shadow Base.lproj for the same side/layout; Base remains active only when the explicit peer is absent.
- next_action: hand off the resolved residual fix
- reasoning_checkpoint: GREEN in focused and broad suites; the live Tranquil snapshot retains all 53 values across its three layouts with no parser issues.
- tdd_checkpoint: green_verified

# Evidence

- timestamp: 2026-09-09T00:00:00+02:00
  observation: Android `strings.xml` isolati producono 9 lingue e 99 valori, mentre l'intera `res` con XML non-localizzazione produce zero candidati.
- timestamp: 2026-09-09T00:00:01+02:00
  observation: JSON i18next annidato produce zero candidati preview ma 2 lingue e 8 valori nel parser canonico.
- timestamp: 2026-09-09T00:00:02+02:00
  observation: Qt SASM produce zero candidati come insieme; il parser canonico importa 10 file, 9 lingue e 1780 valori, mentre due varianti regionali restano ambigue.
- timestamp: 2026-09-09T00:00:03+02:00
  observation: iOS Tranquil rileva tre layout e 53 valori solo da `en.lproj`; i peer `Base.lproj` non vengono associati alla lingua base.
- timestamp: 2026-09-09T00:00:04+02:00
  observation: Minitube contiene 52 file Qt nella root analizzata e supera il tetto preview di 32 lingue.
- timestamp: 2026-09-09T00:00:05+02:00
  observation: TDD RED — targeted preview suite reports 9 failures and 175 passes for mixed Android XML plus en-rUS, nested i18next JSON, canonical Qt metadata, Base.lproj, and 33-language candidates.
- timestamp: 2026-09-09T00:00:06+02:00
  observation: GREEN — 295 focused/architecture tests pass; Ruff and strict mypy pass; the full suite excluding Redis-dependent worker smoke passes 1688 tests.
- timestamp: 2026-09-09T00:00:07+02:00
  observation: Live snapshots now detect Android (19 localization files, 9 languages), i18next JSON (2 languages), SASM Qt (12 files, 11 canonical languages), iOS Base/en (3 layouts), and Minitube Qt (52 files and 52 languages).
- timestamp: 2026-09-09T00:00:08+02:00
  observation: The only full-suite failures are two pre-existing worker smoke tests because their test Redis endpoint 127.0.0.1:56379 is unavailable; 1686 tests passed in that run and all code-related failures were subsequently corrected.
- timestamp: 2026-09-09T00:00:09+02:00
  observation: Residual TDD RED — preview candidate with Base.lproj plus en.lproj reaches duplicate quarantine with no issues but returns zero canonical values instead of the explicit base-language peer.
- timestamp: 2026-09-09T00:00:10+02:00
  observation: Residual GREEN — Tranquil imports 1 InfoPlist, 36 Localizable, and 16 Preferences values from the explicit en peers; focused suite passes 150 tests and broad non-worker suite passes 1690 tests.

# Eliminated

- hypothesis: Il provider GitHub è necessario per correggere l'importazione.
  reason: I problemi sono riproducibili passando snapshot locali agli stessi detector/parser provider-independent; Bitbucket resta l'unico provider v1.

# Resolution

- root_cause: Preview detectors duplicated stricter format grammars, path normalization and schema validation imposed unsupported restrictions, and Base.lproj collided with an explicit base-locale peer so duplicate quarantine removed both representations.
- fix: Reused canonical parsing for preview, added nested/locale-aware detection, removed dedicated language caps, and introduced deterministic iOS fallback precedence where the explicit configured base-locale peer shadows Base.lproj only after the original file/byte budgets are validated.
- verification: Initial TDD RED 9 failed/175 passed plus residual Base/en RED; GREEN 295 initial targeted tests, 150 residual focused tests, full non-worker backend 1690 passed, Ruff and strict mypy passed, and live Tranquil retained 53 values across three layouts without issues.
- files_changed: backend/src/verboflex/localization/{preview/core.py,preview/android_xml.py,preview/json.py,preview/qt_ts.py,preview/ios_strings.py,importing/android_xml.py,importing/ios_strings.py,importing/registry.py,duplicate_diagnostics.py}; backend/src/verboflex/{schemas/previews.py,services/preview_jobs.py}; focused backend tests; regenerated frontend OpenAPI/client artifacts.

# Code keys and Compose capture review

Review date: 12 October 2026. Scope: the implementation on
`codex/code-keys-compose-preview`, including the 1953 opt-in capture integration.
This is a self-review with executable regression checks, not an independent review.
The baseline commit is `1650ac7803bfeae06cbd9db9dd8e135ab8a68652`.
Final changed-code snapshot (79 changed/new non-Markdown files): SHA-256
`72e5e3e8a5cfd4f2d32d369f282e44c3240c45ab8b9a9923b3af907ba9b0ee17`.
Per-file hashes are retained in `/tmp/verboflex-review-source.json`.
That historical snapshot predates the Mac relay and server deployment additions.

## Follow-up verification, 13 October 2026

The dedicated Celery screenshot worker completed two real, on-demand Compose
captures from a fresh immutable checkout through the authenticated Mac relay.
Both produced a validated 1280 × 800 PNG; the requests took 81.4 and 55.8 seconds.
The direct translation page displays the registered preview in its expandable
"Screenshots and code references" panel. The final focused parser/join/runner
suite, including the Mac relay regressions, passed all 51 tests. Ruff, mypy and
the generated MCP contract check also passed. Server rendering is verified
separately after deployment; these results do not certify its Linux environment.

## Findings corrected

| Priority | Finding and user impact | Correction and evidence |
| --- | --- | --- |
| P1 | Untrusted builds could exhaust host disk through log spools or the writable output bind mount, despite container resource limits. | Worker logs go to DEVNULL; Docker uses `--log-driver=none`. Host mounts are read-only and the PNG returns through a stream capped at 8 MiB with a deadline. Real subprocess, hostile-output and timeout regressions, real Docker input/stream transport and real Compose PNG streaming verify the boundaries. |
| P2 | Java invocation extraction discarded the receiver, so a configured `demo.i18n.Translator.text` call silently omitted its keys. | `_call` preserves the receiver before import expansion. The new parser regression failed before the fix and passes afterwards; it also rejects unrelated `Other.text`. |
| P2 | Reconnect reloaded the job but did not retry a failed PNG GET when job ID/state remained unchanged. | The image effect includes the reconnect generation. A failing component test and an actual browser network abort reproduce the defect; both recover the same image without another capture request. |
| P2 | Direct translation URLs had no screenshot controls; only the search context panel offered them. | The detail page now exposes lazy screenshot controls with dirty-edit blocking and the saved proposal version. The built-stack E2E discovered this defect, and the new direct-route component regression was observed failing before the fix. |
| P2 | Under umask 077 the container input remained mode 0600, unreadable by the runner UID. The previous exchange directory also relied on host temporary-directory ancestry for privacy. | A mode-0700 parent contains the read-only bind-mounted input, explicitly mode 0644. The restrictive-umask regression failed before the fix. There is no writable host exchange directory. |

## End-to-end execution

The full documented smoke passed after the fixes:

```sh
PHASE8_HTTP_SETUP=1 PHASE7_EVIDENCE_DIR=/tmp/verboflex-review-e2e-verified \
  bash tools/phase7_smoke.sh
```

It built the current images and used disposable PostgreSQL, Redis, Celery, scheduler,
frontend and a TLS repository provider. Existing assertions passed for five successful
submission groups, seventeen failure/recovery groups, exact provider effects and file
bytes, immutable receipts, revoked sessions, keyboard use, 320-pixel layouts and native
200% zoom. Cleanup passed; the development stack was preserved.

The added `code-capture` stage is now part of that command. It verifies HTTP-only
mapping setup, code-only Kotlin/Java extraction, a separate translation repository,
missing/orphan key reporting, no eager capture, saving a proposal, actual queued worker
execution, authenticated PNG delivery, nonmember denial, idempotency, image reconnect
and direct-route reload. Provider mutation count stays zero.

The Android renderer is an explicit synthetic boundary in this application E2E. Its
PNG contains the selected saved translation, checked separately from browser decoding.
It does not certify Android compilation or the production sandbox image. The real
1953 Compose rendering evidence remains in [the implementation report](code-keys-compose-evidence.md).

Artifacts: `/tmp/verboflex-review-e2e-verified.log`,
`/tmp/verboflex-review-e2e-verified/code-capture-e2e.json` and
`/tmp/verboflex-review-e2e-verified/code-capture-width320.png`.

## Historical Playwright baseline

Five historical fixture-driven suites were also run against the current production
frontend build: `admin-configuration`, `change-sets`, `notifications`,
`review-workspace` and `translations`. Result: **34 passed, 32 failed** (66 tests,
10.5 minutes). Building the baseline commit's frontend separately and running the
same suites gives **the identical 32 failed test identities and 34 passes**. There
are no additional failures in those suites from this change; they are nevertheless
not green and are not presented as passing verification.

| Historical suite | Passed | Failed (also on baseline) |
| --- | ---: | ---: |
| Administration | 16 | 14 |
| Change sets | 1 | 7 |
| Notifications | 4 | 0 |
| Review workspace | 3 | 0 |
| Translations | 10 | 11 |

The failures cover older workspace/navigation, administration, change-set and
translation fixtures. Their reconciliation is separate from the documented application
smoke baseline; no historical assertion was weakened, removed or skipped. The sixth
historical suite, `auth-shell`, was not run: it requires its separate Phase 1 seeded
account/credentials and checks that historical shell. Current authentication is
exercised by the built-stack smoke, including revoked-session denial.

Artifacts: `/tmp/verboflex-review-playwright-final.log`,
`/tmp/verboflex-review-playwright-baseline-all.log` and
`/tmp/verboflex-review-playwright-comparison.json` (the `new_failures` list is empty).

## Scope of assurance

Additional current checks: **1,043 frontend tests passed** (62 files), **47 focused
parser/join/capture/runner tests passed**, and **40 MCP tests passed**. Ruff, mypy
(211 backend source files), ESLint, TypeScript and production builds pass. One existing
preview-poll Vitest test timed out during a heavily concurrent intermediate run; the
complete rerun passed without changing that test or its timeout.

The complete backend gate passed **3,460 tests in 767.93 seconds**, using disposable
PostgreSQL 18, Redis and Celery (`/tmp/verboflex-review-backend-final/pytest.xml`).
That run includes the final backend worker log fix. The last standalone host-transport
hardening and its additional stdout-budget test were completed after full-suite
collection; they are verified by the final 47-test focused run, real Docker transport
and real Compose streaming checks above. No claim is made that the extra transport
test was included in the 3,460 count.

The host transport was exercised with `tools/verify_compose_transport.py` and the
cached image `python@sha256:c3e521df8b2b498a7a682e7e18676771cb80c6b75b8699af886b2d554ce40151`.
The subprocess tests reject output beyond 8 MiB and a silent stalled renderer. Two
temporary in-memory mutants (removed output limit, extended deadline) were killed by
those assertions; source files were never mutated. This is narrow negative evidence,
not a replacement for the earlier incomplete mutation gate.

The real 1953 preview was rendered again in the disposable Android workspace (26
seconds, 74 Gradle tasks: 5 executed, 7 from cache, 62 up-to-date). The new `--emit-png`
path was then exercised with a fresh render: streamed and file PNG bytes are identical,
19,707 bytes, 1280 × 800, SHA-256
`64ff690511c611731817630acc5ac6116e67069ff18a809359e6c32daee5e34d`. The synthetic title
override is visibly present. This uses the explicit development workspace, not the
unvalidated production Android container.

Reproduce the portable runner checks with:

```sh
backend/.venv/bin/pytest backend/tests/unit/localization/test_code_keys.py \
  backend/tests/unit/localization/test_code_key_join.py \
  backend/tests/unit/localization/test_compose_capture.py \
  backend/tests/unit/localization/test_compose_runner.py -q
backend/.venv/bin/python tools/verify_compose_transport.py \
  --image python@sha256:c3e521df8b2b498a7a682e7e18676771cb80c6b75b8699af886b2d554ce40151
```

The application-specific production Android image is still unvalidated. The strict
coverage/mutation limitations documented in the implementation report remain; neither
gate was promoted to passing by this review. No commits, remote writes or deployment
were performed. Repository code continues to run outside the API process, and the
new screenshot endpoints retain current product-membership checks.

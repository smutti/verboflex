#!/usr/bin/env bash
set -euo pipefail
umask 077
PHASE5_SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
case "${1:-}" in
  --dry-run)
    printf '%s\n' \
      'Phase 5 disposable built-stack smoke extends the audited Phase 4 lifecycle.' \
      'Unique Compose project, isolated database and volumes; Alembic head plus worker health are mandatory.' \
      'Built browser saves and reloads a Unicode proposal and a mention comment.' \
      'An authenticated recipient stream invalidates the bell; REST remains authoritative and exact-comment focus marks the origin read.' \
      'Cleanup targets the exact owned Compose project, volumes, images and private runtime only.'
    exit 0 ;;
  '') ;;
  *) printf 'phase5 smoke: unknown option\n' >&2; exit 2 ;;
esac
export PHASE4_BROWSER_EXTENSION="$PHASE5_SCRIPT_DIR/phase5_smoke_browser.mjs"
exec "$PHASE5_SCRIPT_DIR/phase4_smoke.sh"

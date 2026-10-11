#!/usr/bin/env bash
set -euo pipefail
umask 077
PHASE7_SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
if [ "$#" -gt 1 ]; then exit 2; fi
case "${1:-}" in
  --dry-run)
    printf '%s\n' \
      'Phase 7 disposable built-stack TLS smoke: browser API PostgreSQL Redis Celery worker.' \
      'UUID-only queue; exact branch/commit/PR effects, bytes and immutable database receipts.' \
      'Lost response, broker loss, killed worker, delayed effects and credential recovery.' \
      'Keyboard and native browser zoom 200%; separate 320 CSS-pixel viewport.' \
      'Private temporary credentials; bounded commands; exact owned-resource cleanup.'
    exit 0 ;;
  --review-only) export PHASE4_PROFILE=6 ;;
  '') export PHASE4_PROFILE=7 ;;
  *) printf 'phase7 smoke: unknown option\n' >&2; exit 2 ;;
esac
export PHASE4_BROWSER_EXTENSION="$PHASE7_SCRIPT_DIR/phase7_smoke_browser.mjs"
exec bash "$PHASE7_SCRIPT_DIR/phase4_smoke.sh"

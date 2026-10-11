#!/usr/bin/env bash
set -euo pipefail
umask 077
PHASE6_SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
if [ "$#" -gt 1 ]; then exit 2; fi
case "${1:-}" in
  --dry-run)
    printf '%s\n' \
      'Phase 6: unique isolated built Compose/TLS lifecycle, bounded commands and owned cleanup.' \
      'Real OAuth, preview, confirmation, publication and five canonical imports (including separate keys).' \
      'Browser edits, saves and approves complete structured proposals in all four formats, including UTF-16 iOS.' \
      'Built worker runs production prepare/revalidate; exact independent golden bytes and unchanged localization/proposal rows.' \
      'Refuse stale direct and separate keys heads, modified raw bytes, mixed markup and a separately verified duplicate snapshot.' \
      'Require actual metadata/raw reads and zero resource mutations; OAuth token exchange is allowed.'
    exit 0 ;;
  '') ;;
  *) exit 2 ;;
esac
unset PHASE4_BROWSER_EXTENSION
export PHASE4_PROFILE=6
exec bash "$PHASE6_SCRIPT_DIR/phase4_smoke.sh"

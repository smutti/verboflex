#!/usr/bin/env bash
set -euo pipefail
ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/../.." && pwd)
output=$(bash "$ROOT/tools/phase4_smoke.sh" --dry-run)
for required in postgres redis backend worker frontend pg_trgm UUID android_xml qt_ts json ios_strings '180 seconds' '120 seconds' 'PUT/DELETE' 'four roles' 'TLS' 'cleanup'; do
  [[ "$output" == *"$required"* ]] || { printf 'Missing smoke dry-run contract: %s\n' "$required"; exit 1; }
done
if [[ "$output" =~ (https?://|access_token|client_secret|translated_text) ]]; then
  printf 'Dry run exposed a protected field\n'; exit 1
fi
if bash "$ROOT/tools/phase4_smoke.sh" --unknown >/dev/null 2>&1; then
  printf 'Unknown smoke option accepted\n'; exit 1
fi
printf 'phase4 smoke dry-run contract: PASS\n'

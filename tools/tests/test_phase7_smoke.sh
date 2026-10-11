#!/usr/bin/env bash
set -euo pipefail
ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/../.." && pwd)
output=$(bash "$ROOT/tools/phase7_smoke.sh" --dry-run)
for required in TLS UUID exact Redis worker '200%' 320 cleanup; do
  [[ "$output" == *"$required"* ]] || exit 1
done
if [[ "$output" =~ (https?://|access_token|client_secret|translated_text) ]]; then exit 1; fi
if bash "$ROOT/tools/phase7_smoke.sh" --unknown >/dev/null 2>&1; then exit 1; fi
bash "$ROOT/tools/tests/test_phase4_smoke.sh"
printf 'phase7 smoke lifecycle contract: PASS\n'

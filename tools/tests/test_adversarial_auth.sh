#!/usr/bin/env bash
set -euo pipefail

repo_root=$(git rev-parse --show-toplevel)

grep -Fq '__Host-verboflex_refresh' "$repo_root/tools/adversarial_auth.sh"
output_file=$(mktemp)
trap 'rm -f "$output_file"' EXIT

legacy_collision=$(
  cd "$repo_root/backend"
  uv run python - <<'PY'
import base64

token = "header.payload._w"
legacy_tampered = f"{token[:-1]}{'y' if token.endswith('x') else 'x'}"
original_signature = base64.urlsafe_b64decode(f"{token.rsplit('.', 1)[1]}==")
tampered_signature = base64.urlsafe_b64decode(
    f"{legacy_tampered.rsplit('.', 1)[1]}=="
)
if token == legacy_tampered or original_signature != tampered_signature:
    raise SystemExit("fixture does not demonstrate the legacy base64url collision")
print("legacy textual mutation preserved signature bytes")
PY
)
grep -Fq 'legacy textual mutation preserved signature bytes' <<<"$legacy_collision"

if ! "$repo_root/tools/adversarial_auth.sh" --self-test >"$output_file" 2>&1; then
  printf 'expected adversarial-auth self-tests to pass; output follows:\n' >&2
  sed -n '1,120p' "$output_file" >&2
  exit 1
fi

grep -Fq 'adversarial auth self-test: PASS' "$output_file"
grep -Fq 'tampered signature bytes differ: PASS' "$output_file"

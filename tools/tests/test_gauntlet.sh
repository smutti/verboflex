#!/usr/bin/env bash
set -euo pipefail

repo_root=$(git rev-parse --show-toplevel)
output_file=$(mktemp)
trap 'rm -f "$output_file"' EXIT

if ! "$repo_root/tools/gauntlet.sh" --preflight >"$output_file" 2>&1; then
  printf 'expected gauntlet preflight to pass; output follows:\n' >&2
  sed -n '1,120p' "$output_file" >&2
  exit 1
fi

grep -Fq 'gauntlet preflight: PASS' "$output_file"
grep -Fq '"$SOURCE_STATE" --verify-review-closed' "$repo_root/tools/gauntlet.sh"
grep -Fq '"$SOURCE_STATE" --verify-review-source' "$repo_root/tools/gauntlet.sh"

"$repo_root/tools/gauntlet.sh" --self-test-openapi-control >"$output_file" 2>&1
grep -Fq 'OpenAPI drift negative control: PASS' "$output_file"

"$repo_root/tools/gauntlet.sh" --self-test-staging-layer >"$output_file" 2>&1
grep -Fq 'staging/adversarial layer contract: PASS' "$output_file"

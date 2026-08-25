#!/usr/bin/env bash
set -euo pipefail

repo_root=$(git rev-parse --show-toplevel)
output_file=$(mktemp)
trap 'rm -f "$output_file"' EXIT

if ! "$repo_root/tools/source_state.sh" --self-test-manifest >"$output_file" 2>&1; then
  printf 'expected source-state self-tests to pass; output follows:\n' >&2
  sed -n '1,120p' "$output_file" >&2
  exit 1
fi

grep -Fq 'source manifest self-test: PASS' "$output_file"

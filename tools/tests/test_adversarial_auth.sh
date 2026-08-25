#!/usr/bin/env bash
set -euo pipefail

repo_root=$(git rev-parse --show-toplevel)
output_file=$(mktemp)
trap 'rm -f "$output_file"' EXIT

if ! "$repo_root/tools/adversarial_auth.sh" --self-test >"$output_file" 2>&1; then
  printf 'expected adversarial-auth self-tests to pass; output follows:\n' >&2
  sed -n '1,120p' "$output_file" >&2
  exit 1
fi

grep -Fq 'adversarial auth self-test: PASS' "$output_file"

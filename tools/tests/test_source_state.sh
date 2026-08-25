#!/usr/bin/env bash
set -euo pipefail

repo_root=$(git rev-parse --show-toplevel)
output_file=$(mktemp)
runbook="$repo_root/docs/phase-01-smoke.md"
runbook_backup=$(mktemp)
cp "$runbook" "$runbook_backup"
cleanup() {
  cp "$runbook_backup" "$runbook"
  rm -f "$output_file" "$runbook_backup"
}
trap cleanup EXIT INT TERM

if ! "$repo_root/tools/source_state.sh" --self-test-manifest >"$output_file" 2>&1; then
  printf 'expected source-state self-tests to pass; output follows:\n' >&2
  sed -n '1,120p' "$output_file" >&2
  exit 1
fi

grep -Fq 'source manifest self-test: PASS' "$output_file"

while IFS='|' read -r directive category pathspec _reason; do
  [ "$directive" = "include" ] || continue
  if [ -z "$(git -C "$repo_root" ls-files --cached --others --exclude-standard -- "$pathspec")" ]; then
    printf 'include rule resolved no paths: %s (%s)\n' "$pathspec" "$category" >&2
    exit 1
  fi
done <"$repo_root/tools/source_manifest.txt"

printf '\nsource-binding negative control\n' >>"$runbook"
set +e
"$repo_root/tools/source_state.sh" --review-digest >"$output_file" 2>&1
digest_rc=$?
set -e
cp "$runbook_backup" "$runbook"
if [ "$digest_rc" -eq 0 ]; then
  printf 'TLS deployment runbook changed without invalidating the source digest\n' >&2
  exit 1
fi
grep -Fq 'included source has unstaged changes: docs/phase-01-smoke.md' "$output_file"

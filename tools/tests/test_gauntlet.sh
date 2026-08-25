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

for required_path in \
  src/verboflex/auth/login.py \
  src/verboflex/auth/password_change.py \
  src/verboflex/auth/principal.py \
  src/verboflex/auth/refresh_sessions.py; do
  grep -Fq "\"$required_path\"" "$repo_root/backend/pyproject.toml"
done

for required_suite in \
  tests/auth/test_login.py \
  tests/auth/test_password_change.py \
  tests/auth/test_refresh.py \
  tests/auth/test_logout.py \
  tests/api/test_me.py \
  tests/integration/test_refresh_concurrency.py; do
  grep -Fq "\"$required_suite\"" "$repo_root/backend/pyproject.toml"
done

"$repo_root/tools/gauntlet.sh" --self-test-candidate-contract >"$output_file" 2>&1
grep -Fq 'post-fix candidate contract: PASS' "$output_file"
grep -Fq -- '--post-fix-candidate' "$repo_root/tools/gauntlet.sh"

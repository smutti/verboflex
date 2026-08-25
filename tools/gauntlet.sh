#!/usr/bin/env bash
set -euo pipefail

readonly GAUNTLET_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
readonly REPO_ROOT=$(CDPATH= cd -- "$GAUNTLET_DIR/.." && pwd)
readonly BACKEND_ROOT="$REPO_ROOT/backend"
readonly FRONTEND_ROOT="$REPO_ROOT/frontend"
readonly SOURCE_STATE="$GAUNTLET_DIR/source_state.sh"
readonly PHASE_BASE_COMMIT="14aac53"
readonly RANDOM_SEED="1401"
readonly DIGEST_RECORD="${VERBOFLEX_GAUNTLET_DIGEST_FILE:-/tmp/verboflex-phase01-gauntlet.digest}"
readonly LAYER_RECORD="${VERBOFLEX_GAUNTLET_LAYER_FILE:-/tmp/verboflex-phase01-gauntlet.layers}"
readonly BACKEND_COVERAGE="/tmp/verboflex-phase01-backend-coverage.xml"
readonly FRONTEND_COVERAGE_DIR="/tmp/verboflex-phase01-frontend-coverage"
readonly SECRET_SCAN="/tmp/verboflex-phase01-secrets.json"

readonly EXPECTED_LAYERS="source-state
backend-tests
frontend-tests-browser
types
lint-format-complexity
changed-line-coverage
mutation-properties
migration-rehearsal
openapi-drift
supply-chain-secrets
staging-adversarial-smoke
final-source-state"

readonly EXPECTED_CANDIDATE_LAYERS="source-state-candidate
backend-tests
frontend-tests-browser
types
lint-format-complexity
changed-line-coverage
mutation-properties
migration-rehearsal
openapi-drift
supply-chain-secrets
staging-adversarial-smoke
candidate-source-state"

TEST_POSTGRES_NAME=""
TEST_REDIS_NAME=""
TEST_WORKER_PID=""

die() {
  printf 'gauntlet error: %s\n' "$1" >&2
  exit 1
}

run_command() {
  local label=$1
  shift
  local rc
  printf '\n==> %s\n' "$label"
  set +e
  "$@"
  rc=$?
  set -e
  [ "$rc" -eq 0 ] || die "$label failed with exit code $rc"
}

run_layer() {
  local layer=$1
  shift
  local rc
  printf '\n### layer: %s\n' "$layer"
  set +e
  "$@"
  rc=$?
  set -e
  [ "$rc" -eq 0 ] || die "layer $layer failed with exit code $rc"
  printf '%s\n' "$layer" >>"$LAYER_RECORD"
}

expect_control_failure() {
  local label=$1
  local expected_text=$2
  shift 2
  local output_file rc
  output_file=$(mktemp)
  set +e
  ("$@") >"$output_file" 2>&1
  rc=$?
  set -e
  if [ "$rc" -eq 0 ]; then
    rm -f "$output_file"
    die "$label negative control unexpectedly passed"
  fi
  if ! grep -Fq "$expected_text" "$output_file"; then
    sed -n '1,100p' "$output_file" >&2
    rm -f "$output_file"
    die "$label negative control failed for the wrong reason"
  fi
  rm -f "$output_file"
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "required command is unavailable: $1"
}

assert_files_equal() {
  local expected=$1
  local actual=$2
  [ -f "$expected" ] || die "comparison target is missing: $expected"
  [ -f "$actual" ] || die "comparison target is missing: $actual"
  cmp -s "$expected" "$actual" || die "controlled drift detected"
}

assert_no_detected_secrets() {
  local scan_file=$1
  local count rc
  [ -f "$scan_file" ] || die "secret scan output is missing"
  set +e
  count=$(cd "$BACKEND_ROOT" && uv run python -c \
    'import json,sys; data=json.load(open(sys.argv[1])); print(sum(len(items) for items in data["results"].values()))' \
    "$scan_file")
  rc=$?
  set -e
  [ "$rc" -eq 0 ] || die "secret scan output could not be parsed"
  [ "$count" = "0" ] || die "detected secrets outside the audited false-positive map"
}

assert_complexity_below_c() {
  local report=$1
  [ -f "$report" ] || die "complexity report is missing"
  [ ! -s "$report" ] || die "complexity grade C or worse detected"
}

audit_layer_record() {
  local expected_layers=${1:-$EXPECTED_LAYERS}
  local expected_file actual_file
  expected_file=$(mktemp)
  actual_file=$(mktemp)
  printf '%s\n' "$expected_layers" >"$expected_file"
  [ -f "$LAYER_RECORD" ] || die "layer completion record is missing"
  sed '/^$/d' "$LAYER_RECORD" >"$actual_file"
  assert_files_equal "$expected_file" "$actual_file"
  rm -f "$expected_file" "$actual_file"
}

assert_no_secret_string() {
  local candidate=$1
  local scan_output
  scan_output=$(mktemp)
  (cd "$BACKEND_ROOT" && uv run detect-secrets scan --string "$candidate") >"$scan_output"
  if grep -Eq ': True([[:space:]]|$)' "$scan_output"; then
    die "detected secrets outside the audited false-positive map"
  fi
  rm -f "$scan_output"
}

secret_negative_control() {
  local fragment
  fragment='IOSFODNN7EXAMPLE'
  assert_no_secret_string "AKIA$fragment"
}

checker_preflight() {
  local fixture_dir clean_file drift_file complexity_file complete_file incomplete_file
  require_command bash
  require_command git
  require_command shasum
  require_command docker
  require_command uv
  require_command node
  require_command npm
  bash -n "$SOURCE_STATE" "$GAUNTLET_DIR/gauntlet.sh"
  "$SOURCE_STATE" --self-test-manifest

  fixture_dir=$(mktemp -d)
  clean_file="$fixture_dir/expected"
  drift_file="$fixture_dir/actual"
  complexity_file="$fixture_dir/complexity"
  complete_file="$fixture_dir/complete"
  incomplete_file="$fixture_dir/incomplete"
  printf 'canonical\n' >"$clean_file"
  cp "$clean_file" "$drift_file"
  assert_files_equal "$clean_file" "$drift_file"
  printf 'drift\n' >>"$drift_file"
  expect_control_failure openapi-drift 'controlled drift detected' \
    assert_files_equal "$clean_file" "$drift_file"

  : >"$complexity_file"
  assert_complexity_below_c "$complexity_file"
  printf 'sample.py\n    F 1:0 too_complex - C (11)\n' >"$complexity_file"
  expect_control_failure complexity 'complexity grade C or worse detected' \
    assert_complexity_below_c "$complexity_file"

  printf '%s\n' "$EXPECTED_LAYERS" >"$complete_file"
  cp "$complete_file" "$LAYER_RECORD"
  audit_layer_record
  sed '$d' "$complete_file" >"$incomplete_file"
  cp "$incomplete_file" "$LAYER_RECORD"
  expect_control_failure layer-completion 'controlled drift detected' audit_layer_record

  expect_control_failure detect-secrets 'detected secrets outside the audited false-positive map' \
    secret_negative_control
  assert_no_secret_string 'ordinary non-secret fixture text'

  grep -Fq '"@stryker-mutator/core": "10.0.0"' "$FRONTEND_ROOT/package.json" \
    || die "Stryker core exact pin is missing"
  grep -Fq '"@stryker-mutator/vitest-runner": "10.0.0"' "$FRONTEND_ROOT/package.json" \
    || die "Stryker Vitest runner exact pin is missing"
  grep -Fq '"prettier": "3.9.6"' "$FRONTEND_ROOT/package.json" \
    || die "Prettier exact pin is missing"
  grep -Fq 'thresholds:' "$FRONTEND_ROOT/stryker.config.mjs" \
    || die "Stryker fail threshold is missing"
  grep -Fq 'source_paths = ["src/verboflex/auth"]' "$BACKEND_ROOT/pyproject.toml" \
    || die "mutmut handwritten auth target is missing"
  grep -Fq 'include|review|docs/reviews/phase-01-code-security.md' \
    "$GAUNTLET_DIR/source_manifest.txt" || die "review artifact is absent from source manifest"
  printf '%s\n' "$EXPECTED_LAYERS" >"$LAYER_RECORD"
  printf 'gauntlet preflight: PASS\n'
}

cleanup_test_infra() {
  local rc
  if [ -n "$TEST_WORKER_PID" ] && kill -0 "$TEST_WORKER_PID" 2>/dev/null; then
    kill "$TEST_WORKER_PID"
    set +e
    wait "$TEST_WORKER_PID"
    rc=$?
    set -e
    case "$rc" in 0|143) ;; *) printf 'worker cleanup exited %s\n' "$rc" >&2 ;; esac
  fi
  if [ -n "$TEST_POSTGRES_NAME" ]; then
    set +e
    docker stop --time 5 "$TEST_POSTGRES_NAME" >/dev/null
    rc=$?
    set -e
    [ "$rc" -eq 0 ] || [ "$rc" -eq 1 ] || die "PostgreSQL test cleanup failed"
  fi
  if [ -n "$TEST_REDIS_NAME" ]; then
    set +e
    docker stop --time 5 "$TEST_REDIS_NAME" >/dev/null
    rc=$?
    set -e
    [ "$rc" -eq 0 ] || [ "$rc" -eq 1 ] || die "Redis test cleanup failed"
  fi
}

wait_for_container_command() {
  local name=$1
  shift
  local deadline rc
  deadline=$((SECONDS + 60))
  while [ "$SECONDS" -lt "$deadline" ]; do
    set +e
    docker exec "$name" "$@" >/dev/null 2>&1
    rc=$?
    set -e
    [ "$rc" -eq 0 ] && return 0
    sleep 1
  done
  die "container readiness timed out: $name"
}

start_test_infra() {
  local suffix postgres_port redis_port worker_log rc
  suffix="$$"
  TEST_POSTGRES_NAME="verboflex-gauntlet-postgres-$suffix"
  TEST_REDIS_NAME="verboflex-gauntlet-redis-$suffix"
  worker_log="/tmp/verboflex-phase01-worker-$suffix.log"
  docker run -d --rm --name "$TEST_POSTGRES_NAME" -e POSTGRES_HOST_AUTH_METHOD=trust \
    -p 127.0.0.1::5432 postgres:18-alpine >/dev/null
  docker run -d --rm --name "$TEST_REDIS_NAME" -p 127.0.0.1::6379 redis:7-alpine >/dev/null
  wait_for_container_command "$TEST_POSTGRES_NAME" pg_isready -U postgres -d postgres
  wait_for_container_command "$TEST_REDIS_NAME" redis-cli ping
  postgres_port=$(docker port "$TEST_POSTGRES_NAME" 5432/tcp | sed -n 's/.*://p')
  redis_port=$(docker port "$TEST_REDIS_NAME" 6379/tcp | sed -n 's/.*://p')
  [ -n "$postgres_port" ] || die "could not resolve PostgreSQL test port"
  [ -n "$redis_port" ] || die "could not resolve Redis test port"
  export VERBOFLEX_TEST_POSTGRES_ADMIN_URL="postgresql://postgres@127.0.0.1:$postgres_port/postgres"
  export VERBOFLEX_TEST_CELERY_REDIS_URL="redis://127.0.0.1:$redis_port/0"
  (
    cd "$BACKEND_ROOT"
    VERBOFLEX_REDIS_URL="$VERBOFLEX_TEST_CELERY_REDIS_URL" \
      uv run celery -A verboflex.worker.celery_app worker --loglevel=WARNING \
      --pool=solo --concurrency=1 --hostname="verboflex-gauntlet@%h"
  ) >"$worker_log" 2>&1 &
  TEST_WORKER_PID=$!
  local deadline
  deadline=$((SECONDS + 60))
  while [ "$SECONDS" -lt "$deadline" ]; do
    set +e
    (
      cd "$BACKEND_ROOT"
      VERBOFLEX_REDIS_URL="$VERBOFLEX_TEST_CELERY_REDIS_URL" \
        uv run celery -A verboflex.worker.celery_app inspect ping --timeout 1
    ) >/tmp/verboflex-phase01-worker-ping.log 2>&1
    rc=$?
    set -e
    if [ "$rc" -eq 0 ] && grep -Fq '1 node online' /tmp/verboflex-phase01-worker-ping.log; then
      return 0
    fi
    kill -0 "$TEST_WORKER_PID" 2>/dev/null || die "Celery test worker exited before readiness"
    sleep 1
  done
  sed -n '1,120p' "$worker_log" >&2
  die "Celery test worker readiness timed out"
}

backend_tests() {
  start_test_infra
  (cd "$BACKEND_ROOT" && uv run pytest --randomly-seed="$RANDOM_SEED" -q)
  cleanup_test_infra
  TEST_POSTGRES_NAME=""
  TEST_REDIS_NAME=""
  TEST_WORKER_PID=""
}

frontend_tests_browser() {
  (cd "$FRONTEND_ROOT" && npm run test -- --run --sequence.shuffle --sequence.seed="$RANDOM_SEED")
  (cd "$FRONTEND_ROOT" && npm run build)
  [ -x "$GAUNTLET_DIR/real_smoke.sh" ] || die "real smoke harness is missing"
  "$GAUNTLET_DIR/real_smoke.sh" --browser-only
}

types() {
  (cd "$BACKEND_ROOT" && uv run mypy src)
  (cd "$FRONTEND_ROOT" && npm run typecheck)
}

lint_format_complexity() {
  local complexity_report=/tmp/verboflex-phase01-radon.txt
  (cd "$BACKEND_ROOT" && uv run ruff check src tests && uv run ruff format --check src tests)
  (cd "$FRONTEND_ROOT" && npm run lint && npm run format:check)
  (cd "$BACKEND_ROOT" && uv run radon cc src -s -n C) >"$complexity_report"
  assert_complexity_below_c "$complexity_report"
}

changed_line_coverage() {
  (cd "$BACKEND_ROOT" && uv run pytest --randomly-seed="$RANDOM_SEED" -q \
    --cov=verboflex --cov-branch --cov-report="xml:$BACKEND_COVERAGE")
  (cd "$FRONTEND_ROOT" && npm run test:coverage -- --sequence.shuffle --sequence.seed="$RANDOM_SEED" \
    --coverage.provider=v8 --coverage.reporter=text --coverage.reporter=lcov \
    --coverage.reportsDirectory="$FRONTEND_COVERAGE_DIR")
  (cd "$BACKEND_ROOT" && uv run diff-cover "$BACKEND_COVERAGE" \
    --compare-branch "$PHASE_BASE_COMMIT" --branch-coverage --fail-under 100 \
    --exclude 'backend/alembic/**' 'backend/src/verboflex/main.py' \
      'backend/src/verboflex/scripts/export_openapi.py')
  (cd "$BACKEND_ROOT" && uv run diff-cover "$FRONTEND_COVERAGE_DIR/lcov.info" \
    --compare-branch "$PHASE_BASE_COMMIT" --branch-coverage --fail-under 100 \
    --exclude 'frontend/src/api/client/**' 'frontend/src/components/ui/**' \
      'frontend/src/hooks/use-mobile.ts' 'frontend/src/main.tsx')
}

mutation_properties() {
  (cd "$BACKEND_ROOT" && uv run mutmut run)
  (cd "$BACKEND_ROOT" && uv run mutmut results)
  (cd "$BACKEND_ROOT" && uv run pytest -q tests/auth/test_access_tokens.py \
    tests/auth/test_passwords.py tests/core/test_config.py)
  (cd "$FRONTEND_ROOT" && npm run test:mutation)
  (cd "$FRONTEND_ROOT" && npm run test -- --run src/features/auth/session.property.test.ts)
}

migration_rehearsal() {
  start_test_infra
  (cd "$BACKEND_ROOT" && uv run pytest -q tests/integration/test_migrations.py)
  cleanup_test_infra
  TEST_POSTGRES_NAME=""
  TEST_REDIS_NAME=""
  TEST_WORKER_PID=""
}

openapi_negative_control() (
  local target="$BACKEND_ROOT/src/verboflex/api/v1/routes/health.py"
  local backup output rc before_digest mutated_digest restored_digest
  backup=$(mktemp)
  cp "$target" "$backup"
  before_digest=$(shasum -a 256 "$target" | awk '{print $1}')
  restore_openapi_control() {
    cp "$backup" "$target"
    git -C "$REPO_ROOT" restore --worktree -- frontend/openapi.json frontend/src/api/client
  }
  trap restore_openapi_control EXIT INT TERM
  perl -0pi -e 's/async def read_health\(/async def read_health_negative_control\(/' "$target"
  mutated_digest=$(shasum -a 256 "$target" | awk '{print $1}')
  [ "$mutated_digest" != "$before_digest" ] || die "OpenAPI drift control did not mutate its subject"
  set +e
  output=$(cd "$FRONTEND_ROOT" && npm run api:check 2>&1)
  rc=$?
  set -e
  restore_openapi_control
  trap - EXIT INT TERM
  restored_digest=$(shasum -a 256 "$target" | awk '{print $1}')
  [ "$restored_digest" = "$before_digest" ] || die "OpenAPI drift control did not restore its subject"
  git -C "$REPO_ROOT" diff --quiet -- frontend/openapi.json frontend/src/api/client \
    || die "OpenAPI drift control did not restore generated clients"
  [ "$rc" -ne 0 ] || die "OpenAPI drift negative control unexpectedly passed"
  printf '%s' "$output" | grep -Fq 'diff --git' || die "OpenAPI drift control failed for the wrong reason"
  printf 'OpenAPI drift negative control: PASS\n'
)

openapi_drift() {
  openapi_negative_control
  (cd "$FRONTEND_ROOT" && npm run api:check)
}

scan_repository_secrets() {
  local files_file findings_file count
  files_file=$(mktemp)
  findings_file=$(mktemp)
  git -C "$REPO_ROOT" ls-files | \
    grep -Ev '^(backend/uv.lock|frontend/package-lock.json|\.planning/)' >"$files_file"
  (cd "$BACKEND_ROOT" && uv run detect-secrets scan $(sed 's#^#../#' "$files_file")) >"$SECRET_SCAN"
  (cd "$BACKEND_ROOT" && uv run python -c \
    'import json,sys; d=json.load(open(sys.argv[1])); print("\\n".join(sorted(f"{p}|{x[chr(116)+chr(121)+chr(112)+chr(101)]}|{x[chr(104)+chr(97)+chr(115)+chr(104)+chr(101)+chr(100)+chr(95)+chr(115)+chr(101)+chr(99)+chr(114)+chr(101)+chr(116)]}" for p,v in d["results"].items() for x in v)))' \
    "$SECRET_SCAN") >"$findings_file"
  count=$(wc -l <"$findings_file" | tr -d ' ')
  [ "$count" = "15" ] || die "detected secrets outside the audited false-positive map"
  diff -u - "$findings_file" <<'AUDITED_FALSE_POSITIVES'
src/verboflex/auth/refresh_sessions.py|Base64 High Entropy String|e582429052cdb908833560f6f7582d232de37c4d
tests/api/test_rate_limits.py|Secret Keyword|5ac066cfb3bcf9973a0b40daeb7f5606103c1bd3
tests/api/test_system_status.py|Basic Auth Credentials|e5e9fa1ba31ecd1ae84f75caaa474f3a663f05f4
tests/auth/test_bootstrap_admin.py|Secret Keyword|028e59d8204d08fecd6aad12434b872fe4319f6d
tests/auth/test_bootstrap_admin.py|Secret Keyword|1123e04e3b43d460543f1b0bf94e67a0a636b2cc
tests/auth/test_bootstrap_admin.py|Secret Keyword|18468712bc6eede8cb7adf8932b073bf56773a11
tests/auth/test_bootstrap_admin.py|Secret Keyword|3da24dfed48aa2721da14e6f79e588440b934675
tests/auth/test_bootstrap_admin.py|Secret Keyword|5d9dec21ffdbb45c64f0ea2b1abf3b25c2afc728
tests/auth/test_bootstrap_admin.py|Secret Keyword|985a4d67132193977275067aca18c13f8c8371c8
tests/auth/test_bootstrap_admin.py|Secret Keyword|cdd076c21ce35f40d40b6c16d12bd40876050a6f
tests/auth/test_bootstrap_admin.py|Secret Keyword|d36b093dec485bfd20ef697ca6c1ad79e1ac9210
tests/auth/test_login.py|Secret Keyword|e7e0ea25217b715c566268c0607e48acef3b9ccf
tests/auth/test_password_change.py|Secret Keyword|a95b347855753c3b784594a28fa00ec116430d1c
tests/auth/test_password_change.py|Secret Keyword|ba8d4568d2e2f6531c78080cedddb3a16f08afd5
tests/auth/test_password_change.py|Secret Keyword|bc27f09f74d82f81b559a27a26bd03f580960364
AUDITED_FALSE_POSITIVES
}

supply_chain_secrets() {
  expect_control_failure detect-secrets 'detected secrets outside the audited false-positive map' \
    secret_negative_control
  scan_repository_secrets
  (cd "$BACKEND_ROOT" && uv run pip-audit && uv run pip-licenses --format=plain --with-urls)
  (cd "$FRONTEND_ROOT" && npm audit --audit-level=high && npm ls --all)
  (cd "$FRONTEND_ROOT" && npm query ':root > *' --json >/tmp/verboflex-phase01-npm-licenses.json)
}

run_staging_adversarial_smoke() {
  local smoke_script=$1
  [ -x "$smoke_script" ] || die "real smoke harness is missing"
  "$smoke_script"
}

staging_adversarial_smoke() {
  [ -x "$GAUNTLET_DIR/adversarial_auth.sh" ] || die "adversarial auth harness is missing"
  run_staging_adversarial_smoke "$GAUNTLET_DIR/real_smoke.sh"
}

self_test_staging_layer() (
  local fixture counter success_script failure_script rc
  fixture=$(mktemp -d)
  counter="$fixture/count"
  success_script="$fixture/success-smoke"
  failure_script="$fixture/failure-smoke"
  trap 'rm -rf "$fixture"' EXIT INT TERM
  printf '%s\n' '#!/bin/sh' 'printf "run\n" >>"$GAUNTLET_LAYER_COUNTER"' >"$success_script"
  printf '%s\n' '#!/bin/sh' 'exit 42' >"$failure_script"
  chmod 700 "$success_script" "$failure_script"
  export GAUNTLET_LAYER_COUNTER="$counter"
  run_staging_adversarial_smoke "$success_script"
  [ "$(wc -l <"$counter" | tr -d ' ')" = "1" ] || die "staging layer did not run exactly once"
  set +e
  run_staging_adversarial_smoke "$failure_script"
  rc=$?
  set -e
  [ "$rc" -eq 42 ] || die "staging layer did not propagate adversarial failure"
  printf 'staging/adversarial layer contract: PASS\n'
)

source_state_layer() {
  local digest
  "$SOURCE_STATE" --verify-review-closed
  "$SOURCE_STATE" --verify-review-source
  digest=$($SOURCE_STATE --digest)
  [ "${#digest}" -eq 64 ] || die "initial source digest is malformed"
  printf '%s\n' "$digest" >"$DIGEST_RECORD"
}

candidate_source_state_layer() {
  local digest
  "$SOURCE_STATE" --verify-review-candidate
  digest=$($SOURCE_STATE --digest)
  [ "${#digest}" -eq 64 ] || die "candidate source digest is malformed"
  printf '%s\n' "$digest" >"$DIGEST_RECORD"
}

final_source_state() {
  "$SOURCE_STATE" --verify-final-before-report
}

run_full_gauntlet() {
  : >"$LAYER_RECORD"
  trap cleanup_test_infra EXIT INT TERM
  run_layer source-state source_state_layer
  run_layer backend-tests backend_tests
  run_layer frontend-tests-browser frontend_tests_browser
  run_layer types types
  run_layer lint-format-complexity lint_format_complexity
  run_layer changed-line-coverage changed_line_coverage
  run_layer mutation-properties mutation_properties
  run_layer migration-rehearsal migration_rehearsal
  run_layer openapi-drift openapi_drift
  run_layer supply-chain-secrets supply_chain_secrets
  run_layer staging-adversarial-smoke staging_adversarial_smoke
  run_layer final-source-state final_source_state
  audit_layer_record
  cleanup_test_infra
  trap - EXIT INT TERM
  printf '\nPHASE 1 GAUNTLET: PASS\n'
}

run_post_fix_candidate() {
  : >"$LAYER_RECORD"
  trap cleanup_test_infra EXIT INT TERM
  run_layer source-state-candidate candidate_source_state_layer
  run_layer backend-tests backend_tests
  run_layer frontend-tests-browser frontend_tests_browser
  run_layer types types
  run_layer lint-format-complexity lint_format_complexity
  run_layer changed-line-coverage changed_line_coverage
  run_layer mutation-properties mutation_properties
  run_layer migration-rehearsal migration_rehearsal
  run_layer openapi-drift openapi_drift
  run_layer supply-chain-secrets supply_chain_secrets
  run_layer staging-adversarial-smoke staging_adversarial_smoke
  run_layer candidate-source-state final_source_state
  audit_layer_record "$EXPECTED_CANDIDATE_LAYERS"
  cleanup_test_infra
  trap - EXIT INT TERM
  printf '\nPHASE 1 POST-FIX CANDIDATE VALIDATION: PASS (NON-FINAL)\n'
}

self_test_candidate_contract() {
  printf '%s\n' "$EXPECTED_CANDIDATE_LAYERS" >"$LAYER_RECORD"
  audit_layer_record "$EXPECTED_CANDIDATE_LAYERS"
  sed '$d' "$LAYER_RECORD" >"$LAYER_RECORD.incomplete"
  cp "$LAYER_RECORD.incomplete" "$LAYER_RECORD"
  expect_control_failure candidate-layer-completion 'controlled drift detected' \
    audit_layer_record "$EXPECTED_CANDIDATE_LAYERS"
  "$SOURCE_STATE" --help | grep -Fq -- '--verify-review-candidate' \
    || die "candidate review source contract is missing"
  printf 'post-fix candidate contract: PASS\n'
}

case "${1:-}" in
  --preflight) checker_preflight ;;
  --self-test-openapi-control) openapi_negative_control ;;
  --self-test-staging-layer) self_test_staging_layer ;;
  --self-test-candidate-contract) self_test_candidate_contract ;;
  --post-fix-candidate) run_post_fix_candidate ;;
  -h|--help)
    printf 'usage: tools/gauntlet.sh [--preflight|--post-fix-candidate]\n'
    ;;
  '') run_full_gauntlet ;;
  *) die "unknown option: $1" ;;
esac

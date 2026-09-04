#!/usr/bin/env bash
set -euo pipefail

readonly GAUNTLET_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
readonly REPO_ROOT=$(CDPATH= cd -- "$GAUNTLET_DIR/.." && pwd)
readonly BACKEND_ROOT="$REPO_ROOT/backend"
readonly FRONTEND_ROOT="$REPO_ROOT/frontend"
readonly PHASE_BASE_COMMIT="4c557f5147038c4b09dc6dcf26d7b26675884bb5"
readonly RANDOM_SEED="315"
readonly DIGEST_RECORD="${VERBOFLEX_GAUNTLET_DIGEST_FILE:-/tmp/verboflex-phase03-gauntlet.digest}"
readonly LAYER_RECORD="${VERBOFLEX_GAUNTLET_LAYER_FILE:-/tmp/verboflex-phase03-gauntlet.layers}"
readonly RESULT_RECORD="${VERBOFLEX_GAUNTLET_RESULT_FILE:-/tmp/verboflex-phase03-gauntlet.result}"
readonly BACKEND_COVERAGE="/tmp/verboflex-phase03-backend-coverage.xml"
readonly BACKEND_JUNIT="/tmp/verboflex-phase03-backend-junit.xml"
readonly FRONTEND_COVERAGE_DIR="/tmp/verboflex-phase03-frontend-coverage"
readonly STRYKER_REPORT="/tmp/verboflex-phase03-stryker.json"
readonly STRYKER_MARKER_RECORD="/tmp/verboflex-phase03-stryker-markers.txt"
readonly SECRET_SCAN="/tmp/verboflex-phase03-secrets.json"
readonly NPM_PROVENANCE="/tmp/verboflex-phase03-npm-provenance.json"
readonly PYTHON_LICENSES="/tmp/verboflex-phase03-python-licenses.txt"

readonly FRONTEND_MUTATION_MARKERS="src/features/admin/imports/mutationAuthority.ts|published-live-authority
src/features/admin/imports/mutationAuthority.ts|published-request-token-ownership
src/features/admin/imports/mutationAuthority.ts|live-mutation-controller-ownership
src/features/admin/imports/mutationAuthority.ts|rewrite-live-authority-request-token
src/features/admin/imports/mutationAuthority.ts|rewrite-uncommitted-finalization"

readonly EXPECTED_LAYERS="source-state
checker-negative-controls
backend-tests-coverage
backend-types-lint-format
migrations-openapi
frontend-tests-coverage
frontend-types-lint-format-build
targeted-mutation-proof
playwright-responsive-accessibility
supply-chain-license-secret-schema
architecture-provider-audit
mock-deployment-smoke
api-coverage-preseal
final-source-state"

export VERBOFLEX_SOURCE_MANIFEST="tools/phase3_source_manifest.txt"
export VERBOFLEX_REVIEW_PATH=".planning/phases/03-bitbucket-import-integration/03-REVIEW.md"
export VERBOFLEX_EVIDENCE_PATH="docs/evidence/phase-03.md"
export VERBOFLEX_GAUNTLET_DIGEST_FILE="$DIGEST_RECORD"

TEST_POSTGRES_NAME=""
TEST_REDIS_NAME=""
TEST_WORKER_PID=""
TEST_WORKER_LOG=""
TEST_WORKER_PING=""
VITE_PID=""
VITE_LOG=""

die() {
  printf 'phase3-gauntlet error: %s\n' "$1" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "required command is unavailable: $1"
}

run_layer() {
  local layer=$1 started elapsed rc
  shift
  printf '\n### layer: %s\n' "$layer"
  started=$SECONDS
  set +e
  (
    set -e
    "$@"
  )
  rc=$?
  set -e
  [ "$rc" -eq 0 ] || die "layer $layer failed with exit code $rc"
  elapsed=$((SECONDS - started))
  printf '%s|%s\n' "$layer" "$elapsed" >>"$LAYER_RECORD"
  printf 'layer %s: PASS (%ss)\n' "$layer" "$elapsed"
}

assert_exact_layers() {
  local expected=$1 record=${2:-$LAYER_RECORD} expected_file actual_file
  expected_file=$(mktemp)
  actual_file=$(mktemp)
  printf '%s\n' "$expected" >"$expected_file"
  cut -d '|' -f1 "$record" | sed '/^$/d' >"$actual_file"
  if ! diff -u "$expected_file" "$actual_file"; then
    rm -f "$expected_file" "$actual_file"
    die "layer completion record drifted"
  fi
  rm -f "$expected_file" "$actual_file"
}

expect_failure() {
  local label=$1 expected=$2 output rc
  shift 2
  output=$(mktemp)
  set +e
  ("$@") >"$output" 2>&1
  rc=$?
  set -e
  if [ "$rc" -eq 0 ]; then
    rm -f "$output"
    die "$label negative control unexpectedly passed"
  fi
  if ! grep -Fq "$expected" "$output"; then
    sed -n '1,100p' "$output" >&2
    rm -f "$output"
    die "$label negative control failed for the wrong reason"
  fi
  rm -f "$output"
}

wait_for_container_command() {
  local container_name=$1 deadline
  shift
  deadline=$((SECONDS + 60))
  while [ "$SECONDS" -lt "$deadline" ]; do
    if docker exec "$container_name" "$@" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  die "container readiness timed out: $container_name"
}

start_test_infra() {
  local suffix postgres_port redis_port deadline
  suffix="$$-$RANDOM"
  TEST_POSTGRES_NAME="verboflex-phase3-postgres-$suffix"
  TEST_REDIS_NAME="verboflex-phase3-redis-$suffix"
  TEST_WORKER_LOG="/tmp/verboflex-phase03-worker-$suffix.log"
  TEST_WORKER_PING="/tmp/verboflex-phase03-worker-ping-$suffix.log"
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
      exec "$BACKEND_ROOT/.venv/bin/celery" -A verboflex.worker.celery_app \
      worker --loglevel=WARNING --pool=solo --concurrency=1 \
      --hostname="verboflex-phase3-$suffix@%h"
  ) >"$TEST_WORKER_LOG" 2>&1 &
  TEST_WORKER_PID=$!
  deadline=$((SECONDS + 60))
  while [ "$SECONDS" -lt "$deadline" ]; do
    if (
      cd "$BACKEND_ROOT"
      VERBOFLEX_REDIS_URL="$VERBOFLEX_TEST_CELERY_REDIS_URL" \
        uv run celery -A verboflex.worker.celery_app inspect ping --timeout 1
    ) >"$TEST_WORKER_PING" 2>&1 \
      && grep -Fq '1 node online' "$TEST_WORKER_PING"; then
      return 0
    fi
    kill -0 "$TEST_WORKER_PID" 2>/dev/null \
      || { sed -n '1,120p' "$TEST_WORKER_LOG" >&2; die "Celery worker exited before readiness"; }
    sleep 1
  done
  sed -n '1,120p' "$TEST_WORKER_LOG" >&2
  die "Celery worker readiness timed out"
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
    docker stop --time 5 "$TEST_POSTGRES_NAME" >/dev/null 2>&1 || true
  fi
  if [ -n "$TEST_REDIS_NAME" ]; then
    docker stop --time 5 "$TEST_REDIS_NAME" >/dev/null 2>&1 || true
  fi
  [ -z "$TEST_WORKER_LOG" ] || rm -f "$TEST_WORKER_LOG"
  [ -z "$TEST_WORKER_PING" ] || rm -f "$TEST_WORKER_PING"
  TEST_WORKER_PID=""
  TEST_POSTGRES_NAME=""
  TEST_REDIS_NAME=""
  TEST_WORKER_LOG=""
  TEST_WORKER_PING=""
}

with_test_infra() {
  local body=$1 rc
  start_test_infra
  set +e
  (
    set -e
    "$body"
  )
  rc=$?
  set -e
  cleanup_test_infra
  return "$rc"
}

cleanup_runtime() {
  cleanup_test_infra
  if [ -n "$VITE_PID" ] && kill -0 "$VITE_PID" 2>/dev/null; then
    kill "$VITE_PID" >/dev/null 2>&1 || true
    wait "$VITE_PID" >/dev/null 2>&1 || true
  fi
  [ -z "$VITE_LOG" ] || rm -f "$VITE_LOG"
  VITE_PID=""
  VITE_LOG=""
  rm -f "$BACKEND_COVERAGE" "$BACKEND_JUNIT" "$STRYKER_REPORT" \
    "$SECRET_SCAN" "$NPM_PROVENANCE" "$PYTHON_LICENSES" "$STRYKER_MARKER_RECORD" \
    /tmp/verboflex-phase01-stryker.json
  rm -rf "$FRONTEND_COVERAGE_DIR" /tmp/verboflex-phase03-stryker-tmp
}

source_state_layer() {
  local digest
  "$GAUNTLET_DIR/source_state.sh" --self-test-manifest
  digest=$("$GAUNTLET_DIR/source_state.sh" --digest)
  [ "${#digest}" -eq 64 ] || die "source digest is malformed"
  printf '%s\n' "$digest" >"$DIGEST_RECORD"
  printf 'Phase 3 source digest captured: %s\n' "$digest"
}

checker_negative_controls() {
  local fixture
  for command_name in bash curl diff docker git node npm shasum uv; do
    require_command "$command_name"
  done
  bash -n "$GAUNTLET_DIR/phase3_gauntlet.sh" "$GAUNTLET_DIR/phase3_smoke.sh" \
    "$GAUNTLET_DIR/source_state.sh"
  "$BACKEND_ROOT/.venv/bin/python" "$GAUNTLET_DIR/verify_import_job_mutants.py" --self-test
  "$GAUNTLET_DIR/phase3_smoke.sh" --self-test-live-mode
  (
    cd "$BACKEND_ROOT"
    uv run pytest -q \
      tests/architecture/test_phase3_gauntlet.py \
      tests/architecture/test_phase3_scope.py \
      tests/architecture/test_provider_boundaries.py \
      tests/architecture/test_background_boundaries.py
  )
  fixture=$(mktemp)
  printf '%s|0\n' "${EXPECTED_LAYERS%%$'\n'*}" >"$fixture"
  expect_failure layer-completion 'layer completion record drifted' \
    assert_exact_layers "$EXPECTED_LAYERS" "$fixture"
  rm -f "$fixture"
  printf 'stale completion, automatic retry, partial delta, missing coverage, and UI marker controls: PASS\n'
}

backend_tests_coverage_body() {
  (
    cd "$BACKEND_ROOT"
    uv run pytest --randomly-seed="$RANDOM_SEED" -q \
      --junitxml="$BACKEND_JUNIT" \
      --cov=verboflex --cov-branch --cov-report=term-missing \
      --cov-report="xml:$BACKEND_COVERAGE" --cov-fail-under=0
  )
  [ -s "$BACKEND_COVERAGE" ] || die "backend coverage report is empty"
  [ -s "$BACKEND_JUNIT" ] || die "backend JUnit report is empty"
}

backend_tests_coverage() {
  with_test_infra backend_tests_coverage_body
}

backend_types_lint_format() {
  (cd "$BACKEND_ROOT" && uv run mypy src)
  (cd "$BACKEND_ROOT" && uv run ruff check src tests)
  (cd "$BACKEND_ROOT" && uv run ruff format --check src tests)
}

migrations_openapi_body() {
  (cd "$BACKEND_ROOT" && uv run pytest -q tests/integration/test_migrations.py)
}

migrations_openapi() {
  with_test_infra migrations_openapi_body
  (cd "$FRONTEND_ROOT" && npm run api:check)
}

frontend_tests_coverage() {
  rm -rf "$FRONTEND_COVERAGE_DIR"
  (
    cd "$FRONTEND_ROOT"
    npm run test:coverage -- --sequence.shuffle --sequence.seed="$RANDOM_SEED" \
      --coverage.provider=v8 --coverage.reporter=text --coverage.reporter=cobertura \
      --coverage.reportsDirectory="$FRONTEND_COVERAGE_DIR"
  )
  [ -s "$FRONTEND_COVERAGE_DIR/cobertura-coverage.xml" ] \
    || die "frontend coverage report is empty"
}

frontend_types_lint_format_build() {
  (cd "$FRONTEND_ROOT" && npm run typecheck)
  (cd "$FRONTEND_ROOT" && npm run lint)
  (cd "$FRONTEND_ROOT" && npm run format:check)
  (cd "$FRONTEND_ROOT" && npm run build)
}

resolve_frontend_mutation_markers() {
  local relative_path marker source marker_text marker_count marker_line target_line selectors
  selectors=""
  : >"$STRYKER_MARKER_RECORD"
  while IFS='|' read -r relative_path marker; do
    [ -n "$relative_path" ] || continue
    source="$FRONTEND_ROOT/$relative_path"
    marker_text="phase3-mutation:$marker"
    [ -f "$source" ] || die "Stryker marker source is missing: $relative_path"
    marker_count=$(grep -Fc "$marker_text" "$source")
    [ "$marker_count" -eq 1 ] \
      || die "Stryker marker must occur exactly once: $relative_path|$marker"
    marker_line=$(grep -nF "$marker_text" "$source" | cut -d: -f1)
    target_line=$((marker_line + 1))
    sed -n "${target_line}p" "$source" | grep -Eq '[^[:space:]]' \
      || die "Stryker marker has no following target line: $relative_path|$marker"
    printf '%s|%s\n' "$relative_path" "$target_line" >>"$STRYKER_MARKER_RECORD"
    if [ -n "$selectors" ]; then
      selectors="$selectors,"
    fi
    selectors="${selectors}${relative_path}:${target_line}-${target_line}"
  done <<<"$FRONTEND_MUTATION_MARKERS"
  printf '%s\n' "$selectors"
}

assert_stryker_report() {
  [ -s "$STRYKER_REPORT" ] || die "Stryker report is missing"
  [ -s "$STRYKER_MARKER_RECORD" ] || die "Stryker marker ownership is missing"
  "$BACKEND_ROOT/.venv/bin/python" - "$STRYKER_REPORT" "$STRYKER_MARKER_RECORD" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
mutants = [item for file in data.get("files", {}).values() for item in file.get("mutants", [])]
if not mutants:
    raise SystemExit("Stryker executed zero mutants")
expected_locations = {
    "src/features/admin/imports/PublishedMappingImports.tsx": {82, 83, 84, 85, 86, 531},
    "src/features/admin/imports/RewrittenBaselineDialog.tsx": {439},
    "src/features/admin/imports/useImportPolling.ts": {34, 35, 37, 38},
}
expected_marker_locations = {}
with open(sys.argv[2], encoding="utf-8") as marker_record:
    for row in marker_record:
        path, line = row.rstrip("\n").split("|", 1)
        expected_marker_locations.setdefault(path, set()).add(int(line))
for path, locations in expected_marker_locations.items():
    expected_locations.setdefault(path, set()).update(locations)
actual_locations = {
    path: {item["location"]["start"]["line"] for item in file.get("mutants", [])}
    for path, file in data.get("files", {}).items()
    if file.get("mutants")
}
if actual_locations != expected_locations:
    raise SystemExit(
        f"Stryker target ownership drifted: expected {expected_locations!r}, "
        f"got {actual_locations!r}"
    )
bad = [item for item in mutants if item.get("status") != "Killed"]
if bad:
    raise SystemExit(
        "Stryker non-killed mutants: "
        + repr([(item.get("id"), item.get("status")) for item in bad])
    )
print(f"Stryker import UI mutation score: {len(mutants)}/{len(mutants)} killed")
PY
}

backend_targeted_mutations() {
  "$BACKEND_ROOT/.venv/bin/python" "$GAUNTLET_DIR/verify_import_job_mutants.py"
}

targeted_mutation_proof() {
  local marker_targets
  with_test_infra backend_targeted_mutations
  marker_targets=$(resolve_frontend_mutation_markers)
  : >/tmp/verboflex-phase01-stryker.json
  (
    cd "$FRONTEND_ROOT"
    npm run test:mutation -- \
      --mutate "src/features/admin/imports/useImportPolling.ts:33-40,src/features/admin/imports/PublishedMappingImports.tsx:82-86,src/features/admin/imports/PublishedMappingImports.tsx:531-531,src/features/admin/imports/RewrittenBaselineDialog.tsx:439-439,$marker_targets" \
      --reporters clear-text,json \
      --tempDirName '/tmp/verboflex-phase03-stryker-tmp' \
      --cleanTempDir always
  )
  cp /tmp/verboflex-phase01-stryker.json "$STRYKER_REPORT"
  assert_stryker_report
}

random_port() {
  "$BACKEND_ROOT/.venv/bin/python" -c \
    'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()'
}

playwright_responsive_accessibility() {
  local port url deadline
  port=$(random_port)
  url="http://127.0.0.1:$port"
  VITE_LOG="/tmp/verboflex-phase03-vite-$$.log"
  (
    cd "$FRONTEND_ROOT"
    exec npm run dev -- --host 127.0.0.1 --port "$port" --strictPort
  ) >"$VITE_LOG" 2>&1 &
  VITE_PID=$!
  deadline=$((SECONDS + 60))
  while [ "$SECONDS" -lt "$deadline" ]; do
    if curl --silent --show-error --max-time 2 --fail "$url/login" >/dev/null 2>&1; then
      break
    fi
    kill -0 "$VITE_PID" 2>/dev/null \
      || { sed -n '1,120p' "$VITE_LOG" >&2; die "Vite exited before readiness"; }
    sleep 1
  done
  curl --silent --show-error --max-time 2 --fail "$url/login" >/dev/null \
    || die "Vite readiness timed out"
  (
    cd "$FRONTEND_ROOT"
    PLAYWRIGHT_BASE_URL="$url" \
    PLAYWRIGHT_OUTPUT_DIR="/tmp/verboflex-phase03-playwright" \
      npm run e2e -- e2e/admin-configuration.spec.ts --grep 'UI3-C23|UI3-C26|PW3-C27'
  )
  kill "$VITE_PID" >/dev/null 2>&1 || true
  wait "$VITE_PID" >/dev/null 2>&1 || true
  VITE_PID=""
  rm -f "$VITE_LOG"
  VITE_LOG=""
  rm -rf /tmp/verboflex-phase03-playwright
}

scan_phase_secrets() {
  local files findings count
  files=$(mktemp)
  findings=$(mktemp)
  git -C "$REPO_ROOT" diff --name-only "$PHASE_BASE_COMMIT"..HEAD \
    | grep -E '^(backend/src/|frontend/src/|tools/phase3_|tools/verify_import_job_mutants.py)' \
    | grep -Ev '\.(test|spec)\.(ts|tsx)$' >"$files"
  [ -s "$files" ] || die "Phase 3 production secret scan selected no files"
  (
    cd "$BACKEND_ROOT"
    uv run detect-secrets scan $(sed 's#^#../#' "$files") >"$SECRET_SCAN"
    uv run python -c \
      'import json,sys; d=json.load(open(sys.argv[1])); print("\\n".join(sorted(f"{p}|{x[chr(108)+chr(105)+chr(110)+chr(101)+chr(95)+chr(110)+chr(117)+chr(109)+chr(98)+chr(101)+chr(114)]}|{x[chr(116)+chr(121)+chr(112)+chr(101)]}" for p,v in d["results"].items() for x in v)))' \
      "$SECRET_SCAN" >"$findings"
  )
  count=$(sed '/^$/d' "$findings" | wc -l | tr -d ' ')
  if [ "$count" -ne 0 ]; then
    sed -n '1,120p' "$findings" >&2
    rm -f "$files" "$findings"
    die "production secret scan found unreviewed material"
  fi
  rm -f "$files" "$findings" "$SECRET_SCAN"
}

supply_chain_license_secret_schema() {
  (cd "$BACKEND_ROOT" && uv lock --check)
  (cd "$BACKEND_ROOT" && uv run pip-audit)
  (cd "$BACKEND_ROOT" && uv run pip-licenses --format=plain --with-urls) >"$PYTHON_LICENSES"
  [ -s "$PYTHON_LICENSES" ] || die "Python license inventory is empty"
  (cd "$FRONTEND_ROOT" && npm audit --audit-level=high)
  (cd "$FRONTEND_ROOT" && npm audit --omit=dev --audit-level=moderate)
  (cd "$FRONTEND_ROOT" && npm ls --all)
  (cd "$FRONTEND_ROOT" && npm query ':root > *' --json) >"$NPM_PROVENANCE"
  [ -s "$NPM_PROVENANCE" ] || die "npm provenance inventory is empty"
  scan_phase_secrets
  (
    cd "$BACKEND_ROOT"
    uv run pytest -q tests/integration/test_migrations.py \
      tests/api/test_openapi_contract.py
  )
}

architecture_provider_audit() {
  (
    cd "$BACKEND_ROOT"
    uv run pytest -q tests/architecture \
      tests/integration/test_bitbucket_http_adapter.py \
      tests/integration/test_bitbucket_diagnostics.py \
      tests/api/test_openapi_contract.py
  )
}

mock_deployment_smoke() {
  "$GAUNTLET_DIR/phase3_smoke.sh" --mock-provider
}

api_coverage_preseal() {
  node /Users/smutti/.codex/gsd-core/bin/gsd-tools.cjs check api-coverage.verify-pre \
    "$REPO_ROOT/.planning/phases/03-bitbucket-import-integration"
}

final_source_state() {
  local expected actual
  [ -s "$DIGEST_RECORD" ] || die "source digest record is missing"
  expected=$(sed -n '1p' "$DIGEST_RECORD")
  actual=$("$GAUNTLET_DIR/source_state.sh" --digest)
  [ "$actual" = "$expected" ] \
    || die "source digest changed: expected $expected, got $actual"
  printf 'Phase 3 source digest unchanged: %s\n' "$actual"
}

write_result() {
  local started=$1 completed=$2 digest layers
  digest=$(sed -n '1p' "$DIGEST_RECORD")
  layers=$(wc -l <"$LAYER_RECORD" | tr -d ' ')
  {
    printf 'gauntlet_status=PASS\n'
    printf 'source_digest=%s\n' "$digest"
    printf 'layer_count=%s\n' "$layers"
    printf 'duration_seconds=%s\n' "$((completed - started))"
    printf 'backend_junit_sha256=%s\n' "$(shasum -a 256 "$BACKEND_JUNIT" 2>/dev/null | awk '{print $1}')"
    printf 'frontend_coverage_sha256=%s\n' \
      "$(shasum -a 256 "$FRONTEND_COVERAGE_DIR/cobertura-coverage.xml" 2>/dev/null | awk '{print $1}')"
  } >"$RESULT_RECORD"
}

run_gauntlet() {
  local started=$SECONDS completed
  : >"$LAYER_RECORD"
  : >"$RESULT_RECORD"
  rm -f "$DIGEST_RECORD"
  trap cleanup_runtime EXIT INT TERM
  run_layer source-state source_state_layer
  run_layer checker-negative-controls checker_negative_controls
  run_layer backend-tests-coverage backend_tests_coverage
  run_layer backend-types-lint-format backend_types_lint_format
  run_layer migrations-openapi migrations_openapi
  run_layer frontend-tests-coverage frontend_tests_coverage
  run_layer frontend-types-lint-format-build frontend_types_lint_format_build
  run_layer targeted-mutation-proof targeted_mutation_proof
  run_layer playwright-responsive-accessibility playwright_responsive_accessibility
  run_layer supply-chain-license-secret-schema supply_chain_license_secret_schema
  run_layer architecture-provider-audit architecture_provider_audit
  run_layer mock-deployment-smoke mock_deployment_smoke
  run_layer api-coverage-preseal api_coverage_preseal
  run_layer final-source-state final_source_state
  assert_exact_layers "$EXPECTED_LAYERS"
  completed=$SECONDS
  write_result "$started" "$completed"
  cleanup_runtime
  trap - EXIT INT TERM
  printf '\nPHASE 3 GAUNTLET: PASS (14/14 layers, %ss)\n' "$((completed - started))"
}

case "${1:-}" in
  '') run_gauntlet ;;
  --self-test) checker_negative_controls ;;
  -h|--help) printf 'usage: tools/phase3_gauntlet.sh [--self-test]\n' ;;
  *) die "unknown argument: $1" ;;
esac

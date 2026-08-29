#!/usr/bin/env bash
set -euo pipefail

readonly GAUNTLET_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
readonly REPO_ROOT=$(CDPATH= cd -- "$GAUNTLET_DIR/.." && pwd)
readonly BACKEND_ROOT="$REPO_ROOT/backend"
readonly FRONTEND_ROOT="$REPO_ROOT/frontend"
readonly PHASE_BASE_COMMIT="ce9fbeef86b00f594d1d06e15d3083d623c54095"
readonly PLAN_BASE_COMMIT="50664a2"
readonly RANDOM_SEED="220"
readonly DIGEST_RECORD="${VERBOFLEX_GAUNTLET_DIGEST_FILE:-/tmp/verboflex-phase02-gauntlet.digest}"
readonly LAYER_RECORD="${VERBOFLEX_GAUNTLET_LAYER_FILE:-/tmp/verboflex-phase02-gauntlet.layers}"
readonly BACKEND_COVERAGE="/tmp/verboflex-phase02-backend-coverage.xml"
readonly BACKEND_JUNIT="/tmp/verboflex-phase02-backend-junit.xml"
readonly FRONTEND_COVERAGE_DIR="/tmp/verboflex-phase02-frontend-coverage"
readonly FRONTEND_COVERAGE_NORMALIZED="/tmp/verboflex-phase02-frontend-coverage.xml"
readonly STRYKER_REPORT="/tmp/verboflex-phase02-stryker.json"
readonly EVIDENCE_PATH="$REPO_ROOT/docs/evidence/phase-02.md"

readonly EXPECTED_CANDIDATE_LAYERS="source-state
checker-self-tests
backend-tests-coverage
frontend-tests-coverage
types-lint-format-build
property-suites
changed-scope-coverage
mutation-authority-detectors-polling
migrations-openapi
supply-chain-secrets-licenses
architecture-provider-spy
compose-browser-smoke
final-source-state"

readonly EXPECTED_FINAL_LAYERS="$EXPECTED_CANDIDATE_LAYERS
evidence-report"

export VERBOFLEX_SOURCE_MANIFEST="tools/phase2_source_manifest.txt"
export VERBOFLEX_REVIEW_PATH="docs/reviews/phase-02-code-security.md"
export VERBOFLEX_EVIDENCE_PATH="docs/evidence/phase-02.md"
export VERBOFLEX_GAUNTLET_DIGEST_FILE="$DIGEST_RECORD"

TEST_POSTGRES_NAME=""
TEST_REDIS_NAME=""
TEST_WORKER_PID=""

die() {
  printf 'phase2-gauntlet error: %s\n' "$1" >&2
  exit 1
}

run_layer() {
  local layer=$1
  shift
  local rc
  printf '\n### layer: %s\n' "$layer"
  set +e
  (
    set -e
    "$@"
  )
  rc=$?
  set -e
  [ "$rc" -eq 0 ] || die "layer $layer failed with exit code $rc"
  printf '%s\n' "$layer" >>"$LAYER_RECORD"
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "required command is unavailable: $1"
}

filter_frontend_production_paths() {
  awk '!($0 ~ /(^|\/)__tests__\// || $0 ~ /\.(test|spec|stories)\.(ts|tsx|js|jsx)$/)'
}

assert_exact_layers() {
  local expected=$1
  local expected_file actual_file
  expected_file=$(mktemp)
  actual_file=$(mktemp)
  printf '%s\n' "$expected" >"$expected_file"
  sed '/^$/d' "$LAYER_RECORD" >"$actual_file"
  if ! diff -u "$expected_file" "$actual_file"; then
    rm -f "$expected_file" "$actual_file"
    die "layer completion record drifted"
  fi
  rm -f "$expected_file" "$actual_file"
}

wait_for_container_command() {
  local container_name=$1
  shift
  local deadline=$((SECONDS + 60))
  while [ "$SECONDS" -lt "$deadline" ]; do
    if docker exec "$container_name" "$@" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  die "container readiness timed out: $container_name"
}

start_test_infra() {
  local suffix postgres_port redis_port worker_log deadline
  suffix="$$-$RANDOM"
  TEST_POSTGRES_NAME="verboflex-phase2-postgres-$suffix"
  TEST_REDIS_NAME="verboflex-phase2-redis-$suffix"
  worker_log="/tmp/verboflex-phase02-worker-$suffix.log"
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
      --hostname="verboflex-phase2-$suffix@%h"
  ) >"$worker_log" 2>&1 &
  TEST_WORKER_PID=$!
  deadline=$((SECONDS + 60))
  while [ "$SECONDS" -lt "$deadline" ]; do
    if (
      cd "$BACKEND_ROOT"
      VERBOFLEX_REDIS_URL="$VERBOFLEX_TEST_CELERY_REDIS_URL" \
        uv run celery -A verboflex.worker.celery_app inspect ping --timeout 1
    ) >/tmp/verboflex-phase02-worker-ping.log 2>&1 \
      && grep -Fq '1 node online' /tmp/verboflex-phase02-worker-ping.log; then
      return 0
    fi
    kill -0 "$TEST_WORKER_PID" 2>/dev/null \
      || { sed -n '1,120p' "$worker_log" >&2; die "Celery worker exited before readiness"; }
    sleep 1
  done
  sed -n '1,120p' "$worker_log" >&2
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
    set +e
    docker stop --time 5 "$TEST_POSTGRES_NAME" >/dev/null 2>&1
    rc=$?
    set -e
    [ "$rc" -eq 0 ] || [ "$rc" -eq 1 ] || die "PostgreSQL cleanup failed"
  fi
  if [ -n "$TEST_REDIS_NAME" ]; then
    set +e
    docker stop --time 5 "$TEST_REDIS_NAME" >/dev/null 2>&1
    rc=$?
    set -e
    [ "$rc" -eq 0 ] || [ "$rc" -eq 1 ] || die "Redis cleanup failed"
  fi
  TEST_WORKER_PID=""
  TEST_POSTGRES_NAME=""
  TEST_REDIS_NAME=""
}

with_test_infra() {
  local body=$1
  local rc
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

source_state_layer() {
  local digest
  "$GAUNTLET_DIR/source_state.sh" --verify-review-closed
  "$GAUNTLET_DIR/source_state.sh" --verify-review-source
  digest=$("$GAUNTLET_DIR/source_state.sh" --digest)
  [ "${#digest}" -eq 64 ] || die "source digest is malformed"
  printf '%s\n' "$digest" >"$DIGEST_RECORD"
}

checker_self_tests() {
  local fixture expected actual rc command_name
  for command_name in bash git shasum docker uv node npm; do
    require_command "$command_name"
  done
  bash -n "$GAUNTLET_DIR/phase2_gauntlet.sh" "$GAUNTLET_DIR/phase2_smoke.sh" \
    "$GAUNTLET_DIR/source_state.sh"
  "$GAUNTLET_DIR/source_state.sh" --self-test-manifest
  fixture=$(mktemp -d)
  expected="$fixture/expected"
  actual="$fixture/actual"
  printf '%s\n' "$EXPECTED_FINAL_LAYERS" >"$expected"
  sed '$d' "$expected" >"$actual"
  set +e
  diff -u "$expected" "$actual" >/dev/null
  rc=$?
  set -e
  [ "$rc" -ne 0 ] || { rm -rf "$fixture"; die "layer negative control passed"; }
  printf '%s\n' \
    'frontend/src/features/admin/previews/usePreviewPolling.test.ts' \
    'frontend/src/features/admin/previews/usePreviewPolling.ts' \
    'frontend/src/features/admin/previews/__tests__/fixture.ts' \
    | filter_frontend_production_paths >"$actual"
  printf '%s\n' 'frontend/src/features/admin/previews/usePreviewPolling.ts' >"$expected"
  cmp -s "$expected" "$actual" \
    || { rm -rf "$fixture"; die "frontend production-path classifier drifted"; }
  rm -rf "$fixture"
  printf 'checker negative controls: PASS\n'
}

backend_tests_coverage_body() {
  (
    cd "$BACKEND_ROOT"
    uv run pytest --randomly-seed="$RANDOM_SEED" -q \
      --junitxml="$BACKEND_JUNIT" \
      --cov=verboflex --cov-branch --cov-report=term-missing \
      --cov-report="xml:$BACKEND_COVERAGE" --cov-fail-under=0
  )
}

backend_tests_coverage() {
  with_test_infra backend_tests_coverage_body
}

frontend_tests_coverage() {
  rm -rf "$FRONTEND_COVERAGE_DIR"
  (
    cd "$FRONTEND_ROOT"
    npm run test:coverage -- --sequence.shuffle --sequence.seed="$RANDOM_SEED" \
      --coverage.provider=v8 --coverage.reporter=text --coverage.reporter=cobertura \
      --coverage.reportsDirectory="$FRONTEND_COVERAGE_DIR"
  )
}

types_lint_format_build() {
  (cd "$BACKEND_ROOT" && uv run mypy src)
  (cd "$BACKEND_ROOT" && uv run ruff check src tests)
  (cd "$BACKEND_ROOT" && uv run ruff format --check src tests)
  (cd "$FRONTEND_ROOT" && npm run typecheck)
  (cd "$FRONTEND_ROOT" && npm run lint)
  (cd "$FRONTEND_ROOT" && npm run format:check)
  (cd "$FRONTEND_ROOT" && npm run build)
}

backend_property_suites() {
  (
    cd "$BACKEND_ROOT"
    uv run pytest -q \
      tests/unit/localization/preview/test_android_xml.py \
      tests/unit/localization/preview/test_ios_strings.py \
      tests/unit/localization/preview/test_json.py \
      tests/unit/localization/preview/test_qt_ts.py \
      tests/unit/services/test_pr_grouping.py \
      tests/unit/test_product_names.py
  )
}

property_suites() {
  with_test_infra backend_property_suites
  (cd "$FRONTEND_ROOT" && npm run test -- --run src/features/auth/session.property.test.ts)
}

normalize_frontend_coverage() {
  "$BACKEND_ROOT/.venv/bin/python" - "$FRONTEND_COVERAGE_DIR/cobertura-coverage.xml" \
    "$FRONTEND_COVERAGE_NORMALIZED" "$FRONTEND_ROOT" <<'PY'
from pathlib import PurePosixPath
import sys
import xml.etree.ElementTree as ET

source, destination, expected_root = sys.argv[1:]
tree = ET.parse(source)
root = tree.getroot()
sources = root.findall("./sources/source")
classes = root.findall(".//class")
if len(sources) != 1 or (sources[0].text or "").rstrip("/") != expected_root or not classes:
    raise SystemExit("non-canonical frontend Cobertura roots")
sources[0].text = "."
for item in classes:
    filename = item.get("filename", "")
    candidate = PurePosixPath(filename)
    if candidate.is_absolute() or ".." in candidate.parts or not filename.startswith("src/"):
        raise SystemExit("non-canonical frontend Cobertura filename")
    item.set("filename", f"frontend/{filename}")
tree.write(destination, encoding="utf-8", xml_declaration=True)
PY
}

assert_nonempty_diff_coverage() {
  local report=$1
  ! grep -Fq 'No lines with coverage information in this diff.' "$report" \
    || die "changed-scope coverage matched no coverable lines"
  grep -Eq '^Total:[[:space:]]+[1-9][0-9]*[[:space:]]+lines?[[:space:]]*$' "$report" \
    || die "changed-scope coverage reported zero lines"
}

changed_scope_coverage() {
  local backend_report="/tmp/verboflex-phase02-backend-diff-cover.txt"
  local frontend_report="/tmp/verboflex-phase02-frontend-diff-cover.txt"
  local frontend_production_paths
  local excluded_path reason
  local -a frontend_excludes=()
  (
    cd "$BACKEND_ROOT"
    uv run diff-cover "$BACKEND_COVERAGE" --compare-branch "$PLAN_BASE_COMMIT" \
      --branch-coverage --fail-under 100 \
      --exclude 'backend/alembic/**' 'backend/src/verboflex/main.py' \
        'backend/src/verboflex/scripts/export_openapi.py'
  ) | tee "$backend_report"
  assert_nonempty_diff_coverage "$backend_report"
  frontend_production_paths=$(
    git -C "$REPO_ROOT" diff --name-only "$PLAN_BASE_COMMIT"..HEAD -- frontend/src \
      | filter_frontend_production_paths
  )
  if [ -z "$frontend_production_paths" ]; then
    printf 'Frontend changed-scope coverage: N/A (no Plan 02-20 frontend production diff)\n' \
      | tee "$frontend_report"
  else
    normalize_frontend_coverage
    while IFS='|' read -r excluded_path reason; do
      [ -n "$excluded_path" ] && [ -n "$reason" ] || die "invalid frontend coverage exclusion"
      frontend_excludes+=("*/$excluded_path")
    done <"$GAUNTLET_DIR/frontend_coverage_exclusions.txt"
    (
      cd "$REPO_ROOT"
      "$BACKEND_ROOT/.venv/bin/diff-cover" "$FRONTEND_COVERAGE_NORMALIZED" \
        --compare-branch "$PLAN_BASE_COMMIT" --branch-coverage --fail-under 100 \
        --exclude "${frontend_excludes[@]}"
    ) | tee "$frontend_report"
    assert_nonempty_diff_coverage "$frontend_report"
  fi
}

backend_mutation_body() {
  local proof
  local -a proofs=(
    verify_product_api_mutants.py
    verify_repository_api_mutants.py
    verify_bitbucket_oauth_mutants.py
    verify_bitbucket_http_adapter_mutants.py
    verify_bitbucket_discovery_mutants.py
    verify_mapping_api_mutants.py
    verify_product_publication_mutants.py
    verify_preview_job_mutants.py
    verify_android_preview_mutants.py
    verify_ios_preview_mutants.py
  )
  : > /tmp/verboflex-phase02-backend-mutations.log
  for proof in "${proofs[@]}"; do
    "$BACKEND_ROOT/.venv/bin/python" "$GAUNTLET_DIR/$proof" --self-test
    "$BACKEND_ROOT/.venv/bin/python" "$GAUNTLET_DIR/$proof" \
      | tee -a /tmp/verboflex-phase02-backend-mutations.log
  done
  [ "$(grep -Ec '^mutation score:' /tmp/verboflex-phase02-backend-mutations.log)" -eq 10 ] \
    || die "backend mutation proofs did not all report results"
}

assert_stryker_report() {
  [ -f "$STRYKER_REPORT" ] || die "Stryker report is missing"
  "$BACKEND_ROOT/.venv/bin/python" - "$STRYKER_REPORT" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
mutants = [mutant for file in data.get("files", {}).values() for mutant in file.get("mutants", [])]
if not mutants:
    raise SystemExit("Stryker executed zero mutants")
bad = [mutant for mutant in mutants if mutant.get("status") != "Killed"]
if bad:
    raise SystemExit(f"Stryker non-killed mutants: {[(item.get('id'), item.get('status')) for item in bad]}")
print(f"Stryker polling mutation score: {len(mutants)}/{len(mutants)} killed")
PY
}

mutation_authority_detectors_polling() {
  with_test_infra backend_mutation_body
  : > /tmp/verboflex-phase01-stryker.json
  : > "$STRYKER_REPORT"
  (
    cd "$FRONTEND_ROOT"
    npm run test:mutation -- \
      --mutate 'src/features/admin/previews/usePreviewPolling.ts:28-39,src/features/admin/previews/usePreviewPolling.ts:118-126' \
      --reporters clear-text,json \
      --tempDirName '/tmp/verboflex-phase02-stryker-tmp' \
      --cleanTempDir always
  )
  cp /tmp/verboflex-phase01-stryker.json "$STRYKER_REPORT"
  assert_stryker_report
}

migrations_openapi_body() {
  (cd "$BACKEND_ROOT" && uv run pytest -q tests/integration/test_migrations.py)
}

migrations_openapi() {
  with_test_infra migrations_openapi_body
  (cd "$FRONTEND_ROOT" && npm run api:check)
}

scan_phase_secrets() {
  local files findings expected
  files=$(mktemp)
  findings=$(mktemp)
  expected=$(mktemp)
  git -C "$REPO_ROOT" diff --name-only "$PHASE_BASE_COMMIT"..HEAD \
    | grep -Ev '^(backend/uv.lock|frontend/package-lock.json|\.planning/)' >"$files"
  [ -s "$files" ] || die "Phase 2 secret scan selected no files"
  (
    cd "$BACKEND_ROOT"
    uv run detect-secrets scan $(sed 's#^#../#' "$files") \
      > /tmp/verboflex-phase02-secrets.json
    uv run python -c \
      'import json,sys; d=json.load(open(sys.argv[1])); print("\n".join(sorted(f"{p}|{x[chr(108)+chr(105)+chr(110)+chr(101)+chr(95)+chr(110)+chr(117)+chr(109)+chr(98)+chr(101)+chr(114)]}|{x[chr(116)+chr(121)+chr(112)+chr(101)]}" for p,v in d["results"].items() for x in v)))' \
      /tmp/verboflex-phase02-secrets.json >"$findings"
  )
  printf '%s\n' \
    'src/verboflex/auth/principal.py|28|Secret Keyword' \
    'src/verboflex/auth/principal.py|29|Secret Keyword' \
    'tests/api/test_admin_users.py|192|Secret Keyword' \
    'tests/architecture/test_phase2_live_provider_smoke.py|36|Secret Keyword' \
    'tests/integration/test_bitbucket_discovery.py|735|Base64 High Entropy String' \
    'tests/unit/services/test_admin_users.py|335|Secret Keyword' \
    | sort >"$expected"
  if ! diff -u "$expected" "$findings"; then
    rm -f "$files" "$findings" "$expected"
    die "secret findings drifted outside the reviewed false-positive set"
  fi
  rm -f "$files" "$findings" "$expected"
}

supply_chain_secrets_licenses() {
  (cd "$BACKEND_ROOT" && uv lock --check)
  (cd "$BACKEND_ROOT" && uv run pip-audit)
  (cd "$BACKEND_ROOT" && uv run pip-licenses --format=plain --with-urls) \
    > /tmp/verboflex-phase02-python-licenses.txt
  [ -s /tmp/verboflex-phase02-python-licenses.txt ] || die "Python license inventory is empty"
  (cd "$FRONTEND_ROOT" && npm audit --audit-level=high)
  (cd "$FRONTEND_ROOT" && npm audit --omit=dev --audit-level=moderate)
  (cd "$FRONTEND_ROOT" && npm ls --all)
  (cd "$FRONTEND_ROOT" && npm query ':root > *' --json) \
    > /tmp/verboflex-phase02-npm-provenance.json
  [ -s /tmp/verboflex-phase02-npm-provenance.json ] || die "npm provenance inventory is empty"
  scan_phase_secrets
  (cd "$FRONTEND_ROOT" && npm run test -- --run src/features/auth/storage-guard.test.ts)
}

architecture_provider_spy() {
  (
    cd "$BACKEND_ROOT"
    uv run pytest -q tests/architecture \
      tests/integration/test_bitbucket_http_adapter.py \
      tests/api/test_openapi_contract.py
  )
}

compose_browser_smoke() {
  "$GAUNTLET_DIR/phase2_smoke.sh" --mock-provider
}

final_source_state() {
  "$GAUNTLET_DIR/source_state.sh" --verify-final-before-report
}

evidence_report() {
  [ -f "$EVIDENCE_PATH" ] || die "Phase 2 evidence report is missing"
  grep -Fq -- '- Gauntlet-status: PASS' "$EVIDENCE_PATH" \
    || die "evidence does not record a passing gauntlet"
  grep -Fq -- '- Live-provider-smoke: NOT RUN — BLOCKING HUMAN CHECKPOINT' "$EVIDENCE_PATH" \
    || die "evidence does not preserve the live-provider checkpoint"
  "$GAUNTLET_DIR/source_state.sh" --verify-report-digest
}

run_gauntlet() {
  local mode=$1
  : >"$LAYER_RECORD"
  trap cleanup_test_infra EXIT INT TERM
  run_layer source-state source_state_layer
  run_layer checker-self-tests checker_self_tests
  run_layer backend-tests-coverage backend_tests_coverage
  run_layer frontend-tests-coverage frontend_tests_coverage
  run_layer types-lint-format-build types_lint_format_build
  run_layer property-suites property_suites
  run_layer changed-scope-coverage changed_scope_coverage
  run_layer mutation-authority-detectors-polling mutation_authority_detectors_polling
  run_layer migrations-openapi migrations_openapi
  run_layer supply-chain-secrets-licenses supply_chain_secrets_licenses
  run_layer architecture-provider-spy architecture_provider_spy
  run_layer compose-browser-smoke compose_browser_smoke
  run_layer final-source-state final_source_state
  if [ "$mode" = "final" ]; then
    run_layer evidence-report evidence_report
    assert_exact_layers "$EXPECTED_FINAL_LAYERS"
    printf '\nPHASE 2 GAUNTLET: PASS\n'
  else
    assert_exact_layers "$EXPECTED_CANDIDATE_LAYERS"
    printf '\nPHASE 2 GAUNTLET CANDIDATE: PASS (evidence not yet signed)\n'
  fi
  cleanup_test_infra
  trap - EXIT INT TERM
}

case "${1:-}" in
  '') run_gauntlet final ;;
  --candidate) run_gauntlet candidate ;;
  -h|--help) printf 'usage: tools/phase2_gauntlet.sh [--candidate]\n' ;;
  *) die "unknown argument: $1" ;;
esac

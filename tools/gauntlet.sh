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
readonly BACKEND_PROPERTY_MUTATION_CONFIG="$GAUNTLET_DIR/mutmut-property.toml"
readonly BACKEND_EQUIVALENT_MUTANT_MAP="$GAUNTLET_DIR/equivalent_mutants.txt"
readonly BACKEND_EQUIVALENT_MUTANT_PROOF="$GAUNTLET_DIR/verify_equivalent_mutants.py"
readonly BACKEND_RATE_LIMIT_MUTANT_PROOF="$GAUNTLET_DIR/verify_rate_limit_boundary_mutant.py"
readonly FRONTEND_COVERAGE_EXCLUSION_MAP="$GAUNTLET_DIR/frontend_coverage_exclusions.txt"

readonly EXPECTED_LAYERS="source-state
checker-self-tests
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
checker-self-tests
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
TEST_WORKER_HOSTNAME=""

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

run_required_checks() {
  local check rc
  for check in "$@"; do
    "$check" || {
      rc=$?
      return "$rc"
    }
  done
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

normalize_frontend_cobertura() {
  local input=$1 output=$2
  [ -f "$input" ] || die "frontend Cobertura input is missing"
  if ! "$BACKEND_ROOT/.venv/bin/python" -c '
from pathlib import PurePosixPath
import sys
import xml.etree.ElementTree as ET

source_path, output_path, expected_frontend = sys.argv[1:]
tree = ET.parse(source_path)
root = tree.getroot()
sources = root.findall("./sources/source")
classes = root.findall(".//class")
if len(sources) != 1 or (sources[0].text or "").rstrip("/") != expected_frontend:
    raise SystemExit(1)
if not classes:
    raise SystemExit(1)
sources[0].text = "."
for covered_class in classes:
    filename = covered_class.get("filename", "")
    path = PurePosixPath(filename)
    if path.is_absolute() or ".." in path.parts or not filename.startswith("src/"):
        raise SystemExit(1)
    covered_class.set("filename", f"frontend/{filename}")
tree.write(output_path, encoding="utf-8", xml_declaration=True)
' "$input" "$output" "$FRONTEND_ROOT"; then
    rm -f "$output"
    die "frontend Cobertura contains missing or non-canonical source paths"
  fi
}

assert_diff_coverage_nonempty() {
  local report=$1
  [ -f "$report" ] || die "diff coverage output is missing"
  if grep -Fq 'No lines with coverage information in this diff.' "$report"; then
    die "changed-line coverage matched no coverable frontend lines"
  fi
  grep -Eq '^Total:[[:space:]]+[1-9][0-9]*[[:space:]]+lines[[:space:]]*$' "$report" \
    || die "changed-line coverage did not report a nonzero frontend line total"
}

write_expected_frontend_coverage_exclusion_map() {
  printf '%s\n' \
    'frontend/src/api/client/**|OpenAPI-generated internals; drift is enforced separately' \
    'frontend/src/components/ui/**|official project-owned shadcn registry source' \
    'frontend/src/hooks/use-mobile.ts|official shadcn registry support source' \
    'frontend/src/main.tsx|entrypoint-only application wiring'
}

assert_frontend_coverage_exclusion_map() {
  local mapping=$1 expected
  [ -s "$mapping" ] || die "frontend coverage exclusion mapping is missing"
  expected=$(mktemp)
  write_expected_frontend_coverage_exclusion_map >"$expected"
  if ! cmp -s "$expected" "$mapping"; then
    rm -f "$expected"
    die "frontend coverage exclusion mapping drifted outside the approved SPEC scope"
  fi
  rm -f "$expected"
}

frontend_coverage_exclude_patterns() {
  local mapping=${1:-$FRONTEND_COVERAGE_EXCLUSION_MAP} path reason
  assert_frontend_coverage_exclusion_map "$mapping"
  while IFS='|' read -r path reason; do
    [ -n "$path" ] && [ -n "$reason" ] \
      || die "frontend coverage exclusion mapping contains an incomplete row"
    printf '*/%s\n' "$path"
  done <"$mapping"
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
  grep -Fq 'source_paths = ["src"]' "$BACKEND_ROOT/pyproject.toml" \
    || die "mutmut complete import tree is missing"
  grep -Fq 'include|review|docs/reviews/phase-01-code-security.md' \
    "$GAUNTLET_DIR/source_manifest.txt" || die "review artifact is absent from source manifest"
  [ -f "$BACKEND_EQUIVALENT_MUTANT_MAP" ] \
    || die "exact equivalent mutant mapping is missing"
  [ -x "$BACKEND_EQUIVALENT_MUTANT_PROOF" ] \
    || die "equivalent mutant proof is not executable"
  [ -x "$BACKEND_RATE_LIMIT_MUTANT_PROOF" ] \
    || die "rate limit boundary mutant proof is not executable"
  printf '%s\n' "$EXPECTED_LAYERS" >"$LAYER_RECORD"
  printf 'gauntlet preflight: PASS\n'
}

packaged_checker_self_tests() {
  local checker
  local -a checkers
  if [ "$#" -gt 0 ]; then
    checkers=("$@")
  else
    checkers=(
      "$GAUNTLET_DIR/tests/test_source_state.sh"
      "$GAUNTLET_DIR/tests/test_gauntlet.sh"
      "$GAUNTLET_DIR/tests/test_real_smoke.sh"
      "$GAUNTLET_DIR/tests/test_adversarial_auth.sh"
    )
  fi
  for checker in "${checkers[@]}"; do
    [ -x "$checker" ] || die "packaged checker self-test is not executable: $checker"
    (
      local nested_layer_record
      nested_layer_record=$(mktemp)
      trap 'rm -f "$nested_layer_record"' EXIT
      VERBOFLEX_GAUNTLET_LAYER_FILE="$nested_layer_record" "$checker"
    )
  done
}

self_test_packaged_checker_isolation() (
  local sentinel_file fake_checker
  sentinel_file=$(mktemp)
  fake_checker="${sentinel_file}.checker"
  trap 'rm -f "$sentinel_file" "$fake_checker"' EXIT
  printf '%s\n' \
    '#!/usr/bin/env bash' \
    'printf "nested-checker-overwrite\\n" >"$VERBOFLEX_GAUNTLET_LAYER_FILE"' \
    >"$fake_checker"
  chmod +x "$fake_checker"
  printf 'caller-owned-layer-record\n' >"$sentinel_file"

  VERBOFLEX_GAUNTLET_LAYER_FILE="$sentinel_file" \
    VERBOFLEX_CHECKER_ISOLATION_NESTED=1 \
    packaged_checker_self_tests "$fake_checker"

  [ "$(cat "$sentinel_file")" = 'caller-owned-layer-record' ] \
    || die 'packaged checker self-tests modified the caller-owned layer record'
  printf 'packaged checker layer isolation: PASS\n'
)

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
  if [ -n "$TEST_WORKER_PID" ] && kill -0 "$TEST_WORKER_PID" 2>/dev/null; then
    die "Celery test worker survived cleanup"
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
  TEST_POSTGRES_NAME=""
  TEST_REDIS_NAME=""
  TEST_WORKER_PID=""
  TEST_WORKER_HOSTNAME=""
}

run_lifecycle() {
  local start_function=$1 cleanup_function=$2 body_function=$3 rc
  "$start_function"
  if "$body_function"; then
    rc=0
  else
    rc=$?
  fi
  "$cleanup_function"
  return "$rc"
}

with_test_infra() {
  local body_function=$1
  run_lifecycle start_test_infra cleanup_test_infra "$body_function"
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
  TEST_WORKER_HOSTNAME="verboflex-gauntlet-$suffix@%h"
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
      exec "$BACKEND_ROOT/.venv/bin/celery" -A verboflex.worker.celery_app \
      worker --loglevel=WARNING --pool=solo --concurrency=1 \
      --hostname="$TEST_WORKER_HOSTNAME"
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

backend_tests_body() {
  (cd "$BACKEND_ROOT" && uv run pytest --randomly-seed="$RANDOM_SEED" -q)
}

backend_tests() {
  with_test_infra backend_tests_body
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

backend_static_checks() {
  (cd "$BACKEND_ROOT" && uv run ruff check src tests) &&
    (cd "$BACKEND_ROOT" && uv run ruff format --check src tests)
}

frontend_static_checks() {
  (cd "$FRONTEND_ROOT" && npm run lint) &&
    (cd "$FRONTEND_ROOT" && npm run format:check)
}

backend_complexity_check() {
  local complexity_report=/tmp/verboflex-phase01-radon.txt
  (cd "$BACKEND_ROOT" && uv run radon cc src -s -n C) >"$complexity_report"
  assert_complexity_below_c "$complexity_report"
}

lint_format_complexity() {
  run_required_checks backend_static_checks frontend_static_checks backend_complexity_check
}

backend_coverage_body() {
  (cd "$BACKEND_ROOT" && uv run pytest --randomly-seed="$RANDOM_SEED" -q \
    --cov=verboflex --cov-branch --cov-report="xml:$BACKEND_COVERAGE")
}

changed_line_coverage() (
  local frontend_coverage_workspace normalized_frontend_coverage frontend_diff_report
  local frontend_diff_rc
  local -a frontend_excludes
  frontend_coverage_workspace=$(mktemp -d)
  normalized_frontend_coverage="$frontend_coverage_workspace/frontend-coverage.xml"
  frontend_diff_report="$frontend_coverage_workspace/diff-cover-report.txt"
  trap 'rm -rf "$frontend_coverage_workspace"' EXIT INT TERM
  with_test_infra backend_coverage_body
  (cd "$FRONTEND_ROOT" && npm run test:coverage -- --sequence.shuffle --sequence.seed="$RANDOM_SEED" \
    --coverage.provider=v8 --coverage.reporter=text --coverage.reporter=cobertura \
    --coverage.reportsDirectory="$FRONTEND_COVERAGE_DIR")
  (cd "$BACKEND_ROOT" && uv run diff-cover "$BACKEND_COVERAGE" \
    --compare-branch "$PHASE_BASE_COMMIT" --branch-coverage --fail-under 100 \
    --exclude 'backend/alembic/**' 'backend/src/verboflex/main.py' \
      'backend/src/verboflex/scripts/export_openapi.py')
  normalize_frontend_cobertura \
    "$FRONTEND_COVERAGE_DIR/cobertura-coverage.xml" "$normalized_frontend_coverage"
  while IFS= read -r exclusion; do
    frontend_excludes+=("$exclusion")
  done < <(frontend_coverage_exclude_patterns)
  set +e
  (cd "$REPO_ROOT" && "$BACKEND_ROOT/.venv/bin/diff-cover" "$normalized_frontend_coverage" \
    --compare-branch "$PHASE_BASE_COMMIT" --branch-coverage --fail-under 100 \
    --exclude "${frontend_excludes[@]}") >"$frontend_diff_report" 2>&1
  frontend_diff_rc=$?
  set -e
  sed -n '1,240p' "$frontend_diff_report"
  [ "$frontend_diff_rc" -eq 0 ] || die "frontend changed-line coverage failed"
  assert_diff_coverage_nonempty "$frontend_diff_report"
)

create_fresh_backend_workspace() {
  local workspace
  workspace=$(mktemp -d)
  if ! git -C "$REPO_ROOT" archive --format=tar HEAD backend | tar -xf - -C "$workspace"; then
    rm -rf "$workspace"
    die "could not materialize fresh backend mutation workspace"
  fi
  [ ! -e "$workspace/backend/mutants" ] || {
    rm -rf "$workspace"
    die "fresh backend mutation workspace unexpectedly contains cached mutants"
  }
  printf '%s\n' "$workspace"
}

assert_mutation_stats_fresh() {
  local stats_file=$1 totals total killed invalid
  [ -f "$stats_file" ] || die "mutation statistics are missing"
  totals=$("$BACKEND_ROOT/.venv/bin/python" -c '
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
keys = ("survived", "no_tests", "skipped", "suspicious", "timeout", "check_was_interrupted_by_user", "segfault")
print(data.get("total", 0), data.get("killed", 0), sum(data.get(key, 0) for key in keys))
' "$stats_file") || die "mutation statistics could not be parsed"
  read -r total killed invalid <<EOF
$totals
EOF
  [ "$total" -gt 0 ] || die "fresh mutation run produced zero mutants"
  [ "$killed" -eq "$total" ] || die "fresh mutation run did not kill every mutant"
  [ "$invalid" -eq 0 ] || die "fresh mutation run contains a non-killed verdict"
}

expected_equivalent_mutation_results() {
  printf '%s\n' \
    'verboflex.auth.refresh_sessions.x_logout_rate_limit_user_id__mutmut_18: survived' \
    'verboflex.auth.refresh_sessions.x_logout_rate_limit_user_id__mutmut_20: survived'
}

assert_exact_equivalent_mutation_results() {
  local mutation_results=$1 actual expected
  actual=$(printf '%s\n' "$mutation_results" | sed '/^[[:space:]]*$/d; s/^[[:space:]]*//' | sort)
  expected=$(expected_equivalent_mutation_results | sort)
  if [ "$actual" != "$expected" ]; then
    printf 'expected exact equivalent mutation results:\n%s\n' "$expected" >&2
    printf 'actual mutation results:\n%s\n' "$actual" >&2
    die "equivalent mutation verdict set drifted"
  fi
}

assert_full_mutation_stats_fresh() {
  local stats_file=$1 totals total killed survived invalid
  [ -f "$stats_file" ] || die "mutation statistics are missing"
  totals=$("$BACKEND_ROOT/.venv/bin/python" -c '
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
keys = ("no_tests", "skipped", "suspicious", "timeout", "check_was_interrupted_by_user", "segfault")
print(data.get("total", 0), data.get("killed", 0), data.get("survived", 0), sum(data.get(key, 0) for key in keys))
' "$stats_file") || die "mutation statistics could not be parsed"
  read -r total killed survived invalid <<EOF
$totals
EOF
  [ "$total" -eq 893 ] || die "complete mutation total drifted from the reviewed source set"
  [ "$killed" -eq 891 ] || die "not every non-equivalent mutant was killed"
  [ "$survived" -eq 2 ] || die "equivalent mutation count drifted"
  [ $((killed + survived)) -eq "$total" ] \
    || die "fresh mutation run contains an unclassified verdict"
  [ "$invalid" -eq 0 ] || die "fresh mutation run contains a forbidden verdict"
}

assert_equivalent_mutant_show() {
  local mutant_name=$1 mutant_show=$2 expected_added actual_changes expected_changes
  case "$mutant_name" in
    verboflex.auth.refresh_sessions.x_logout_rate_limit_user_id__mutmut_18)
      expected_added='+            .join(User, None)'
      ;;
    verboflex.auth.refresh_sessions.x_logout_rate_limit_user_id__mutmut_20)
      expected_added='+            .join(User, )'
      ;;
    *) die "unregistered equivalent mutant requested for diff proof" ;;
  esac
  printf '%s\n' "$mutant_show" \
    | grep -Fq "# $mutant_name: survived" \
    || die "equivalent mutant is not a current survivor"
  actual_changes=$(printf '%s\n' "$mutant_show" \
    | sed -n '/^[-+]/ { /^---/d; /^+++/d; p; }')
  expected_changes=$(printf '%s\n' \
    '-            .join(User, User.id == AuthSession.user_id)' \
    "$expected_added")
  [ "$actual_changes" = "$expected_changes" ] \
    || die "equivalent mutant diff drifted outside the reviewed join transformation"
}

prove_exact_equivalent_mutants() {
  local mutation_backend=$1 mutant_name mutant_show
  "$BACKEND_ROOT/.venv/bin/python" "$BACKEND_EQUIVALENT_MUTANT_PROOF" \
    --mapping "$BACKEND_EQUIVALENT_MUTANT_MAP" --backend-root "$mutation_backend"
  for mutant_name in \
    verboflex.auth.refresh_sessions.x_logout_rate_limit_user_id__mutmut_18 \
    verboflex.auth.refresh_sessions.x_logout_rate_limit_user_id__mutmut_20; do
    mutant_show=$(cd "$mutation_backend" && "$BACKEND_ROOT/.venv/bin/mutmut" show "$mutant_name") \
      || die "equivalent mutant diff could not be inspected"
    assert_equivalent_mutant_show "$mutant_name" "$mutant_show"
  done
}

backend_mutation_body() (
  local workspace mutation_backend mutation_results mutation_stats
  workspace=$(create_fresh_backend_workspace)
  trap 'rm -rf "$workspace"' EXIT INT TERM
  mutation_backend="$workspace/backend"
  mutation_stats="$mutation_backend/mutants/mutmut-cicd-stats.json"
  (cd "$mutation_backend" && "$BACKEND_ROOT/.venv/bin/mutmut" run)
  (cd "$mutation_backend" && "$BACKEND_ROOT/.venv/bin/mutmut" export-cicd-stats)
  mutation_results=$(cd "$mutation_backend" && "$BACKEND_ROOT/.venv/bin/mutmut" results)
  assert_exact_equivalent_mutation_results "$mutation_results"
  assert_full_mutation_stats_fresh "$mutation_stats"
  prove_exact_equivalent_mutants "$mutation_backend"
)

backend_property_mutation() (
  local workspace mutation_backend mutation_results mutation_stats
  workspace=$(create_fresh_backend_workspace)
  trap 'rm -rf "$workspace"' EXIT INT TERM
  mutation_backend="$workspace/backend"
  mutation_stats="$mutation_backend/mutants/mutmut-cicd-stats.json"
  cp "$BACKEND_PROPERTY_MUTATION_CONFIG" "$mutation_backend/pyproject.toml"
  (cd "$mutation_backend" && "$BACKEND_ROOT/.venv/bin/mutmut" run)
  (cd "$mutation_backend" && "$BACKEND_ROOT/.venv/bin/mutmut" export-cicd-stats)
  mutation_results=$(cd "$mutation_backend" && "$BACKEND_ROOT/.venv/bin/mutmut" results)
  assert_no_surviving_mutants "$mutation_results"
  assert_mutation_stats_fresh "$mutation_stats"
)

frontend_property_mutation() {
  (cd "$FRONTEND_ROOT" && npm run test:mutation -- \
    --mutate 'src/features/auth/session.tsx:39-91' \
    --testFiles 'src/features/auth/session.property.test.ts' \
    --reporters clear-text \
    --tempDirName '.stryker-property-tmp' \
    --cleanTempDir always)
}

assert_no_surviving_mutants() {
  local mutation_results=$1
  if [ -n "$mutation_results" ]; then
    printf '%s\n' "$mutation_results" >&2
    die "surviving mutation verdicts are forbidden"
  fi
}

mutation_properties() {
  "$BACKEND_ROOT/.venv/bin/python" "$BACKEND_RATE_LIMIT_MUTANT_PROOF" \
    --backend-root "$BACKEND_ROOT"
  with_test_infra backend_mutation_body
  backend_property_mutation
  (cd "$FRONTEND_ROOT" && npm run test:mutation)
  frontend_property_mutation
  (cd "$BACKEND_ROOT" && uv run pytest -q tests/auth/test_access_tokens.py \
    tests/auth/test_passwords.py tests/core/test_config.py)
  (cd "$FRONTEND_ROOT" && npm run test -- --run src/features/auth/session.property.test.ts)
}

migration_rehearsal_body() {
  (cd "$BACKEND_ROOT" && uv run pytest -q tests/integration/test_migrations.py)
}

migration_rehearsal() {
  with_test_infra migration_rehearsal_body
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
  case "$output" in
    *'diff --git'*) ;;
    *) die "OpenAPI drift control failed for the wrong reason" ;;
  esac
  printf 'OpenAPI drift negative control: PASS\n'
)

openapi_drift() {
  openapi_negative_control
  (cd "$FRONTEND_ROOT" && npm run api:check)
}

write_audited_secret_policy() {
  cat <<'AUDITED_FALSE_POSITIVES'
src/verboflex/auth/access_tokens.py|16|Secret Keyword|3591079abcc3407a2c2ed76661ec29a7ec0d1cb8
src/verboflex/auth/access_tokens.py|17|Secret Keyword|06c49c9b4bd885fbdc2a04cc3f65b214292b0da9
src/verboflex/auth/access_tokens.py|19|Secret Keyword|411a5e3d10eceaebc65194fdafdd05fb8e432e38
src/verboflex/auth/password_change.py|25|Secret Keyword|443fe4e817f15f5b62b02db228cd59ec2d5cfc8f
src/verboflex/auth/password_change.py|26|Secret Keyword|3b8788b039ebfe732e34b976cabe8fe87a3ceb17
src/verboflex/auth/password_change.py|55|Secret Keyword|42213dc7f2ef60d5d6744c00f091a46b2161dda5
src/verboflex/auth/principal.py|28|Secret Keyword|3591079abcc3407a2c2ed76661ec29a7ec0d1cb8
src/verboflex/auth/principal.py|29|Secret Keyword|82bde2d99285779d940c36fdcdb9c3e9afa40d2f
src/verboflex/auth/refresh_sessions.py|20|Base64 High Entropy String|e582429052cdb908833560f6f7582d232de37c4d
tests/api/test_admin_users.py|192|Secret Keyword|cbd35a7eedd58ee2f4ab223644a0a2b73a635bbd
tests/api/test_rate_limits.py|189|Secret Keyword|5ac066cfb3bcf9973a0b40daeb7f5606103c1bd3
tests/api/test_system_status.py|109|Basic Auth Credentials|e5e9fa1ba31ecd1ae84f75caaa474f3a663f05f4
tests/architecture/test_phase2_gap_closure.py|101|Hex High Entropy String|861c51f9e1bcf75dd79a1cac09d53a876442638d
tests/architecture/test_phase2_gap_closure.py|102|Hex High Entropy String|e3fec03c2aae0f002e0e60a8d15c8aee11bcf3e7
tests/architecture/test_phase2_gap_closure.py|103|Hex High Entropy String|47d93d606e2b04f5f317c24a01fd44e6dc43e592
tests/architecture/test_phase2_gap_closure.py|104|Hex High Entropy String|a155a53fbc7f26ec0526caf8be1246aea7f0fe8b
tests/architecture/test_phase2_gap_closure.py|105|Hex High Entropy String|32f2c288943d38941b79b702cc253b1f814376be
tests/architecture/test_phase2_gap_closure.py|106|Hex High Entropy String|5162b7f6fc82261331603793a1a5bfa1d7976275
tests/architecture/test_phase2_gap_closure.py|107|Hex High Entropy String|06a4b4c4c936aa7862fbe37149451abcc8444ab0
tests/architecture/test_phase2_gap_closure.py|108|Hex High Entropy String|4602cbb9ed906875802566ad74f6779f952dc6dc
tests/architecture/test_phase2_gap_closure.py|128|Hex High Entropy String|5f7aed697833d16ba9e41cc8f000cfba6f97fe77
tests/architecture/test_phase2_gap_closure.py|129|Hex High Entropy String|5d70bc15dfa4f1e23e34e0e5dfdd2ad6d006eabe
tests/architecture/test_phase2_gap_closure.py|130|Hex High Entropy String|7f7be4f4e4c5e506bf045d221b44449c2d18e500
tests/architecture/test_phase2_gap_closure.py|131|Hex High Entropy String|dddd6827f8d987ee84817dabb218c536fc3a1056
tests/architecture/test_phase2_gap_closure.py|132|Hex High Entropy String|ec644a764ac25986979e1da959adeab9d16ee728
tests/architecture/test_phase2_gap_closure.py|133|Hex High Entropy String|0bee47b9490683452e0f043a89f001bd59e90cb9
tests/architecture/test_phase2_gap_closure.py|134|Hex High Entropy String|efdf916626799c4045557767bc7db60b53f34257
tests/architecture/test_phase2_gap_closure.py|135|Hex High Entropy String|88b88c99e9961eeb48d847cb4faeb1e0d74f6cf4
tests/architecture/test_phase2_gap_closure.py|136|Hex High Entropy String|da0661c828b3507a12e6aa79f156b5249a31db04
tests/architecture/test_phase2_gap_closure.py|139|Hex High Entropy String|768c3725acced65278c65d81fc7d3b3877d3e452
tests/architecture/test_phase2_gap_closure.py|140|Hex High Entropy String|b73ba3448a019c2d2af515211f3bf34e953737ce
tests/architecture/test_phase2_gap_closure.py|141|Hex High Entropy String|e28039f8f923290107561ec763be989189a3109f
tests/architecture/test_phase2_gap_closure.py|142|Hex High Entropy String|e44800d52286f74b9e510b8a736f92c98891eab3
tests/architecture/test_phase2_gap_closure.py|143|Hex High Entropy String|bddc89a074e272d22c24ef8852d0592ba4ebb4c2
tests/architecture/test_phase2_gap_closure.py|144|Hex High Entropy String|bd9ef523c312ae923aa59e0b3e6b0e456efefd2c
tests/architecture/test_phase2_gap_closure.py|145|Hex High Entropy String|24b7ea4ba096aefdf15771974e329c2ea984f028
tests/architecture/test_phase2_gap_closure.py|146|Hex High Entropy String|c16a1ab5924ff06b09bc82b7b35770841c58c258
tests/architecture/test_phase2_gap_closure.py|147|Hex High Entropy String|80a3beaa47c3497520fadfa8357e43a44b22a952
tests/architecture/test_phase2_gap_closure.py|148|Hex High Entropy String|862b107e8f28d16105624ba1ef43a1b44ee6ccc4
tests/architecture/test_phase2_gap_closure.py|149|Hex High Entropy String|c12f10aa321327ca1b2fa23f646b144d3a5f9001
tests/architecture/test_phase2_gap_closure.py|150|Hex High Entropy String|d8a775307a511052a80f0a68d5e4c8155f10a379
tests/architecture/test_phase2_gap_closure.py|151|Hex High Entropy String|bec854fe0dfada0277e30c78d9db6977dadd73f9
tests/architecture/test_phase2_gap_closure.py|152|Hex High Entropy String|b85040ed2f2d9aaedff5a3bee71445aee95bad01
tests/architecture/test_phase2_gap_closure.py|153|Hex High Entropy String|f873e97615618a3da956a943170cb0bffc015d82
tests/architecture/test_phase2_gap_closure.py|154|Hex High Entropy String|9fce54fa9bed3604b4ccb57c7a4e5da93e7033db
tests/architecture/test_phase2_gap_closure.py|155|Hex High Entropy String|57094b273076e6cf20d8ed7d31d687f02fec1072
tests/architecture/test_phase2_gap_closure.py|156|Hex High Entropy String|6bc309f0da813b64d2da34cf24988e712e7b34bd
tests/architecture/test_phase2_gap_closure.py|157|Hex High Entropy String|bf4fd9a58861808dc5783407c24b843535ea6371
tests/architecture/test_phase2_gap_closure.py|158|Hex High Entropy String|c9a34cdd23689844f55c6c62b9fad408e936fbc8
tests/architecture/test_phase2_gap_closure.py|159|Hex High Entropy String|71f2d5eda8109fd7467f5937b4dabedf5985b697
tests/architecture/test_phase2_gap_closure.py|160|Hex High Entropy String|851e31e68ef17dd86e40a36da9081aea087e425e
tests/architecture/test_phase2_gap_closure.py|161|Hex High Entropy String|e2decc5a5e8f29c9217d9540057b52b83ba1c266
tests/architecture/test_phase2_gap_closure.py|162|Hex High Entropy String|ad4e89d456ec9741ecdd88005e79d1befbb3fbe4
tests/architecture/test_phase2_gap_closure.py|163|Hex High Entropy String|6b99eb1094f1e2e0d1c20f3ca5d1b7353826cd7a
tests/architecture/test_phase2_gap_closure.py|164|Hex High Entropy String|0a59fd6c077f8b93441e172545b6479d6f554ca0
tests/architecture/test_phase2_gap_closure.py|165|Hex High Entropy String|823fe230db0fa34b559e569b71f384e61f7936c1
tests/architecture/test_phase2_gap_closure.py|166|Hex High Entropy String|11c5a7f9cd758ba10bfef9b63a07f1226c07ae5c
tests/architecture/test_phase2_gap_closure.py|167|Hex High Entropy String|37c8042bce182f8d353ed58e688ba01ac4f14098
tests/architecture/test_phase2_gap_closure.py|168|Hex High Entropy String|3df8f20294b52f0c7a84c9bf88e4d3df109743b4
tests/architecture/test_phase2_gap_closure.py|169|Hex High Entropy String|82c01157711f96082e514e6a77bf18545ab5067b
tests/architecture/test_phase2_gap_closure.py|170|Hex High Entropy String|55a2b7d75d5dc7eac8ffb47c4c91f5c3a4a7e9f3
tests/architecture/test_phase2_gap_closure.py|171|Hex High Entropy String|863294e273d66a71051e7fb8face42f1a2eb0a62
tests/architecture/test_phase2_gap_closure.py|41|Hex High Entropy String|84272060a1b4a958cd3b38f5f0f59c7494d47e5b
tests/architecture/test_phase2_gap_closure.py|43|Hex High Entropy String|1129b095b56d1c5a58898c1ce78a8a39ef621d26
tests/architecture/test_phase2_gap_closure.py|44|Hex High Entropy String|81ab625e90a1129d3e2f9920e7b6b7cc7397d334
tests/architecture/test_phase2_gap_closure.py|45|Hex High Entropy String|7f5ef0452e0c7b977c763781b6f70649c2fa71a0
tests/architecture/test_phase2_gap_closure.py|46|Hex High Entropy String|1e6a6fc292cc473f4525dbccad3e3eaf32426356
tests/architecture/test_phase2_gap_closure.py|47|Hex High Entropy String|bf174e02ae98e85b96b464bf81a908c1b5a9fa2f
tests/architecture/test_phase2_gap_closure.py|48|Hex High Entropy String|d6834e2141dc4b3c4b01de8a23cc1cb31f9a1cfa
tests/architecture/test_phase2_gap_closure.py|49|Hex High Entropy String|7f9ae4ed580cc82b1b6be40a23f272140bbc7476
tests/architecture/test_phase2_gap_closure.py|51|Hex High Entropy String|cf0cd4431b51a8b8cdd6128ef0a27394d6b2b7e1
tests/architecture/test_phase2_gap_closure.py|52|Hex High Entropy String|4db8a39cffc2954b8e48636ee85e02859387e9a3
tests/architecture/test_phase2_gap_closure.py|53|Hex High Entropy String|b76e43aed365048c97424e1cfcf0170e61aeb692
tests/architecture/test_phase2_gap_closure.py|55|Hex High Entropy String|d8cd5c961305d97f853e29512bd143182626c358
tests/architecture/test_phase2_gap_closure.py|56|Hex High Entropy String|76c82148887d6acac01f51d3fee846761f8d74f7
tests/architecture/test_phase2_gap_closure.py|57|Hex High Entropy String|69770043673fe5e60ca9f4aae2dc470f9248fddf
tests/architecture/test_phase2_gap_closure.py|60|Hex High Entropy String|8828eadd103b37eaa11aa741e95dc397ba7597d6
tests/architecture/test_phase2_gap_closure.py|61|Hex High Entropy String|aea6af1fd9fb990a85304f558c6860629c2ded70
tests/architecture/test_phase2_gap_closure.py|62|Hex High Entropy String|562bb26bf0656b9ae707a4f535b299118500639f
tests/architecture/test_phase2_gap_closure.py|63|Hex High Entropy String|4b587c3c69dfd5ccf2823c455002130c930d490d
tests/architecture/test_phase2_gap_closure.py|64|Hex High Entropy String|e60d885472c681c9673909d89b4dac77a0a2033e
tests/architecture/test_phase2_gap_closure.py|65|Hex High Entropy String|2bfdb456589e0ad7a13491152d8aa1e2899f11a8
tests/architecture/test_phase2_gap_closure.py|66|Hex High Entropy String|ad2bf777b582262c72344aa285996ab29e2c3a29
tests/architecture/test_phase2_gap_closure.py|67|Hex High Entropy String|d922e3de97b8d42d8353fdee1bade49e96763e76
tests/architecture/test_phase2_gap_closure.py|68|Hex High Entropy String|57de6d1704fcfc8b0486673dafd8e57563cb813d
tests/architecture/test_phase2_gap_closure.py|69|Hex High Entropy String|d740d494b499202e127d5777a7acba1a0a459429
tests/architecture/test_phase2_gap_closure.py|70|Hex High Entropy String|0edf0df42184e8e637e1f02de37fa1c539d045b1
tests/architecture/test_phase2_gap_closure.py|71|Hex High Entropy String|1bd3f19008dacbfa8d08402566ec721419b21c79
tests/architecture/test_phase2_gap_closure.py|72|Hex High Entropy String|c10917cc93021b12770e8575570b063dd12edfdb
tests/architecture/test_phase2_gap_closure.py|73|Hex High Entropy String|16057707afdd498ae5478d5486e85173fa20e237
tests/architecture/test_phase2_gap_closure.py|74|Hex High Entropy String|396782bd9ba8540ec6787ee9354d87d70fc5e822
tests/architecture/test_phase2_gap_closure.py|75|Hex High Entropy String|94e0b1ddfedd502a19d22b45445a3bd9621b8b7a
tests/architecture/test_phase2_gap_closure.py|77|Hex High Entropy String|2e1b0e04a5cb43582ddf32197e8049f567df8c5c
tests/architecture/test_phase2_gap_closure.py|78|Hex High Entropy String|4bf9f72d2c506a1dc47dbe9bd7d4afadc06d52d3
tests/architecture/test_phase2_gap_closure.py|79|Hex High Entropy String|687f8291590033bfe8a913110c535b8159f5d66d
tests/architecture/test_phase2_gap_closure.py|80|Hex High Entropy String|463d7c3109f2ecfa6cb927c53ed986be6ded544e
tests/architecture/test_phase2_gap_closure.py|81|Hex High Entropy String|07633598be1a9cc0f8ff4eea50b53019d6b5c811
tests/architecture/test_phase2_gap_closure.py|82|Hex High Entropy String|e0267f8c6a7f93f317d4e3ee080d3b6b34c89b8c
tests/architecture/test_phase2_gap_closure.py|85|Hex High Entropy String|c943b7c5d845dfd3f552e0c2155b3528a8ad31ef
tests/architecture/test_phase2_gap_closure.py|86|Hex High Entropy String|9941c20e13fe5266a34240bba6a7d074cc99f08a
tests/architecture/test_phase2_gap_closure.py|87|Hex High Entropy String|9b99026574d85e39fa678c435b217af18e026e3e
tests/architecture/test_phase2_gap_closure.py|90|Hex High Entropy String|35870f97f8793daa8fd5f889556cf8b204f07acd
tests/architecture/test_phase2_gap_closure.py|91|Hex High Entropy String|c56e9fc5e1743b66049cf86c1865e66559a3c065
tests/architecture/test_phase2_gap_closure.py|92|Hex High Entropy String|db366f18fe58722e9d93ba49c9fcd6961947bf3c
tests/architecture/test_phase2_gap_closure.py|93|Hex High Entropy String|c008ca85001a9b0db883a925b292e056b7de3ad2
tests/architecture/test_phase2_gap_closure.py|94|Hex High Entropy String|b30221ec453984441e0fcfb20a55dfcc598bf316
tests/architecture/test_phase2_gap_closure.py|95|Hex High Entropy String|da7942e506abd934e8e9b281ec0cfacf8d928254
tests/architecture/test_phase2_gap_closure.py|96|Hex High Entropy String|0cc14d34ab3a94303db0387e6d7635a957c94fc8
tests/architecture/test_phase2_gap_closure.py|97|Hex High Entropy String|960b27719c11d5aad565fd4709b3dde569769a18
tests/architecture/test_phase2_gap_closure.py|98|Hex High Entropy String|c9a9a0ddf0c2adf994402955cc84944b7e14f351
tests/architecture/test_phase2_live_provider_smoke.py|123|Secret Keyword|70fc6e0d262430f6631fe63e5bfeea516e31a638
tests/architecture/test_phase2_live_provider_smoke.py|124|Secret Keyword|1de639a3d621921d3f0f3b5a1d7ebb55ae2d14bf
tests/architecture/test_phase2_live_provider_smoke.py|162|Secret Keyword|691ad370655555d3143654d4e7ecdda5282437c5
tests/auth/test_bootstrap_admin.py|137|Secret Keyword|985a4d67132193977275067aca18c13f8c8371c8
tests/auth/test_bootstrap_admin.py|148|Secret Keyword|d36b093dec485bfd20ef697ca6c1ad79e1ac9210
tests/auth/test_bootstrap_admin.py|236|Secret Keyword|3da24dfed48aa2721da14e6f79e588440b934675
tests/auth/test_bootstrap_admin.py|296|Secret Keyword|028e59d8204d08fecd6aad12434b872fe4319f6d
tests/auth/test_bootstrap_admin.py|411|Secret Keyword|5d9dec21ffdbb45c64f0ea2b1abf3b25c2afc728
tests/auth/test_bootstrap_admin.py|589|Secret Keyword|1123e04e3b43d460543f1b0bf94e67a0a636b2cc
tests/auth/test_bootstrap_admin.py|692|Secret Keyword|cdd076c21ce35f40d40b6c16d12bd40876050a6f
tests/auth/test_bootstrap_admin.py|770|Secret Keyword|18468712bc6eede8cb7adf8932b073bf56773a11
tests/auth/test_login.py|45|Secret Keyword|e7e0ea25217b715c566268c0607e48acef3b9ccf
tests/auth/test_password_change.py|188|Secret Keyword|a95b347855753c3b784594a28fa00ec116430d1c
tests/auth/test_password_change.py|36|Secret Keyword|bc27f09f74d82f81b559a27a26bd03f580960364
tests/auth/test_password_change.py|37|Secret Keyword|ba8d4568d2e2f6531c78080cedddb3a16f08afd5
tests/integration/test_bitbucket_discovery.py|735|Base64 High Entropy String|8eb6a2543a00fa38b9a717242e592d4afa7f80cf
tests/unit/services/test_admin_users.py|596|Secret Keyword|374997990c71d0ff9a4f7a41bc0ceb63a2110237
AUDITED_FALSE_POSITIVES
}

assert_audited_secret_findings() {
  local findings_file=$1 policy_file
  policy_file=$(mktemp)
  write_audited_secret_policy >"$policy_file"
  if ! diff -u "$policy_file" "$findings_file"; then
    rm -f "$policy_file"
    die "detected secrets outside the audited false-positive map"
  fi
  rm -f "$policy_file"
}

scan_repository_secrets() {
  local files_file findings_file
  files_file=$(mktemp)
  findings_file=$(mktemp)
  git -C "$REPO_ROOT" ls-files | \
    grep -Ev '^(backend/uv.lock|frontend/package-lock.json|\.planning/)' >"$files_file"
  (cd "$BACKEND_ROOT" && uv run detect-secrets scan $(sed 's#^#../#' "$files_file")) >"$SECRET_SCAN"
  (cd "$BACKEND_ROOT" && uv run python -c \
    'import json,sys; d=json.load(open(sys.argv[1])); print("\n".join(sorted(f"{p}|{x[chr(108)+chr(105)+chr(110)+chr(101)+chr(95)+chr(110)+chr(117)+chr(109)+chr(98)+chr(101)+chr(114)]}|{x[chr(116)+chr(121)+chr(112)+chr(101)]}|{x[chr(104)+chr(97)+chr(115)+chr(104)+chr(101)+chr(100)+chr(95)+chr(115)+chr(101)+chr(99)+chr(114)+chr(101)+chr(116)]}" for p,v in d["results"].items() for x in v)))' \
    "$SECRET_SCAN") >"$findings_file"
  assert_audited_secret_findings "$findings_file"
  rm -f "$files_file" "$findings_file"
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
  run_layer checker-self-tests packaged_checker_self_tests
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
  run_layer checker-self-tests packaged_checker_self_tests
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

self_test_infra_lifecycle() (
  local fixture log rc
  fixture=$(mktemp -d)
  log="$fixture/lifecycle.log"
  trap 'rm -rf "$fixture"' EXIT INT TERM
  lifecycle_start() { printf 'start\n' >>"$log"; }
  lifecycle_cleanup() { printf 'cleanup\n' >>"$log"; }
  lifecycle_success() { printf 'body\n' >>"$log"; }
  lifecycle_failure() { printf 'body\n' >>"$log"; return 42; }
  run_lifecycle lifecycle_start lifecycle_cleanup lifecycle_success
  printf '%s\n' start body cleanup | diff -u - "$log" >/dev/null \
    || die "success lifecycle order drifted"
  : >"$log"
  set +e
  run_lifecycle lifecycle_start lifecycle_cleanup lifecycle_failure
  rc=$?
  set -e
  [ "$rc" -eq 42 ] || die "failure lifecycle status was not propagated"
  printf '%s\n' start body cleanup | diff -u - "$log" >/dev/null \
    || die "failure lifecycle omitted cleanup"
  printf 'test infrastructure lifecycle: PASS\n'
)

self_test_infra_failure_cleanup() (
  local fixture identity output rc worker_pid worker_hostname postgres_name redis_name processes
  fixture=$(mktemp -d)
  identity="$fixture/identity"
  output="$fixture/candidate-failure.log"
  trap 'cleanup_test_infra; rm -rf "$fixture"' EXIT INT TERM

  failure_probe_start() {
    start_test_infra
    printf '%s\n%s\n%s\n%s\n' \
      "$TEST_WORKER_PID" "$TEST_WORKER_HOSTNAME" \
      "$TEST_POSTGRES_NAME" "$TEST_REDIS_NAME" >"$identity"
  }
  failure_probe_backend_layer() {
    run_lifecycle failure_probe_start cleanup_test_infra true
  }
  failure_probe_frontend_layer() { return 42; }

  set +e
  (
    trap cleanup_test_infra EXIT INT TERM
    run_layer backend-tests failure_probe_backend_layer
    run_layer frontend-tests-browser failure_probe_frontend_layer
  ) >"$output" 2>&1
  rc=$?
  set -e
  [ "$rc" -ne 0 ] || die "controlled frontend layer failure unexpectedly passed"
  grep -Fq 'layer frontend-tests-browser failed with exit code 42' "$output" \
    || die "controlled candidate sequence failed for the wrong reason"
  [ -s "$identity" ] || die "failure cleanup probe did not record infrastructure identity"
  worker_pid=$(sed -n '1p' "$identity")
  worker_hostname=$(sed -n '2p' "$identity")
  postgres_name=$(sed -n '3p' "$identity")
  redis_name=$(sed -n '4p' "$identity")
  [ -n "$worker_pid" ] && [ -n "$worker_hostname" ] \
    && [ -n "$postgres_name" ] && [ -n "$redis_name" ] \
    || die "failure cleanup probe recorded incomplete infrastructure identity"
  ! kill -0 "$worker_pid" 2>/dev/null \
    || die "controlled candidate failure left the tracked Celery worker running"
  processes=$(ps -axo command=)
  ! printf '%s\n' "$processes" | grep -Fq -- "--hostname=$worker_hostname" \
    || die "controlled candidate failure orphaned a Celery worker"
  ! docker ps -a --format '{{.Names}}' | grep -Fxq "$postgres_name" \
    || die "controlled candidate failure left PostgreSQL test infrastructure"
  ! docker ps -a --format '{{.Names}}' | grep -Fxq "$redis_name" \
    || die "controlled candidate failure left Redis test infrastructure"
  printf 'test infrastructure failure cleanup: PASS\n'
)

self_test_mutation_verdict() {
  assert_no_surviving_mutants ""
  expect_control_failure mutation-survivor 'surviving mutation verdicts are forbidden' \
    assert_no_surviving_mutants '    example.module.x_behavior__mutmut_1: survived'
  printf 'mutation verdict negative control: PASS\n'
}

self_test_equivalent_mutants() (
  local fixture mapping valid_stats invalid_stats valid_results valid_show invalid_show
  fixture=$(mktemp -d)
  mapping="$fixture/equivalent-mutants.txt"
  valid_stats="$fixture/valid-stats.json"
  invalid_stats="$fixture/invalid-stats.json"
  trap 'rm -rf "$fixture"' EXIT INT TERM

  valid_results=$(expected_equivalent_mutation_results)
  assert_exact_equivalent_mutation_results "$valid_results"
  expect_control_failure equivalent-mutant-extra 'equivalent mutation verdict set drifted' \
    assert_exact_equivalent_mutation_results \
    "$valid_results
example.module.x_unreviewed__mutmut_1: survived"
  expect_control_failure equivalent-mutant-missing 'equivalent mutation verdict set drifted' \
    assert_exact_equivalent_mutation_results \
    'verboflex.auth.refresh_sessions.x_logout_rate_limit_user_id__mutmut_18: survived'

  printf '%s\n' \
    '{"killed": 891, "survived": 2, "total": 893, "no_tests": 0, "skipped": 0, "suspicious": 0, "timeout": 0, "check_was_interrupted_by_user": 0, "segfault": 0}' \
    >"$valid_stats"
  printf '%s\n' \
    '{"killed": 890, "survived": 3, "total": 893, "no_tests": 0, "skipped": 0, "suspicious": 0, "timeout": 0, "check_was_interrupted_by_user": 0, "segfault": 0}' \
    >"$invalid_stats"
  assert_full_mutation_stats_fresh "$valid_stats"
  expect_control_failure equivalent-mutant-count 'not every non-equivalent mutant was killed' \
    assert_full_mutation_stats_fresh "$invalid_stats"

  "$BACKEND_ROOT/.venv/bin/python" "$BACKEND_EQUIVALENT_MUTANT_PROOF" \
    --mapping "$BACKEND_EQUIVALENT_MUTANT_MAP" \
    --backend-root "$BACKEND_ROOT" --self-test
  cp "$BACKEND_EQUIVALENT_MUTANT_MAP" "$mapping"
  printf '%s\n' \
    'example.module.x_unreviewed__mutmut_1|unreviewed|forbidden broadening' >>"$mapping"
  expect_control_failure equivalent-mutant-mapping 'equivalent mutant mapping drifted' \
    "$BACKEND_ROOT/.venv/bin/python" "$BACKEND_EQUIVALENT_MUTANT_PROOF" \
    --mapping "$mapping" \
    --backend-root "$BACKEND_ROOT"

  valid_show=$(printf '%s\n' \
    '# verboflex.auth.refresh_sessions.x_logout_rate_limit_user_id__mutmut_18: survived' \
    '--- src/verboflex/auth/refresh_sessions.py' \
    '+++ src/verboflex/auth/refresh_sessions.py' \
    '-            .join(User, User.id == AuthSession.user_id)' \
    '+            .join(User, None)')
  assert_equivalent_mutant_show \
    verboflex.auth.refresh_sessions.x_logout_rate_limit_user_id__mutmut_18 \
    "$valid_show"
  invalid_show=$(printf '%s\n' \
    '# verboflex.auth.refresh_sessions.x_logout_rate_limit_user_id__mutmut_18: survived' \
    '--- src/verboflex/auth/refresh_sessions.py' \
    '+++ src/verboflex/auth/refresh_sessions.py' \
    '-            .join(User, User.id == AuthSession.user_id)' \
    '+            .join(User, true())')
  expect_control_failure equivalent-mutant-diff \
    'equivalent mutant diff drifted outside the reviewed join transformation' \
    assert_equivalent_mutant_show \
    verboflex.auth.refresh_sessions.x_logout_rate_limit_user_id__mutmut_18 \
    "$invalid_show"
  printf 'exact equivalent mutation controls: PASS\n'
)

self_test_mutation_freshness() (
  local fixture fresh_stats stale_stats
  fixture=$(mktemp -d)
  fresh_stats="$fixture/fresh.json"
  stale_stats="$fixture/stale.json"
  trap 'rm -rf "$fixture"' EXIT INT TERM
  printf '%s\n' \
    '{"killed": 2, "survived": 0, "total": 2, "no_tests": 0, "skipped": 0, "suspicious": 0, "timeout": 0, "check_was_interrupted_by_user": 0, "segfault": 0}' \
    >"$fresh_stats"
  printf '%s\n' \
    '{"killed": 0, "survived": 0, "total": 0, "no_tests": 0, "skipped": 0, "suspicious": 0, "timeout": 0, "check_was_interrupted_by_user": 0, "segfault": 0}' \
    >"$stale_stats"
  assert_mutation_stats_fresh "$fresh_stats"
  expect_control_failure mutation-freshness 'fresh mutation run produced zero mutants' \
    assert_mutation_stats_fresh "$stale_stats"
  printf 'mutation freshness negative control: PASS\n'
)

self_test_property_mutation() {
  local frontend_scope
  [ -f "$BACKEND_PROPERTY_MUTATION_CONFIG" ] \
    || die "backend property mutation config is missing"
  for required_path in \
    src/verboflex/auth/access_tokens.py \
    src/verboflex/auth/identity.py \
    src/verboflex/auth/passwords.py; do
    grep -Fq "\"$required_path\"" "$BACKEND_PROPERTY_MUTATION_CONFIG" \
      || die "backend property mutation scope is incomplete"
  done
  frontend_scope=$(sed -n '39,91p' "$FRONTEND_ROOT/src/features/auth/session.tsx")
  printf '%s\n' "$frontend_scope" | grep -Fq 'export function transitionSession' \
    || die "frontend property mutation range omits transitionSession"
  printf '%s\n' "$frontend_scope" | grep -Fq 'export function initialSessionState' \
    || die "frontend property mutation range omits initialSessionState"
  printf 'property mutation attribution contract: PASS\n'
}

self_test_rate_limit_mutant() {
  "$BACKEND_ROOT/.venv/bin/python" "$BACKEND_RATE_LIMIT_MUTANT_PROOF" \
    --backend-root "$BACKEND_ROOT" --self-test
}

self_test_check_sequence() (
  local fixture log rc
  fixture=$(mktemp -d)
  log="$fixture/checks.log"
  trap 'rm -rf "$fixture"' EXIT INT TERM
  first_check() { printf 'first\n' >>"$log"; }
  failing_check() { printf 'failure\n' >>"$log"; return 42; }
  forbidden_check() { printf 'forbidden\n' >>"$log"; }
  set +e
  run_required_checks first_check failing_check forbidden_check
  rc=$?
  set -e
  [ "$rc" -eq 42 ] || die "required check failure status was not propagated"
  printf '%s\n' first failure | diff -u - "$log" >/dev/null \
    || die "required checks continued after a failure"
  printf 'required check sequence negative control: PASS\n'
)

self_test_frontend_coverage() (
  local fixture source normalized valid_report vacuous_report valid_map invalid_map patterns
  local partial_coverage partial_diff partial_report partial_rc
  local positive_diff positive_report positive_rc
  fixture=$(mktemp -d)
  source="$fixture/source.xml"
  normalized="$fixture/frontend-coverage.xml"
  valid_report="$fixture/valid-report"
  vacuous_report="$fixture/vacuous-report"
  valid_map="$fixture/frontend-coverage-exclusions"
  invalid_map="$fixture/frontend-coverage-exclusions-invalid"
  patterns="$fixture/frontend-coverage-patterns"
  partial_coverage="$fixture/partial-coverage.xml"
  partial_diff="$fixture/partial.diff"
  partial_report="$fixture/partial-report"
  positive_diff="$fixture/positive.diff"
  positive_report="$fixture/positive-report"
  trap 'rm -rf "$fixture"' EXIT INT TERM

  printf '%s\n' \
    '<?xml version="1.0"?>' \
    '<coverage><sources>' \
    "<source>$FRONTEND_ROOT</source>" \
    '</sources><packages><package><classes>' \
    '<class filename="src/features/auth/session.tsx"><lines><line number="1" hits="1"/></lines></class>' \
    '</classes></package></packages></coverage>' >"$source"
  normalize_frontend_cobertura "$source" "$normalized"
  grep -Fq 'filename="frontend/src/features/auth/session.tsx"' "$normalized" \
    || die "frontend Cobertura path normalization drifted"
  printf '%s\n' \
    'diff --git a/frontend/src/features/auth/session.tsx b/frontend/src/features/auth/session.tsx' \
    'new file mode 100644' \
    'index 0000000..1111111' \
    '--- /dev/null' \
    '+++ b/frontend/src/features/auth/session.tsx' \
    '@@ -0,0 +1 @@' \
    '+coveredLine()' >"$positive_diff"
  set +e
  (cd "$REPO_ROOT" && "$BACKEND_ROOT/.venv/bin/diff-cover" "$normalized" \
    --diff-file "$positive_diff" --branch-coverage --fail-under 100) \
    >"$positive_report" 2>&1
  positive_rc=$?
  set -e
  if [ "$positive_rc" -ne 0 ]; then
    sed -n '1,80p' "$positive_report" >&2
    die "normalized frontend Cobertura could not be consumed by production diff-cover"
  fi

  printf '%s\n' 'Diff Coverage' 'Total:   152 lines' 'Missing: 0 lines' 'Coverage: 100%' \
    >"$valid_report"
  assert_diff_coverage_nonempty "$valid_report"

  printf '%s\n' 'Diff Coverage' 'No lines with coverage information in this diff.' \
    >"$vacuous_report"
  expect_control_failure frontend-coverage-vacuity \
    'changed-line coverage matched no coverable frontend lines' \
    assert_diff_coverage_nonempty "$vacuous_report"

  printf '%s\n' \
    '<?xml version="1.0"?>' \
    '<coverage><sources><source>/unexpected/frontend</source></sources><packages><package><classes>' \
    '<class filename="/absolute/session.tsx"><lines><line number="1" hits="1"/></lines></class>' \
    '</classes></package></packages></coverage>' >"$source"
  expect_control_failure frontend-cobertura-path \
    'frontend Cobertura contains missing or non-canonical source paths' \
    normalize_frontend_cobertura "$source" "$normalized"

  write_expected_frontend_coverage_exclusion_map >"$valid_map"
  assert_frontend_coverage_exclusion_map "$valid_map"
  frontend_coverage_exclude_patterns "$valid_map" >"$patterns"
  grep -Fq '*/frontend/src/api/client/**' "$patterns" \
    || die "frontend coverage generated-code exclusion is not absolute-path safe"
  cp "$valid_map" "$invalid_map"
  printf '%s\n' \
    'frontend/src/components/layout/**|forbidden handwritten production exclusion' \
    >>"$invalid_map"
  expect_control_failure frontend-coverage-exclusion-map \
    'frontend coverage exclusion mapping drifted outside the approved SPEC scope' \
    assert_frontend_coverage_exclusion_map "$invalid_map"
  printf 'frontend coverage exclusion mapping negative control: PASS\n'

  printf '%s\n' \
    '<?xml version="1.0"?>' \
    '<coverage><sources><source>.</source></sources><packages><package><classes>' \
    '<class filename="frontend/src/partial.ts"><lines>' \
    '<line number="1" hits="1" branch="true" condition-coverage="50% (1/2)"/>' \
    '</lines></class></classes></package></packages></coverage>' >"$partial_coverage"
  printf '%s\n' \
    'diff --git a/frontend/src/partial.ts b/frontend/src/partial.ts' \
    'new file mode 100644' \
    'index 0000000..1111111' \
    '--- /dev/null' \
    '+++ b/frontend/src/partial.ts' \
    '@@ -0,0 +1 @@' \
    '+condition ? left() : right()' >"$partial_diff"
  set +e
  (cd "$REPO_ROOT" && "$BACKEND_ROOT/.venv/bin/diff-cover" "$partial_coverage" \
    --diff-file "$partial_diff" --branch-coverage --fail-under 100) \
    >"$partial_report" 2>&1
  partial_rc=$?
  set -e
  [ "$partial_rc" -ne 0 ] \
    || die "frontend Cobertura partial branch escaped the changed-line gate"
  grep -Fq 'Coverage is below 100%' "$partial_report" \
    || die "frontend Cobertura partial-branch control did not reach diff-cover"
  printf 'frontend Cobertura partial-branch negative control: PASS\n'
  printf 'frontend changed-line coverage negative controls: PASS\n'
)

self_test_secret_audit_policy() (
  local fixture findings
  fixture=$(mktemp -d)
  findings="$fixture/findings"
  trap 'rm -rf "$fixture"' EXIT INT TERM
  scan_repository_secrets
  write_audited_secret_policy >"$findings"
  assert_audited_secret_findings "$findings"
  printf '%s\n' 'src/new.py|1|Secret Keyword|unreviewed-fingerprint' >>"$findings"
  expect_control_failure secret-audit-policy \
    'detected secrets outside the audited false-positive map' \
    assert_audited_secret_findings "$findings"
  printf 'secret audit exact-policy negative control: PASS\n'
)

case "${1:-}" in
  --preflight) checker_preflight ;;
  --self-test-openapi-control) openapi_negative_control ;;
  --self-test-staging-layer) self_test_staging_layer ;;
  --self-test-candidate-contract) self_test_candidate_contract ;;
  --self-test-infra-lifecycle) self_test_infra_lifecycle ;;
  --self-test-infra-failure-cleanup) self_test_infra_failure_cleanup ;;
  --self-test-mutation-verdict) self_test_mutation_verdict ;;
  --self-test-equivalent-mutants) self_test_equivalent_mutants ;;
  --self-test-mutation-freshness) self_test_mutation_freshness ;;
  --self-test-property-mutation) self_test_property_mutation ;;
  --self-test-rate-limit-mutant) self_test_rate_limit_mutant ;;
  --self-test-check-sequence) self_test_check_sequence ;;
  --self-test-packaged-checker-isolation) self_test_packaged_checker_isolation ;;
  --self-test-frontend-coverage) self_test_frontend_coverage ;;
  --self-test-secret-audit-policy) self_test_secret_audit_policy ;;
  --post-fix-candidate) run_post_fix_candidate ;;
  -h|--help)
    printf 'usage: tools/gauntlet.sh [--preflight|--post-fix-candidate]\n'
    ;;
  '') run_full_gauntlet ;;
  *) die "unknown option: $1" ;;
esac

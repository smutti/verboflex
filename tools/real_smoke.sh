#!/usr/bin/env bash
set -euo pipefail

readonly SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
readonly REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
readonly BACKEND_ROOT="$REPO_ROOT/backend"
readonly FRONTEND_ROOT="$REPO_ROOT/frontend"

SMOKE_PROJECT=""
SMOKE_ENV_FILE=""
SMOKE_RUNTIME_DIR=""
SMOKE_IMAGE_TAG=""
SMOKE_BACKEND_URL=""
SMOKE_FRONTEND_URL=""
SMOKE_ALLOWED_ORIGIN=""
SMOKE_EMAIL="phase01-smoke@example.com"
SMOKE_TEMP_PASSWORD=""
SMOKE_NEW_PASSWORD=""

die() {
  printf 'real-smoke error: %s\n' "$1" >&2
  exit 1
}

assert_status() {
  local expected=$1
  local actual=$2
  local label=$3
  [ "$expected" = "$actual" ] || die "$label expected HTTP $expected, got $actual"
}

assert_json_exact() {
  local response_file=$1
  local expected_json=$2
  local label=$3
  local rc
  set +e
  (
    cd "$BACKEND_ROOT"
    uv run python -c \
      'import json,sys; actual=json.load(open(sys.argv[1])); expected=json.loads(sys.argv[2]); raise SystemExit(0 if actual == expected else 1)' \
      "$response_file" "$expected_json"
  )
  rc=$?
  set -e
  [ "$rc" -eq 0 ] || die "$label returned an unexpected JSON body"
}

expect_failure() {
  local expected_text=$1
  shift
  local output rc
  output=$(mktemp)
  set +e
  ("$@") >"$output" 2>&1
  rc=$?
  set -e
  [ "$rc" -ne 0 ] || die "negative control unexpectedly passed: $expected_text"
  grep -Fq "$expected_text" "$output" || die "negative control failed for the wrong reason"
  rm -f "$output"
}

json_field() {
  local response_file=$1
  local field=$2
  (
    cd "$BACKEND_ROOT"
    uv run python -c 'import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])' \
      "$response_file" "$field"
  )
}

write_login_form() {
  local destination=$1
  local email=$2
  local password=$3
  printf 'username=%s&password=%s' "$email" "$password" >"$destination"
  chmod 600 "$destination"
}

http_request() {
  local method=$1
  local url=$2
  local response_file=$3
  local headers_file=$4
  shift 4
  curl --silent --show-error --max-time 10 --request "$method" \
    --output "$response_file" --dump-header "$headers_file" --write-out '%{http_code}' \
    "$@" "$url"
}

random_port() {
  (
    cd "$BACKEND_ROOT"
    uv run python -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()'
  )
}

settings_check() {
  local secret=$1
  local secure=$2
  (
    cd "$BACKEND_ROOT"
    VERBOFLEX_APP_ENV=staging \
    VERBOFLEX_JWT_SECRET_KEY="$secret" \
    VERBOFLEX_REFRESH_COOKIE_SECURE="$secure" \
    VERBOFLEX_CORS_ORIGINS='["https://staging.verboflex.example"]' \
      uv run python -c 'from verboflex.core.config import Settings; Settings()' >/dev/null
  )
}

preflight() {
  local runtime env_file backend_port frontend_port secret rc
  command -v docker >/dev/null 2>&1 || die "Docker is unavailable"
  docker info >/dev/null 2>&1 || die "Docker daemon is unavailable"
  runtime=$(mktemp -d /tmp/verboflex-phase01-smoke-preflight.XXXXXX)
  env_file="$runtime/smoke.env"
  chmod 700 "$runtime"
  secret=$(openssl rand -hex 32)
  settings_check "$secret" true
  assert_status 200 200 preflight-status-positive
  expect_failure 'expected HTTP 200, got 500' assert_status 200 500 preflight-status-negative
  set +e
  settings_check 'replace-me-with-at-least-32-random-bytes' true >/dev/null 2>&1
  rc=$?
  set -e
  [ "$rc" -ne 0 ] || die "placeholder-secret negative control unexpectedly passed"
  set +e
  settings_check "$secret" false >/dev/null 2>&1
  rc=$?
  set -e
  [ "$rc" -ne 0 ] || die "insecure-cookie negative control unexpectedly passed"
  backend_port=$(random_port)
  frontend_port=$(random_port)
  while [ "$frontend_port" = "$backend_port" ]; do frontend_port=$(random_port); done
  : >"$env_file"
  chmod 600 "$env_file"
  printf '%s\n' \
    "VERBOFLEX_POSTGRES_PASSWORD=$(openssl rand -hex 24)" \
    "VERBOFLEX_JWT_SECRET_KEY=$secret" \
    "VERBOFLEX_CORS_ORIGINS=[\"http://localhost:$frontend_port\"]" \
    'VERBOFLEX_REFRESH_COOKIE_SECURE=true' \
    "VERBOFLEX_BACKEND_PORT=$backend_port" \
    "VERBOFLEX_FRONTEND_PORT=$frontend_port" \
    "VITE_API_BASE_URL=http://localhost:$backend_port" \
    'VERBOFLEX_IMAGE_TAG=phase01-smoke-preflight' >"$env_file"
  docker compose --project-name "verboflex_phase01_preflight_$$" --env-file "$env_file" \
    -f "$REPO_ROOT/docker-compose.yml" -f "$REPO_ROOT/docker-compose.staging.yml" \
    config >/dev/null
  rm -rf "$runtime"
  printf 'real smoke preflight: PASS\n'
}

compose() {
  docker compose --project-name "$SMOKE_PROJECT" --env-file "$SMOKE_ENV_FILE" \
    -f "$REPO_ROOT/docker-compose.yml" -f "$REPO_ROOT/docker-compose.staging.yml" "$@"
}

cleanup() {
  local rc image
  if [ -n "$SMOKE_PROJECT" ] && [ -n "$SMOKE_ENV_FILE" ] && [ -f "$SMOKE_ENV_FILE" ]; then
    set +e
    compose down --volumes --remove-orphans --timeout 10 >/dev/null 2>&1
    rc=$?
    set -e
    [ "$rc" -eq 0 ] || printf 'warning: isolated Compose cleanup exited %s\n' "$rc" >&2
  fi
  if [ -n "$SMOKE_IMAGE_TAG" ]; then
    for image in "verboflex-backend:$SMOKE_IMAGE_TAG" "verboflex-frontend:$SMOKE_IMAGE_TAG"; do
      set +e
      docker image rm "$image" >/dev/null 2>&1
      rc=$?
      set -e
      [ "$rc" -eq 0 ] || [ "$rc" -eq 1 ] || printf 'warning: image cleanup exited %s\n' "$rc" >&2
    done
  fi
  if [ -n "$SMOKE_RUNTIME_DIR" ] && [ -d "$SMOKE_RUNTIME_DIR" ]; then
    rm -rf "$SMOKE_RUNTIME_DIR"
  fi
}

initialize_runtime() {
  local backend_port frontend_port secret postgres_password suffix
  suffix="$$-$(date +%s)"
  SMOKE_PROJECT="verboflex_phase01_smoke_${suffix//-/_}"
  SMOKE_RUNTIME_DIR=$(mktemp -d /tmp/verboflex-phase01-smoke.XXXXXX)
  SMOKE_ENV_FILE="$SMOKE_RUNTIME_DIR/smoke.env"
  SMOKE_IMAGE_TAG="phase01-smoke-${suffix}"
  chmod 700 "$SMOKE_RUNTIME_DIR"
  : >"$SMOKE_ENV_FILE"
  chmod 600 "$SMOKE_ENV_FILE"
  backend_port=$(random_port)
  frontend_port=$(random_port)
  while [ "$frontend_port" = "$backend_port" ]; do frontend_port=$(random_port); done
  secret=$(openssl rand -hex 32)
  postgres_password=$(openssl rand -hex 24)
  SMOKE_TEMP_PASSWORD="TemporarySmoke$(openssl rand -hex 12)!"
  SMOKE_NEW_PASSWORD="OrdinarySmoke$(openssl rand -hex 12)!"
  SMOKE_BACKEND_URL="http://localhost:$backend_port"
  SMOKE_FRONTEND_URL="http://localhost:$frontend_port"
  SMOKE_ALLOWED_ORIGIN="$SMOKE_FRONTEND_URL"
  printf '%s\n' \
    "VERBOFLEX_POSTGRES_PASSWORD=$postgres_password" \
    "VERBOFLEX_JWT_SECRET_KEY=$secret" \
    "VERBOFLEX_CORS_ORIGINS=[\"$SMOKE_ALLOWED_ORIGIN\"]" \
    'VERBOFLEX_REFRESH_COOKIE_SECURE=true' \
    "VERBOFLEX_BACKEND_PORT=$backend_port" \
    "VERBOFLEX_FRONTEND_PORT=$frontend_port" \
    "VITE_API_BASE_URL=$SMOKE_BACKEND_URL" \
    "VERBOFLEX_IMAGE_TAG=$SMOKE_IMAGE_TAG" >"$SMOKE_ENV_FILE"
}

wait_for_url() {
  local url=$1
  local expected=$2
  local label=$3
  local deadline status rc
  deadline=$((SECONDS + 120))
  while [ "$SECONDS" -lt "$deadline" ]; do
    set +e
    status=$(curl --silent --show-error --max-time 3 --output /dev/null --write-out '%{http_code}' "$url")
    rc=$?
    set -e
    if [ "$rc" -eq 0 ] && [ "$status" = "$expected" ]; then return 0; fi
    sleep 1
  done
  compose ps >&2
  die "$label readiness timed out"
}

prepare_stack() {
  compose build backend worker frontend
  compose up -d postgres redis
  local deadline rc
  deadline=$((SECONDS + 120))
  while [ "$SECONDS" -lt "$deadline" ]; do
    set +e
    compose exec -T postgres pg_isready -U verboflex -d verboflex >/dev/null 2>&1
    rc=$?
    set -e
    [ "$rc" -eq 0 ] && break
    sleep 1
  done
  [ "$rc" -eq 0 ] || die "PostgreSQL readiness timed out"
  compose run --rm -T backend alembic upgrade head
  compose run --rm -T backend alembic downgrade base
  compose run --rm -T backend alembic upgrade head
  printf '%s\n' "$SMOKE_TEMP_PASSWORD" | compose run --rm -T backend \
    python -m verboflex.cli bootstrap-admin --email "$SMOKE_EMAIL" --display-name 'Phase Thirteen' \
    >"$SMOKE_RUNTIME_DIR/bootstrap.out"
  grep -Fxq 'First administrator created.' "$SMOKE_RUNTIME_DIR/bootstrap.out" \
    || die "admin bootstrap did not reach its non-secret success checkpoint"
  compose up -d backend worker frontend
  wait_for_url "$SMOKE_BACKEND_URL/api/v1/health" 200 backend
  wait_for_url "$SMOKE_FRONTEND_URL/login" 200 frontend
}

verify_worker_result() {
  local result deadline rc
  deadline=$((SECONDS + 120))
  while [ "$SECONDS" -lt "$deadline" ]; do
    set +e
    result=$(compose exec -T backend python -c \
      'from verboflex.worker.celery_app import app; r=app.send_task("verboflex.add",args=(2,3)); print(r.get(timeout=10)); r.forget()' \
      2>"$SMOKE_RUNTIME_DIR/worker-attempt.err")
    rc=$?
    set -e
    if [ "$rc" -eq 0 ] && [ "$result" = "5" ]; then return 0; fi
    sleep 2
  done
  sed -n '1,100p' "$SMOKE_RUNTIME_DIR/worker-attempt.err" >&2
  die "Celery result did not become exactly 5"
}

core_api_flow() {
  local form response headers status restricted_token ordinary_token refresh_cookie next_cookie access_token
  form="$SMOKE_RUNTIME_DIR/login.form"
  response="$SMOKE_RUNTIME_DIR/response.json"
  headers="$SMOKE_RUNTIME_DIR/headers.txt"
  status=$(http_request GET "$SMOKE_BACKEND_URL/api/v1/health" "$response" "$headers")
  assert_status 200 "$status" health
  assert_json_exact "$response" '{"status":"ok"}' health

  write_login_form "$form" "$SMOKE_EMAIL" "$SMOKE_TEMP_PASSWORD"
  status=$(http_request POST "$SMOKE_BACKEND_URL/api/v1/auth/token" "$response" "$headers" \
    -H 'Content-Type: application/x-www-form-urlencoded' --data-binary "@$form")
  assert_status 200 "$status" temporary-login
  restricted_token=$(json_field "$response" access_token)
  [ "$(json_field "$response" must_change_password)" = "True" ] || die "temporary login was not restricted"
  [ "$(json_field "$response" expires_in)" = "300" ] || die "temporary login lifetime drifted"
  if grep -Eiq '^set-cookie: __Host-verboflex_refresh=' "$headers"; then die "temporary login issued refresh authority"; fi
  if grep -Eiq '^set-cookie: (__Secure-verboflex_refresh|verboflex_refresh)=' "$headers"; then die "temporary login issued legacy refresh authority"; fi

  status=$(http_request GET "$SMOKE_BACKEND_URL/api/v1/users/me" "$response" "$headers" \
    -H "Authorization: Bearer $restricted_token")
  assert_status 403 "$status" temporary-me
  assert_json_exact "$response" '{"detail":"Password change required"}' temporary-me

  printf '{"current_password":"%s","new_password":"%s"}' \
    "$SMOKE_TEMP_PASSWORD" "$SMOKE_NEW_PASSWORD" >"$SMOKE_RUNTIME_DIR/change.json"
  chmod 600 "$SMOKE_RUNTIME_DIR/change.json"
  status=$(http_request POST "$SMOKE_BACKEND_URL/api/v1/auth/change-password" "$response" "$headers" \
    -H 'Content-Type: application/json' -H "Authorization: Bearer $restricted_token" \
    --data-binary "@$SMOKE_RUNTIME_DIR/change.json")
  assert_status 204 "$status" password-change
  grep -Eiq '^set-cookie: __Host-verboflex_refresh=.*Max-Age=0' "$headers" \
    || die "password change did not clear refresh authority"

  status=$(http_request POST "$SMOKE_BACKEND_URL/api/v1/auth/token" "$response" "$headers" \
    -H 'Content-Type: application/x-www-form-urlencoded' --data-binary "@$form")
  assert_status 401 "$status" old-password-login
  assert_json_exact "$response" '{"detail":"Invalid credentials"}' old-password-login

  write_login_form "$form" "$SMOKE_EMAIL" "$SMOKE_NEW_PASSWORD"
  status=$(http_request POST "$SMOKE_BACKEND_URL/api/v1/auth/token" "$response" "$headers" \
    -H 'Content-Type: application/x-www-form-urlencoded' --data-binary "@$form")
  assert_status 200 "$status" ordinary-login
  ordinary_token=$(json_field "$response" access_token)
  [ "$(json_field "$response" must_change_password)" = "False" ] || die "ordinary login remained restricted"
  [ "$(json_field "$response" expires_in)" = "900" ] || die "ordinary login lifetime drifted"
  grep -Eiq '^set-cookie: __Host-verboflex_refresh=.*HttpOnly' "$headers" || die "refresh cookie omitted HttpOnly"
  if grep -Eiq '^set-cookie: (__Secure-verboflex_refresh|verboflex_refresh)=' "$headers"; then die "ordinary login emitted legacy refresh cookie"; fi
  grep -Eiq '^set-cookie: __Host-verboflex_refresh=.*Secure' "$headers" || die "staging refresh cookie omitted Secure"
  grep -Eiq '^set-cookie: __Host-verboflex_refresh=.*SameSite=lax' "$headers" || die "refresh cookie SameSite drifted"
  grep -Eiq '^set-cookie: __Host-verboflex_refresh=.*Path=/([;[:space:]]|$)' "$headers" || die "refresh cookie Path drifted"
  if grep -Eiq '^set-cookie: __Host-verboflex_refresh=.*Domain=' "$headers"; then die "refresh cookie Domain must be absent"; fi
  refresh_cookie=$(sed -n 's/^set-cookie: __Host-verboflex_refresh=\([^;]*\).*/\1/ip' "$headers" | sed -n '1p')
  [ -n "$refresh_cookie" ] || die "ordinary login omitted refresh cookie"

  status=$(http_request GET "$SMOKE_BACKEND_URL/api/v1/users/me" "$response" "$headers" \
    -H "Authorization: Bearer $ordinary_token")
  assert_status 200 "$status" current-identity
  [ "$(json_field "$response" email)" = "$SMOKE_EMAIL" ] || die "identity email drifted"
  grep -Fq '"admin"' "$response" || die "identity omitted admin role"
  status=$(http_request GET "$SMOKE_BACKEND_URL/api/v1/system/status" "$response" "$headers" \
    -H "Authorization: Bearer $ordinary_token")
  assert_status 200 "$status" system-status
  (cd "$BACKEND_ROOT" && uv run python -c \
    'import json,sys; d=json.load(open(sys.argv[1])); assert set(d)=={"api","database","redis","worker","checked_at"}; assert d["api"]=="online"; assert all(d[k] in {"online","unavailable","pending"} for k in ("database","redis","worker"))' \
    "$response")

  status=$(http_request POST "$SMOKE_BACKEND_URL/api/v1/auth/refresh" "$response" "$headers" \
    -H "Origin: $SMOKE_ALLOWED_ORIGIN" -H "Cookie: __Host-verboflex_refresh=$refresh_cookie")
  assert_status 200 "$status" refresh
  access_token=$(json_field "$response" access_token)
  [ -n "$access_token" ] || die "refresh omitted access token"
  next_cookie=$(sed -n 's/^set-cookie: __Host-verboflex_refresh=\([^;]*\).*/\1/ip' "$headers" | sed -n '1p')
  [ -n "$next_cookie" ] && [ "$next_cookie" != "$refresh_cookie" ] || die "refresh did not rotate cookie"

  status=$(http_request POST "$SMOKE_BACKEND_URL/api/v1/auth/logout" "$response" "$headers" \
    -H "Origin: $SMOKE_ALLOWED_ORIGIN" -H "Cookie: __Host-verboflex_refresh=$next_cookie")
  assert_status 204 "$status" logout-first
  status=$(http_request POST "$SMOKE_BACKEND_URL/api/v1/auth/logout" "$response" "$headers" \
    -H "Origin: $SMOKE_ALLOWED_ORIGIN" -H "Cookie: __Host-verboflex_refresh=$next_cookie")
  assert_status 204 "$status" logout-second
  status=$(http_request GET "$SMOKE_BACKEND_URL/api/v1/users/me" "$response" "$headers" \
    -H "Authorization: Bearer $ordinary_token")
  assert_status 401 "$status" pre-rotation-revoked-access
  status=$(http_request GET "$SMOKE_BACKEND_URL/api/v1/users/me" "$response" "$headers" \
    -H "Authorization: Bearer $access_token")
  assert_status 401 "$status" successor-revoked-access
}

reset_admin_for_browser() {
  local browser_temp=$1
  printf '%s\n' "$browser_temp" | compose exec -T backend python -m verboflex.cli \
    reset-password --email "$SMOKE_EMAIL" >"$SMOKE_RUNTIME_DIR/reset.out"
  grep -Fxq 'Password reset completed; password change is required.' "$SMOKE_RUNTIME_DIR/reset.out" \
    || die "browser reset did not reach its non-secret checkpoint"
}

reset_auth_rate_limits() {
  compose exec -T backend python -c \
    'from redis import Redis; from verboflex.core.config import get_settings; r=Redis.from_url(str(get_settings().redis_url)); keys=list(r.scan_iter(match="verboflex:auth:*")); r.delete(*keys) if keys else None; r.close()'
}

browser_flow() {
  local browser_temp=$1
  local browser_password=$2
  reset_admin_for_browser "$browser_temp"
  (
    cd "$FRONTEND_ROOT"
    PLAYWRIGHT_BASE_URL="$SMOKE_FRONTEND_URL" \
    PLAYWRIGHT_OUTPUT_DIR="$SMOKE_RUNTIME_DIR/playwright" \
    E2E_EMAIL="$SMOKE_EMAIL" E2E_TEMP_PASSWORD="$browser_temp" E2E_PASSWORD="$browser_password" \
      npm run e2e -- --grep 'auth shell'
  )
}

adversarial_flow() {
  local adversarial_temp adversarial_password
  adversarial_temp="AdversarialTemp$(openssl rand -hex 12)!"
  adversarial_password="AdversarialOrdinary$(openssl rand -hex 12)!"
  reset_admin_for_browser "$adversarial_temp"
  VERBOFLEX_SMOKE_PROJECT="$SMOKE_PROJECT" \
  VERBOFLEX_SMOKE_ENV_FILE="$SMOKE_ENV_FILE" \
  VERBOFLEX_SMOKE_BACKEND_URL="$SMOKE_BACKEND_URL" \
  VERBOFLEX_SMOKE_ALLOWED_ORIGIN="$SMOKE_ALLOWED_ORIGIN" \
  VERBOFLEX_SMOKE_EMAIL="$SMOKE_EMAIL" \
  VERBOFLEX_SMOKE_TEMP_PASSWORD="$adversarial_temp" \
  VERBOFLEX_SMOKE_NEW_PASSWORD="$adversarial_password" \
    "$SCRIPT_DIR/adversarial_auth.sh" --against-running-stack
}

run_smoke() {
  local mode=$1 browser_temp browser_password
  initialize_runtime
  trap cleanup EXIT INT TERM
  prepare_stack
  verify_worker_result
  if [ "$mode" = "browser-only" ]; then
    browser_temp="BrowserTemp$(openssl rand -hex 12)!"
    browser_password="BrowserOrdinary$(openssl rand -hex 12)!"
    browser_flow "$browser_temp" "$browser_password"
  else
    core_api_flow
    reset_auth_rate_limits
    browser_flow "BrowserTemp$(openssl rand -hex 12)!" "BrowserOrdinary$(openssl rand -hex 12)!"
    reset_auth_rate_limits
    adversarial_flow
  fi
  cleanup
  trap - EXIT INT TERM
  printf 'real staging smoke: PASS\n'
}

case "${1:-}" in
  --preflight) preflight ;;
  --browser-only) run_smoke browser-only ;;
  -h|--help) printf 'usage: tools/real_smoke.sh [--preflight|--browser-only]\n' ;;
  '') run_smoke full ;;
  *) die "unknown option: $1" ;;
esac

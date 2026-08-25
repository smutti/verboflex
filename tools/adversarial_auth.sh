#!/usr/bin/env bash
set -euo pipefail

readonly SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
readonly REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
RUNTIME_DIR=""

die() {
  printf 'adversarial-auth error: %s\n' "$1" >&2
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
    cd "$REPO_ROOT/backend"
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
    cd "$REPO_ROOT/backend"
    uv run python -c 'import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])' \
      "$response_file" "$field"
  )
}

tamper_token_signature() {
  local token=$1
  printf '%s' "$token" | (
    cd "$REPO_ROOT/backend"
    uv run python -c '
import base64
import binascii
import sys

token = sys.stdin.read().strip()
parts = token.split(".")
if len(parts) != 3:
    raise SystemExit("token must contain exactly three segments")
try:
    signature = base64.urlsafe_b64decode(
        parts[2] + "=" * (-len(parts[2]) % 4)
    )
except (binascii.Error, ValueError) as error:
    raise SystemExit("token signature is not valid base64url") from error
if not signature:
    raise SystemExit("token signature is empty")
mutated_signature = bytes([signature[0] ^ 1]) + signature[1:]
parts[2] = base64.urlsafe_b64encode(mutated_signature).rstrip(b"=").decode("ascii")
print(".".join(parts))
'
  )
}

assert_signature_bytes_differ() {
  local original_token=$1
  local tampered_token=$2
  printf '%s\n%s\n' "$original_token" "$tampered_token" | (
    cd "$REPO_ROOT/backend"
    uv run python -c '
import base64
import binascii
import sys

tokens = sys.stdin.read().splitlines()
if len(tokens) != 2:
    raise SystemExit("signature comparison requires exactly two tokens")

def signature_bytes(token: str) -> bytes:
    parts = token.split(".")
    if len(parts) != 3:
        raise SystemExit("token must contain exactly three segments")
    try:
        return base64.urlsafe_b64decode(parts[2] + "=" * (-len(parts[2]) % 4))
    except (binascii.Error, ValueError) as error:
        raise SystemExit("token signature is not valid base64url") from error

if signature_bytes(tokens[0]) == signature_bytes(tokens[1]):
    raise SystemExit("signature bytes did not change")
'
  )
}

write_login_form() {
  local destination=$1
  local email=$2
  local password=$3
  printf 'username=%s&password=%s' "$email" "$password" >"$destination"
  chmod 600 "$destination"
}

cleanup_runtime() {
  if [ -n "$RUNTIME_DIR" ] && [ -d "$RUNTIME_DIR" ]; then
    rm -rf "$RUNTIME_DIR"
  fi
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

self_test() {
  local fixture token_fixture tampered_fixture
  fixture=$(mktemp)
  printf '{"detail":"Invalid credentials"}\n' >"$fixture"
  assert_status 401 401 status-positive-control
  assert_json_exact "$fixture" '{"detail":"Invalid credentials"}' json-positive-control
  expect_failure 'expected HTTP 401, got 200' assert_status 401 200 status-negative-control
  expect_failure 'unexpected JSON body' \
    assert_json_exact "$fixture" '{"detail":"different"}' json-negative-control
  token_fixture='header.payload._w'
  tampered_fixture=$(tamper_token_signature "$token_fixture")
  assert_signature_bytes_differ "$token_fixture" "$tampered_fixture"
  expect_failure 'signature bytes did not change' \
    assert_signature_bytes_differ "$token_fixture" "$token_fixture"
  rm -f "$fixture"
  printf 'tampered signature bytes differ: PASS\n'
  printf 'adversarial auth self-test: PASS\n'
}

require_runtime_environment() {
  local name
  for name in VERBOFLEX_SMOKE_PROJECT VERBOFLEX_SMOKE_ENV_FILE \
    VERBOFLEX_SMOKE_BACKEND_URL VERBOFLEX_SMOKE_ALLOWED_ORIGIN \
    VERBOFLEX_SMOKE_EMAIL VERBOFLEX_SMOKE_TEMP_PASSWORD VERBOFLEX_SMOKE_NEW_PASSWORD; do
    [ -n "${!name:-}" ] || die "required runtime value is missing: $name"
  done
  [ -f "$VERBOFLEX_SMOKE_ENV_FILE" ] || die "isolated Compose environment file is missing"
}

run_adversarial() {
  require_runtime_environment
  RUNTIME_DIR=$(mktemp -d /tmp/verboflex-phase01-adversarial.XXXXXX)
  chmod 700 "$RUNTIME_DIR"
  trap cleanup_runtime EXIT INT TERM
  local -a compose=(docker compose --project-name "$VERBOFLEX_SMOKE_PROJECT" \
    --env-file "$VERBOFLEX_SMOKE_ENV_FILE" \
    -f "$REPO_ROOT/docker-compose.yml" -f "$REPO_ROOT/docker-compose.staging.yml")
  local login_form response headers status restricted_token ordinary_token refresh_cookie
  local tampered_token inactive_email inactive_password wrong_body unknown_body inactive_body
  local expired_token replay_one replay_two replay_status_one replay_status_two reset_password
  login_form="$RUNTIME_DIR/login.form"
  response="$RUNTIME_DIR/response.json"
  headers="$RUNTIME_DIR/headers.txt"

  write_login_form "$login_form" "$VERBOFLEX_SMOKE_EMAIL" "$VERBOFLEX_SMOKE_TEMP_PASSWORD"
  status=$(http_request POST "$VERBOFLEX_SMOKE_BACKEND_URL/api/v1/auth/token" \
    "$response" "$headers" -H 'Content-Type: application/x-www-form-urlencoded' \
    --data-binary "@$login_form")
  assert_status 200 "$status" temporary-login
  restricted_token=$(json_field "$response" access_token)

  status=$(http_request GET "$VERBOFLEX_SMOKE_BACKEND_URL/api/v1/users/me" \
    "$response" "$headers" -H "Authorization: Bearer $restricted_token")
  assert_status 403 "$status" wrong-purpose-token
  assert_json_exact "$response" '{"detail":"Password change required"}' wrong-purpose-token

  printf '{"current_password":"%s","new_password":"%s"}' \
    "$VERBOFLEX_SMOKE_TEMP_PASSWORD" "$VERBOFLEX_SMOKE_NEW_PASSWORD" >"$RUNTIME_DIR/change.json"
  chmod 600 "$RUNTIME_DIR/change.json"
  status=$(http_request POST "$VERBOFLEX_SMOKE_BACKEND_URL/api/v1/auth/change-password" \
    "$response" "$headers" -H 'Content-Type: application/json' \
    -H "Authorization: Bearer $restricted_token" --data-binary "@$RUNTIME_DIR/change.json")
  assert_status 204 "$status" adversarial-password-change

  write_login_form "$login_form" "$VERBOFLEX_SMOKE_EMAIL" "$VERBOFLEX_SMOKE_NEW_PASSWORD"
  status=$(http_request POST "$VERBOFLEX_SMOKE_BACKEND_URL/api/v1/auth/token" \
    "$response" "$headers" -H 'Content-Type: application/x-www-form-urlencoded' \
    --data-binary "@$login_form")
  assert_status 200 "$status" ordinary-login
  ordinary_token=$(json_field "$response" access_token)
  refresh_cookie=$(sed -n 's/^set-cookie: __Host-verboflex_refresh=\([^;]*\).*/\1/ip' "$headers" | sed -n '1p')
  [ -n "$refresh_cookie" ] || die "ordinary login did not set a refresh cookie"

  tampered_token=$(tamper_token_signature "$ordinary_token")
  assert_signature_bytes_differ "$ordinary_token" "$tampered_token"
  status=$(http_request GET "$VERBOFLEX_SMOKE_BACKEND_URL/api/v1/users/me" \
    "$response" "$headers" -H "Authorization: Bearer $tampered_token")
  assert_status 401 "$status" tampered-token

  expired_token=$("${compose[@]}" exec -T backend python -c \
    'from datetime import UTC,datetime,timedelta; from sqlalchemy import select; from verboflex.auth.access_tokens import issue_access_token; from verboflex.core.config import get_settings; from verboflex.db.session import SessionFactory; from verboflex.models.auth_session import AuthSession; from verboflex.models.user import User; s=SessionFactory(); u=s.scalar(select(User).where(User.email=="phase01-smoke@example.com")); a=s.scalar(select(AuthSession).where(AuthSession.user_id==u.id).order_by(AuthSession.created_at.desc())); print(issue_access_token(user_id=u.id,session_id=a.id,token_version=u.token_version,purpose="access",settings=get_settings(),now=datetime.now(UTC)-timedelta(hours=1))); s.close()')
  status=$(http_request GET "$VERBOFLEX_SMOKE_BACKEND_URL/api/v1/users/me" \
    "$response" "$headers" -H "Authorization: Bearer $expired_token")
  assert_status 401 "$status" expired-token

  status=$(http_request POST "$VERBOFLEX_SMOKE_BACKEND_URL/api/v1/auth/refresh" \
    "$response" "$headers" -H 'Origin: https://attacker.example' \
    -H "Cookie: __Host-verboflex_refresh=$refresh_cookie")
  assert_status 403 "$status" hostile-origin
  assert_json_exact "$response" '{"detail":"Origin not allowed"}' hostile-origin

  inactive_email="inactive-smoke@example.com"
  inactive_password="InactiveSmokePassword-${VERBOFLEX_SMOKE_PROJECT##*_}!"
  printf '%s\n%s\n' "$inactive_email" "$inactive_password" | \
    "${compose[@]}" exec -T backend python -c \
      'import sys; from verboflex.auth.passwords import hash_password; from verboflex.db.session import SessionFactory; from verboflex.models.user import User; email=sys.stdin.readline().strip(); password=sys.stdin.readline().strip(); s=SessionFactory(); s.add(User(email=email,display_name="Inactive Smoke",hashed_password=hash_password(password),is_active=False,must_change_password=False)); s.commit(); s.close()' \
      >/dev/null

  write_login_form "$login_form" "$VERBOFLEX_SMOKE_EMAIL" 'definitely-wrong-password'
  status=$(http_request POST "$VERBOFLEX_SMOKE_BACKEND_URL/api/v1/auth/token" \
    "$RUNTIME_DIR/wrong.json" "$headers" -H 'Content-Type: application/x-www-form-urlencoded' \
    --data-binary "@$login_form")
  assert_status 401 "$status" wrong-password-enumeration
  wrong_body=$(shasum -a 256 "$RUNTIME_DIR/wrong.json" | awk '{print $1}')

  write_login_form "$login_form" 'unknown-smoke@example.com' 'definitely-wrong-password'
  status=$(http_request POST "$VERBOFLEX_SMOKE_BACKEND_URL/api/v1/auth/token" \
    "$RUNTIME_DIR/unknown.json" "$headers" -H 'Content-Type: application/x-www-form-urlencoded' \
    --data-binary "@$login_form")
  assert_status 401 "$status" unknown-account-enumeration
  unknown_body=$(shasum -a 256 "$RUNTIME_DIR/unknown.json" | awk '{print $1}')

  write_login_form "$login_form" "$inactive_email" "$inactive_password"
  status=$(http_request POST "$VERBOFLEX_SMOKE_BACKEND_URL/api/v1/auth/token" \
    "$RUNTIME_DIR/inactive.json" "$headers" -H 'Content-Type: application/x-www-form-urlencoded' \
    --data-binary "@$login_form")
  assert_status 401 "$status" inactive-account-enumeration
  inactive_body=$(shasum -a 256 "$RUNTIME_DIR/inactive.json" | awk '{print $1}')
  [ "$wrong_body" = "$unknown_body" ] && [ "$wrong_body" = "$inactive_body" ] \
    || die "credential failures are enumerable by response body"

  write_login_form "$login_form" 'bruteforce-smoke@example.com' 'definitely-wrong-password'
  local attempt
  for attempt in 1 2 3 4 5; do
    status=$(http_request POST "$VERBOFLEX_SMOKE_BACKEND_URL/api/v1/auth/token" \
      "$response" "$headers" -H 'Content-Type: application/x-www-form-urlencoded' \
      --data-binary "@$login_form")
    assert_status 401 "$status" "brute-force-attempt-$attempt"
  done
  status=$(http_request POST "$VERBOFLEX_SMOKE_BACKEND_URL/api/v1/auth/token" \
    "$response" "$headers" -H 'Content-Type: application/x-www-form-urlencoded' \
    --data-binary "@$login_form")
  assert_status 429 "$status" brute-force-boundary
  grep -Eiq '^retry-after: [1-9][0-9]*' "$headers" || die "429 omitted positive Retry-After"
  grep -Eiq '^x-ratelimit-remaining: 0' "$headers" || die "429 omitted remaining zero"

  replay_one="$RUNTIME_DIR/replay-one.status"
  replay_two="$RUNTIME_DIR/replay-two.status"
  curl --silent --show-error --max-time 10 --request POST --output "$RUNTIME_DIR/replay-one.json" \
    --write-out '%{http_code}' -H "Origin: $VERBOFLEX_SMOKE_ALLOWED_ORIGIN" \
    -H "Cookie: __Host-verboflex_refresh=$refresh_cookie" \
    "$VERBOFLEX_SMOKE_BACKEND_URL/api/v1/auth/refresh" >"$replay_one" &
  local replay_pid_one=$!
  curl --silent --show-error --max-time 10 --request POST --output "$RUNTIME_DIR/replay-two.json" \
    --write-out '%{http_code}' -H "Origin: $VERBOFLEX_SMOKE_ALLOWED_ORIGIN" \
    -H "Cookie: __Host-verboflex_refresh=$refresh_cookie" \
    "$VERBOFLEX_SMOKE_BACKEND_URL/api/v1/auth/refresh" >"$replay_two" &
  local replay_pid_two=$!
  wait "$replay_pid_one"
  wait "$replay_pid_two"
  replay_status_one=$(sed -n '1p' "$replay_one")
  replay_status_two=$(sed -n '1p' "$replay_two")
  printf '%s\n%s\n' "$replay_status_one" "$replay_status_two" | sort | \
    diff -u - <(printf '200\n401\n') >/dev/null || die "refresh concurrency was not exactly one success and one replay denial"

  reset_password="ResetSmoke-${VERBOFLEX_SMOKE_PROJECT##*_}!"
  printf '%s\n' "$reset_password" | "${compose[@]}" exec -T backend \
    python -m verboflex.cli reset-password --email "$VERBOFLEX_SMOKE_EMAIL" >/dev/null
  status=$(http_request GET "$VERBOFLEX_SMOKE_BACKEND_URL/api/v1/users/me" \
    "$response" "$headers" -H "Authorization: Bearer $ordinary_token")
  assert_status 401 "$status" stale-token-version

  write_login_form "$login_form" "$VERBOFLEX_SMOKE_EMAIL" "$reset_password"
  status=$(http_request POST "$VERBOFLEX_SMOKE_BACKEND_URL/api/v1/auth/token" \
    "$response" "$headers" -H 'Content-Type: application/x-www-form-urlencoded' \
    --data-binary "@$login_form")
  assert_status 200 "$status" reset-restricted-login
  restricted_token=$(json_field "$response" access_token)

  "${compose[@]}" stop redis >/dev/null
  status=$(http_request POST "$VERBOFLEX_SMOKE_BACKEND_URL/api/v1/auth/token" \
    "$response" "$headers" -H 'Content-Type: application/x-www-form-urlencoded' \
    --data-binary "@$login_form")
  assert_status 503 "$status" redis-outage-login
  status=$(http_request POST "$VERBOFLEX_SMOKE_BACKEND_URL/api/v1/auth/change-password" \
    "$response" "$headers" -H 'Content-Type: application/json' \
    -H "Authorization: Bearer $restricted_token" --data-binary "@$RUNTIME_DIR/change.json")
  assert_status 503 "$status" redis-outage-password-change
  status=$(http_request POST "$VERBOFLEX_SMOKE_BACKEND_URL/api/v1/auth/refresh" \
    "$response" "$headers" -H "Origin: $VERBOFLEX_SMOKE_ALLOWED_ORIGIN" \
    -H "Cookie: __Host-verboflex_refresh=$refresh_cookie")
  assert_status 503 "$status" redis-outage-refresh
  status=$(http_request POST "$VERBOFLEX_SMOKE_BACKEND_URL/api/v1/auth/logout" \
    "$response" "$headers" -H "Origin: $VERBOFLEX_SMOKE_ALLOWED_ORIGIN" \
    -H "Cookie: __Host-verboflex_refresh=$refresh_cookie")
  assert_status 204 "$status" redis-outage-logout
  status=$(http_request GET "$VERBOFLEX_SMOKE_BACKEND_URL/api/v1/health" "$response" "$headers")
  assert_status 200 "$status" redis-outage-health
  assert_json_exact "$response" '{"status":"ok"}' redis-outage-health

  cleanup_runtime
  trap - EXIT INT TERM
  printf 'adversarial auth: PASS\n'
}

case "${1:-}" in
  --self-test) self_test ;;
  --against-running-stack) run_adversarial ;;
  -h|--help)
    printf 'usage: tools/adversarial_auth.sh --self-test | --against-running-stack\n'
    ;;
  '') die 'direct execution requires a stack owned by tools/real_smoke.sh' ;;
  *) die "unknown option: $1" ;;
esac

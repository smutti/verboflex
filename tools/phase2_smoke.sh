#!/usr/bin/env bash
set -euo pipefail

readonly SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
readonly REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
readonly BACKEND_ROOT="$REPO_ROOT/backend"

SMOKE_MODE=""
SMOKE_DEPLOYMENT_OVERLAY=""
SMOKE_PROJECT=""
SMOKE_RUNTIME_DIR=""
SMOKE_ENV_FILE=""
SMOKE_OVERRIDE_FILE=""
SMOKE_PROBE_ENV_FILE=""
SMOKE_IMAGE_TAG=""
SMOKE_BACKEND_URL=""
SMOKE_FRONTEND_URL=""
SMOKE_EMAIL="phase02-smoke@example.com"
SMOKE_TEMP_PASSWORD=""
SMOKE_NEW_PASSWORD=""
SMOKE_CLIENT_SECRET=""
SMOKE_POSTGRES_PASSWORD=""
SMOKE_JWT_SECRET_KEY=""
SMOKE_ACCESS_TOKEN=""
SMOKE_KEYRING=""
SMOKE_WORKER_LOSS_STATE=""
SMOKE_BLOCK_FILE=""
SMOKE_BLOCK_STARTED_FILE=""

die() {
  printf 'phase2-smoke error: %s\n' "$1" >&2
  exit 1
}

random_port() {
  (
    cd "$BACKEND_ROOT"
    uv run python -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()'
  )
}

compose_base() {
  docker compose --project-name "$SMOKE_PROJECT" --env-file "$SMOKE_ENV_FILE" \
    -f "$REPO_ROOT/docker-compose.yml" "$@"
}

compose_deployment_overlay() {
  case "${1:-}" in
    staging) printf '%s\n' "$REPO_ROOT/docker-compose.staging.yml" ;;
    production) printf '%s\n' "$REPO_ROOT/docker-compose.prod.yml" ;;
    *) die "unsupported deployment overlay" ;;
  esac
}

compose_mock() {
  local deployment_overlay
  if [ -n "$SMOKE_DEPLOYMENT_OVERLAY" ]; then
    deployment_overlay=$(compose_deployment_overlay "$SMOKE_DEPLOYMENT_OVERLAY")
    docker compose --project-name "$SMOKE_PROJECT" --env-file "$SMOKE_ENV_FILE" \
      -f "$REPO_ROOT/docker-compose.yml" -f "$deployment_overlay" \
      -f "$SMOKE_OVERRIDE_FILE" "$@"
  else
    docker compose --project-name "$SMOKE_PROJECT" --env-file "$SMOKE_ENV_FILE" \
      -f "$REPO_ROOT/docker-compose.yml" -f "$SMOKE_OVERRIDE_FILE" "$@"
  fi
}

compose_active() {
  if [ "$SMOKE_MODE" = "mock-live-provider" ]; then
    compose_mock "$@"
  else
    compose_base "$@"
  fi
}

compose() {
  compose_active "$@"
}

cleanup() {
  local incoming_rc=$? cleanup_rc=0 runtime_dir="$SMOKE_RUNTIME_DIR"
  trap - EXIT INT TERM
  if [ -n "$SMOKE_PROJECT" ] && [ -n "$SMOKE_ENV_FILE" ] && [ -f "$SMOKE_ENV_FILE" ]; then
    set +e
    compose down --volumes --remove-orphans --timeout 10 >/dev/null 2>&1
    [ $? -eq 0 ] || cleanup_rc=1
    if [ -n "$(docker ps -aq --filter "label=com.docker.compose.project=$SMOKE_PROJECT")" ]; then
      cleanup_rc=1
    fi
    if [ -n "$(docker volume ls -q --filter "label=com.docker.compose.project=$SMOKE_PROJECT")" ]; then
      cleanup_rc=1
    fi
    if [ -n "$(docker network ls -q --filter "label=com.docker.compose.project=$SMOKE_PROJECT")" ]; then
      cleanup_rc=1
    fi
    set -e
  fi
  if [ -n "$SMOKE_IMAGE_TAG" ]; then
    docker image rm "verboflex-backend:$SMOKE_IMAGE_TAG" >/dev/null 2>&1 || true
    docker image rm "verboflex-frontend:$SMOKE_IMAGE_TAG" >/dev/null 2>&1 || true
  fi
  if [ -n "$runtime_dir" ] && [ -d "$runtime_dir" ]; then
    rm -rf "$runtime_dir"
  fi
  if [ -n "$runtime_dir" ] && [ -e "$runtime_dir" ]; then
    cleanup_rc=1
  fi
  if [ "$cleanup_rc" -ne 0 ]; then
    printf 'phase2-smoke error: disposable resources or temporary files remain\n' >&2
    incoming_rc=1
  fi
  exit "$incoming_rc"
}

wait_for_url() {
  local url=$1 expected=$2 label=$3 deadline status rc
  deadline=$((SECONDS + 180))
  while [ "$SECONDS" -lt "$deadline" ]; do
    set +e
    status=$(curl --silent --show-error --max-time 3 --output /dev/null --write-out '%{http_code}' "$url")
    rc=$?
    set -e
    if [ "$rc" -eq 0 ] && [ "$status" = "$expected" ]; then return 0; fi
    sleep 1
  done
  compose_active ps >&2 || true
  die "$label readiness timed out"
}

wait_for_worker() {
  local deadline
  deadline=$((SECONDS + 180))
  while [ "$SECONDS" -lt "$deadline" ]; do
    if [ "$(compose_active ps --status running -q worker | wc -l | tr -d ' ')" = "1" ] \
      && compose_active exec -T worker celery -A verboflex.worker.celery_app inspect ping \
        --timeout 5 >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  die "Celery worker readiness timed out"
}

wait_for_scheduler() {
  local deadline
  deadline=$((SECONDS + 180))
  while [ "$SECONDS" -lt "$deadline" ]; do
    if [ "$(compose_active ps --status running -q scheduler | wc -l | tr -d ' ')" = "1" ] \
      && compose_active exec -T scheduler python -c \
        'from verboflex.worker.celery_app import app; assert "preview-stale-job-watchdog" in app.conf.beat_schedule' \
        >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  die "Celery scheduler readiness timed out"
}

wait_for_file() {
  local path=$1 label=$2 deadline
  deadline=$((SECONDS + 30))
  while [ "$SECONDS" -lt "$deadline" ]; do
    if [ -f "$path" ]; then return 0; fi
    sleep 1
  done
  die "$label timed out"
}

wait_for_mock_provider() {
  local deadline
  deadline=$((SECONDS + 180))
  while [ "$SECONDS" -lt "$deadline" ]; do
    if compose_active exec -T backend python -c \
      'from urllib.request import urlopen; raise SystemExit(0 if urlopen("https://bitbucket.org/_health", timeout=2).status == 200 else 1)' \
      >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  die "mock provider readiness timed out"
}

make_tls_material() {
  local config="$SMOKE_RUNTIME_DIR/openssl.cnf"
  printf '%s\n' \
    '[req]' \
    'distinguished_name = dn' \
    'x509_extensions = v3_ca' \
    'prompt = no' \
    '[dn]' \
    'CN = VerboFlex Phase 2 Smoke CA' \
    '[v3_ca]' \
    'basicConstraints = critical,CA:TRUE' \
    'keyUsage = critical,keyCertSign,cRLSign' \
    'subjectKeyIdentifier = hash' \
    'authorityKeyIdentifier = keyid:always' >"$config"
  openssl req -x509 -newkey rsa:2048 -nodes -days 1 \
    -keyout "$SMOKE_RUNTIME_DIR/ca.key" -out "$SMOKE_RUNTIME_DIR/ca.pem" \
    -config "$config" >/dev/null 2>&1
  printf '%s\n' \
    '[req]' \
    'distinguished_name = dn' \
    'req_extensions = server_req' \
    'prompt = no' \
    '[dn]' \
    'CN = api.bitbucket.org' \
    '[server_req]' \
    'subjectAltName = @alt_names' \
    '[server_ext]' \
    'basicConstraints = critical,CA:FALSE' \
    'keyUsage = critical,digitalSignature,keyEncipherment' \
    'extendedKeyUsage = serverAuth' \
    'authorityKeyIdentifier = keyid,issuer' \
    'subjectAltName = @alt_names' \
    '[alt_names]' \
    'DNS.1 = api.bitbucket.org' \
    'DNS.2 = bitbucket.org' >"$config"
  openssl req -new -newkey rsa:2048 -nodes \
    -keyout "$SMOKE_RUNTIME_DIR/server.key" -out "$SMOKE_RUNTIME_DIR/server.csr" \
    -config "$config" >/dev/null 2>&1
  openssl x509 -req -days 1 -sha256 \
    -in "$SMOKE_RUNTIME_DIR/server.csr" \
    -CA "$SMOKE_RUNTIME_DIR/ca.pem" -CAkey "$SMOKE_RUNTIME_DIR/ca.key" \
    -CAcreateserial -CAserial "$SMOKE_RUNTIME_DIR/ca.srl" \
    -out "$SMOKE_RUNTIME_DIR/server.pem" \
    -extensions server_ext -extfile "$config" >/dev/null 2>&1
  chmod 600 "$SMOKE_RUNTIME_DIR"/*.key "$SMOKE_RUNTIME_DIR"/*.pem
}

initialize_runtime() {
  local backend_port frontend_port suffix deployment_name
  suffix="$$-$(date +%s)"
  deployment_name=${SMOKE_DEPLOYMENT_OVERLAY:-base}
  SMOKE_PROJECT="verboflex_phase02_37_${deployment_name}_${suffix//-/_}"
  SMOKE_RUNTIME_DIR=$(mktemp -d "/tmp/verboflex-phase02-37.${deployment_name}.XXXXXX")
  SMOKE_ENV_FILE="$SMOKE_RUNTIME_DIR/owner-only.env"
  SMOKE_OVERRIDE_FILE="$SMOKE_RUNTIME_DIR/mock-provider.yml"
  SMOKE_PROBE_ENV_FILE="$SMOKE_RUNTIME_DIR/local-api-probe.env"
  SMOKE_IMAGE_TAG="phase02-37-$deployment_name-$suffix"
  chmod 700 "$SMOKE_RUNTIME_DIR"
  backend_port=$(random_port)
  frontend_port=$(random_port)
  SMOKE_BACKEND_URL="http://localhost:$backend_port"
  SMOKE_FRONTEND_URL="http://localhost:$frontend_port"
  SMOKE_TEMP_PASSWORD="PhaseTwoTemporary-$(openssl rand -hex 10)!"
  SMOKE_NEW_PASSWORD="PhaseTwoOrdinary-$(openssl rand -hex 10)!"
  SMOKE_CLIENT_SECRET="mock-client-secret-$(openssl rand -hex 24)"
  SMOKE_POSTGRES_PASSWORD="mock-postgres-password-$(openssl rand -hex 24)"
  SMOKE_JWT_SECRET_KEY="mock-jwt-secret-$(openssl rand -hex 32)"
  SMOKE_ACCESS_TOKEN="mock-provider-bearer-$(openssl rand -hex 24)"
  SMOKE_WORKER_LOSS_STATE="$SMOKE_RUNTIME_DIR/worker-loss-state.json"
  SMOKE_BLOCK_FILE="$SMOKE_RUNTIME_DIR/preview-worker-block"
  SMOKE_BLOCK_STARTED_FILE="$SMOKE_RUNTIME_DIR/preview-worker-blocked"
  SMOKE_KEYRING=$(
    cd "$BACKEND_ROOT"
    uv run python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
  )
  printf '%s\n' \
    "VERBOFLEX_BACKEND_PORT=$backend_port" \
    "VERBOFLEX_FRONTEND_PORT=$frontend_port" \
    "VERBOFLEX_IMAGE_TAG=$SMOKE_IMAGE_TAG" \
    "VITE_API_BASE_URL=$SMOKE_BACKEND_URL" \
    'VERBOFLEX_BITBUCKET_OAUTH_CLIENT_ID=phase2-mock-consumer' \
    "VERBOFLEX_BITBUCKET_OAUTH_CLIENT_SECRET=$SMOKE_CLIENT_SECRET" \
    "VERBOFLEX_BITBUCKET_TOKEN_ENCRYPTION_KEYRING=$SMOKE_KEYRING" \
    "VERBOFLEX_POSTGRES_PASSWORD=$SMOKE_POSTGRES_PASSWORD" \
    "VERBOFLEX_JWT_SECRET_KEY=$SMOKE_JWT_SECRET_KEY" \
    "PHASE2_RUNTIME_DIR=$SMOKE_RUNTIME_DIR" \
    "PHASE2_REPO_ROOT=$REPO_ROOT" \
    "PHASE2_FRONTEND_ORIGIN=$SMOKE_FRONTEND_URL" \
    "MOCK_ACCESS_TOKEN=$SMOKE_ACCESS_TOKEN" \
    'VERBOFLEX_PREVIEW_SOFT_TIME_LIMIT_SECONDS=5' \
    'VERBOFLEX_PREVIEW_HARD_TIME_LIMIT_SECONDS=8' \
    'VERBOFLEX_PREVIEW_WATCHDOG_GRACE_SECONDS=3' \
    'VERBOFLEX_PREVIEW_WATCHDOG_INTERVAL_SECONDS=1' >"$SMOKE_ENV_FILE"
  chmod 600 "$SMOKE_ENV_FILE"
  : >"$SMOKE_RUNTIME_DIR/stdout.log"
  : >"$SMOKE_RUNTIME_DIR/stderr.log"
  : >"$SMOKE_RUNTIME_DIR/provider-audit.jsonl"
  chmod 600 "$SMOKE_RUNTIME_DIR/stdout.log" "$SMOKE_RUNTIME_DIR/stderr.log" \
    "$SMOKE_RUNTIME_DIR/provider-audit.jsonl"
}

configure_mock_provider() {
  make_tls_material
  printf '%s\n' \
    'services:' \
    '  mock-bitbucket:' \
    '    image: python:3.14-slim' \
    '    environment:' \
    '      MOCK_AUDIT_FILE: /run/phase2/provider-audit.jsonl' \
    '      MOCK_ACCESS_TOKEN: ${MOCK_ACCESS_TOKEN}' \
    '      MOCK_CLIENT_ID: ${VERBOFLEX_BITBUCKET_OAUTH_CLIENT_ID}' \
    '      MOCK_CLIENT_SECRET: ${VERBOFLEX_BITBUCKET_OAUTH_CLIENT_SECRET}' \
    '      MOCK_TLS_CERT: /run/phase2/server.pem' \
    '      MOCK_TLS_KEY: /run/phase2/server.key' \
    '      MOCK_BLOCK_FILE: /run/phase2/preview-worker-block' \
    '      MOCK_BLOCK_STARTED_FILE: /run/phase2/preview-worker-blocked' \
    '      MOCK_BLOCK_TIMEOUT_SECONDS: "120"' \
    '    command: ["python", "/mock/phase2_mock_provider.py"]' \
    '    volumes:' \
    '      - ${PHASE2_REPO_ROOT}/tools/phase2_mock_provider.py:/mock/phase2_mock_provider.py:ro' \
    '      - ${PHASE2_RUNTIME_DIR}:/run/phase2' \
    '    networks:' \
    '      default:' \
    '        aliases: [bitbucket.org, api.bitbucket.org]' \
    '  backend:' \
    '    environment:' \
    '      VERBOFLEX_CORS_ORIGINS: '\''["${PHASE2_FRONTEND_ORIGIN}"]'\''' \
    '      SSL_CERT_FILE: /run/phase2/ca.pem' \
    '    volumes:' \
    '      - ${PHASE2_RUNTIME_DIR}/ca.pem:/run/phase2/ca.pem:ro' \
    '      - ${PHASE2_RUNTIME_DIR}/ca.pem:/opt/venv/lib/python3.14/site-packages/certifi/cacert.pem:ro' \
    '    depends_on:' \
    '      mock-bitbucket:' \
    '        condition: service_started' \
    '  worker:' \
    '    environment:' \
    '      SSL_CERT_FILE: /run/phase2/ca.pem' \
    '    volumes:' \
    '      - ${PHASE2_RUNTIME_DIR}/ca.pem:/run/phase2/ca.pem:ro' \
    '      - ${PHASE2_RUNTIME_DIR}/ca.pem:/opt/venv/lib/python3.14/site-packages/certifi/cacert.pem:ro' \
    '    depends_on:' \
    '      mock-bitbucket:' \
    '        condition: service_started' \
    '  scheduler:' \
    '    environment:' \
    '      SSL_CERT_FILE: /run/phase2/ca.pem' \
    '    volumes:' \
    '      - ${PHASE2_RUNTIME_DIR}/ca.pem:/run/phase2/ca.pem:ro' \
    '      - ${PHASE2_RUNTIME_DIR}/ca.pem:/opt/venv/lib/python3.14/site-packages/certifi/cacert.pem:ro' \
    '    depends_on:' \
    '      mock-bitbucket:' \
    '        condition: service_started' >"$SMOKE_OVERRIDE_FILE"
  chmod 600 "$SMOKE_OVERRIDE_FILE"
  printf '%s\n' \
    'VERBOFLEX_LIVE_PROVIDER_OPT_IN=production-api-read-only-confirmed' \
    "VERBOFLEX_BASE_URL=$SMOKE_BACKEND_URL" \
    "VERBOFLEX_ADMIN_EMAIL=$SMOKE_EMAIL" \
    "VERBOFLEX_ADMIN_PASSWORD=$SMOKE_TEMP_PASSWORD" \
    "VERBOFLEX_ADMIN_NEW_PASSWORD=$SMOKE_NEW_PASSWORD" \
    'BITBUCKET_WORKSPACE=verboflex-smoke' \
    'BITBUCKET_REPOSITORY_SLUG=translations' \
    'BITBUCKET_BRANCH=main' >"$SMOKE_PROBE_ENV_FILE"
  chmod 600 "$SMOKE_PROBE_ENV_FILE"
}

preflight() {
  command -v docker >/dev/null 2>&1 || die "Docker is unavailable"
  command -v openssl >/dev/null 2>&1 || die "OpenSSL is unavailable"
  command -v curl >/dev/null 2>&1 || die "curl is unavailable"
  docker info >/dev/null 2>&1 || die "Docker daemon is unavailable"
  (
    cd "$BACKEND_ROOT"
    uv run python -m py_compile ../tools/phase2_live_provider.py \
      ../tools/phase2_mock_provider.py ../tools/phase2_compose_flow.py
  )
  compose_active config --quiet >"$SMOKE_RUNTIME_DIR/stdout.log" \
    2>"$SMOKE_RUNTIME_DIR/stderr.log"
  printf 'phase2 smoke preflight: PASS\n'
}

prepare_base_stack() {
  local compose_start_log="$SMOKE_RUNTIME_DIR/compose-start.log" rc
  compose_active build backend frontend >/dev/null
  compose_active up -d postgres redis >/dev/null
  compose_active run --rm -T backend alembic upgrade head >/dev/null
  set +e
  compose_active up -d backend worker scheduler frontend >"$compose_start_log" 2>&1
  rc=$?
  set -e
  if [ "$rc" -ne 0 ]; then
    if grep -Fq "address already in use" "$compose_start_log"; then
      return 75
    fi
    return "$rc"
  fi
  wait_for_url "$SMOKE_BACKEND_URL/api/v1/health" 200 backend
  wait_for_url "$SMOKE_FRONTEND_URL" 200 frontend
  wait_for_worker
  wait_for_scheduler
  for service in postgres redis backend worker scheduler frontend; do
    [ "$(compose_active ps --status running -q "$service" | wc -l | tr -d ' ')" = "1" ] \
      || die "$service did not remain ready"
  done
}

verify_provider_ready() {
  local ready_code
  ready_code='from verboflex.core.config import Settings; from verboflex.services.bitbucket_oauth import BitbucketOAuthService,BitbucketOAuthTokenExchange; BitbucketOAuthService(settings=Settings(),token_exchange=BitbucketOAuthTokenExchange()); print("provider-ready")'
  compose_active exec -T backend python -c "$ready_code" \
    >>"$SMOKE_RUNTIME_DIR/stdout.log" 2>>"$SMOKE_RUNTIME_DIR/stderr.log"
  compose_active exec -T worker python -c "$ready_code" \
    >>"$SMOKE_RUNTIME_DIR/stdout.log" 2>>"$SMOKE_RUNTIME_DIR/stderr.log"
  compose_active exec -T scheduler python -c "$ready_code" \
    >>"$SMOKE_RUNTIME_DIR/stdout.log" 2>>"$SMOKE_RUNTIME_DIR/stderr.log"
  [ "$(grep -Fc 'provider-ready' "$SMOKE_RUNTIME_DIR/stdout.log")" = "3" ] \
    || die "backend, worker, and scheduler did not all become provider-ready"
}

bootstrap_admin() {
  printf '%s\n' "$SMOKE_TEMP_PASSWORD" | compose_active run --rm -T backend \
    python -m verboflex.cli bootstrap-admin --email "$SMOKE_EMAIL" \
      --display-name 'Phase Two Provider Admin' \
    >"$SMOKE_RUNTIME_DIR/bootstrap.out" 2>>"$SMOKE_RUNTIME_DIR/stderr.log"
  grep -Fxq 'First administrator created.' "$SMOKE_RUNTIME_DIR/bootstrap.out" \
    || die "administrator bootstrap did not complete"
}

verify_mock_audit() {
  local audit="$SMOKE_RUNTIME_DIR/provider-audit.jsonl"
  (
    cd "$BACKEND_ROOT"
    uv run python - "$audit" <<'PY'
import json
import sys

rows = [json.loads(line) for line in open(sys.argv[1], encoding="utf-8") if line.strip()]
assert rows, "provider audit is empty"
exchanges = [row for row in rows if row["category"] == "oauth-token-exchange"]
assert len(exchanges) == 3
assert all(row["grant_type"] == "client_credentials" for row in exchanges)
assert all(row["effective_scope"] == "repository" for row in exchanges)
assert not [row for row in rows if row["category"] == "forbidden-mutation"]
repository_reads = [row for row in rows if row["category"] == "repository-read"]
assert len(repository_reads) == 5
assert all(row["method"] == "GET" for row in repository_reads)
allowed_keys = {"category", "effective_scope", "grant_type", "method"}
assert all(set(row) == allowed_keys for row in rows)
print("phase2 provider audit: PASS (client_credentials, repository, five GETs, zero writes)")
PY
  )
}

verify_no_secret_surfaces() {
  local logs="$SMOKE_RUNTIME_DIR/compose.log" secret surface
  local -a traceback_surfaces
  compose_active logs --no-color >"$logs" 2>>"$SMOKE_RUNTIME_DIR/stderr.log"
  traceback_surfaces=(
    "$logs"
    "$SMOKE_RUNTIME_DIR/stdout.log"
    "$SMOKE_RUNTIME_DIR/stderr.log"
    "$SMOKE_RUNTIME_DIR/bootstrap.out"
    "$SMOKE_RUNTIME_DIR/provider-audit.jsonl"
  )
  for secret in "$SMOKE_TEMP_PASSWORD" "$SMOKE_NEW_PASSWORD" "$SMOKE_CLIENT_SECRET" \
    "$SMOKE_POSTGRES_PASSWORD" "$SMOKE_JWT_SECRET_KEY" "$SMOKE_ACCESS_TOKEN" \
    "$SMOKE_KEYRING"; do
    for surface in "${traceback_surfaces[@]}"; do
      if [ -f "$surface" ] && grep -Fq -- "$secret" "$surface"; then
        die "captured evidence exposed seeded secret material"
      fi
    done
    if [ -d "$SMOKE_RUNTIME_DIR/playwright" ] \
      && grep -R -a -Fq -- "$secret" "$SMOKE_RUNTIME_DIR/playwright"; then
      die "Playwright evidence exposed seeded secret material"
    fi
  done
  for surface in "${traceback_surfaces[@]}"; do
    if [ -f "$surface" ] \
      && grep -Eiq '(authorization:[[:space:]]*(bearer|basic)|client_secret[=:][^[:space:]]|access_token[=:][^[:space:]]|refresh_token[=:][^[:space:]]|gAAAAA[A-Za-z0-9_-]+)' "$surface"; then
      die "captured evidence contains credential or ciphertext shaped material"
    fi
  done
  if [ -d "$SMOKE_RUNTIME_DIR/playwright" ] \
    && grep -R -a -Eiq \
      '(VF e2e (reactivation|terminal cursor)|authorization:[[:space:]]*(bearer|basic)|client_secret|refresh_token|gAAAAA[A-Za-z0-9_-]+)' \
      "$SMOKE_RUNTIME_DIR/playwright"; then
    die "Playwright evidence contains seeded or credential-shaped material"
  fi
}

run_gap_playwright() {
  local backend_container grep_expression
  backend_container=$(compose_active ps -q backend)
  [ -n "$backend_container" ] || die "real backend container is unavailable to Playwright"
  grep_expression='role-aware Workspace navigation stays location-authoritative|non-admin admin-request denial|100/101 exact branches stay fail-closed|gap-closure mobile wizard traverses|unchanged active revision reactivation uses real backend state|51st mapping preview readiness consumes terminal cursor'
  (
    cd "$REPO_ROOT/frontend"
    PLAYWRIGHT_BASE_URL="$SMOKE_FRONTEND_URL" \
    PLAYWRIGHT_OUTPUT_DIR="$SMOKE_RUNTIME_DIR/playwright" \
    E2E_BACKEND_CONTAINER="$backend_container" \
    E2E_EMAIL="$SMOKE_EMAIL" E2E_TEMP_PASSWORD="$SMOKE_TEMP_PASSWORD" \
    E2E_PASSWORD="$SMOKE_NEW_PASSWORD" \
      npm run e2e -- --grep "$grep_expression"
  )
}

run_gap_boundaries() {
  if ! "$BACKEND_ROOT/.venv/bin/python" "$REPO_ROOT/tools/phase2_compose_flow.py" \
    --gap-boundaries "$SMOKE_BACKEND_URL" "$SMOKE_EMAIL" "$SMOKE_NEW_PASSWORD" \
    >>"$SMOKE_RUNTIME_DIR/stdout.log" 2>>"$SMOKE_RUNTIME_DIR/stderr.log"; then
    tail -n 1 "$SMOKE_RUNTIME_DIR/stderr.log" >&2
    die "0/1/50/51 Compose boundary probe failed"
  fi
  grep -Fq 'phase2 gap boundaries: PASS' "$SMOKE_RUNTIME_DIR/stdout.log" \
    || die "Compose boundary probe did not pass"
}

reset_provider_fixture_for_e2e() {
  compose_active exec -T backend python -c \
    'from verboflex.db.session import SessionFactory; from verboflex.models.bitbucket_connection import BitbucketConnection; session=SessionFactory(); connection=session.get_one(BitbucketConnection, 1); connection.generation=0; connection.access_token_ciphertext=None; connection.refresh_token_ciphertext=None; connection.scope_profile=None; connection.provider_expires_at=None; connection.connected_at=None; connection.revoked_at=None; session.commit(); session.close()'
}

run_base_client_credentials() {
  SMOKE_MODE="base-client-credentials"
  trap cleanup EXIT INT TERM
  initialize_runtime
  preflight
  prepare_base_stack
  verify_provider_ready
  verify_no_secret_surfaces
  printf 'phase2 base Compose client-credentials readiness: PASS\n'
}

run_mock_live_provider() {
  SMOKE_MODE="mock-live-provider"
  trap cleanup EXIT INT TERM
  initialize_runtime
  configure_mock_provider
  preflight
  prepare_base_stack
  wait_for_mock_provider
  bootstrap_admin
  if ! "$BACKEND_ROOT/.venv/bin/python" "$REPO_ROOT/tools/phase2_live_provider.py" \
    "$SMOKE_PROBE_ENV_FILE" >"$SMOKE_RUNTIME_DIR/stdout.log" \
    2>"$SMOKE_RUNTIME_DIR/stderr.log"; then
    sed -n '1p' "$SMOKE_RUNTIME_DIR/stderr.log" >&2
    die "production API provider probe rejected"
  fi
  grep -Fq 'phase2 live provider production API smoke: PASS' "$SMOKE_RUNTIME_DIR/stdout.log" \
    || die "production API provider probe did not pass"
  verify_mock_audit
  run_gap_boundaries
  verify_mock_audit
  reset_provider_fixture_for_e2e
  run_gap_playwright
  verify_no_secret_surfaces
  printf 'phase2 mocked live-provider production API and browser smoke: PASS\n'
}

preview_max_terminalization_seconds() {
  compose_active exec -T scheduler python -c \
    'from verboflex.core.config import get_settings; print(get_settings().preview_max_terminalization_seconds)'
}

wait_for_preview_state() {
  local expected=$1 timeout_seconds=${2:-30}
  case "$expected" in
    "running")
      [ -f "$SMOKE_WORKER_LOSS_STATE" ] \
        || die "running preview evidence is unavailable"
      ;;
    "timed_out")
      if ! "$BACKEND_ROOT/.venv/bin/python" "$REPO_ROOT/tools/phase2_compose_flow.py" \
        --worker-loss-terminal "$SMOKE_BACKEND_URL" "$SMOKE_EMAIL" "$SMOKE_NEW_PASSWORD" \
        "$SMOKE_WORKER_LOSS_STATE" "$timeout_seconds" \
        >>"$SMOKE_RUNTIME_DIR/stdout.log" 2>>"$SMOKE_RUNTIME_DIR/stderr.log"; then
        tail -n 1 "$SMOKE_RUNTIME_DIR/stderr.log" >&2
        die "worker-loss terminal-state probe failed"
      fi
      ;;
    "succeeded")
      grep -Fq 'phase2 worker-loss recovery: PASS' "$SMOKE_RUNTIME_DIR/stdout.log" \
        || die "replacement worker retry did not succeed"
      ;;
    *) die "unsupported worker-loss preview state" ;;
  esac
}

retry_preview_job() {
  local timeout_seconds=$1
  if ! "$BACKEND_ROOT/.venv/bin/python" "$REPO_ROOT/tools/phase2_compose_flow.py" \
    --worker-loss-recovery "$SMOKE_BACKEND_URL" "$SMOKE_EMAIL" "$SMOKE_NEW_PASSWORD" \
    "$SMOKE_WORKER_LOSS_STATE" "$timeout_seconds" \
    >>"$SMOKE_RUNTIME_DIR/stdout.log" 2>>"$SMOKE_RUNTIME_DIR/stderr.log"; then
    tail -n 1 "$SMOKE_RUNTIME_DIR/stderr.log" >&2
    die "worker-loss watchdog and replacement recovery failed"
  fi
}

assert_original_preview_unchanged() {
  grep -Fq 'watchdog terminalized, replacement isolated' "$SMOKE_RUNTIME_DIR/stdout.log" \
    || die "retry did not preserve the original timed-out preview"
}

run_worker_loss() {
  local worker_container max_bound deadline remaining terminal_error="time_limit_exceeded"
  SMOKE_DEPLOYMENT_OVERLAY=$1
  compose_deployment_overlay "$SMOKE_DEPLOYMENT_OVERLAY" >/dev/null
  SMOKE_MODE="mock-live-provider"
  trap cleanup EXIT INT TERM
  initialize_runtime
  configure_mock_provider
  preflight
  prepare_base_stack
  wait_for_mock_provider
  bootstrap_admin
  : >"$SMOKE_BLOCK_FILE"
  chmod 600 "$SMOKE_BLOCK_FILE"
  if ! "$BACKEND_ROOT/.venv/bin/python" "$REPO_ROOT/tools/phase2_compose_flow.py" \
    --worker-loss-setup "$SMOKE_BACKEND_URL" "$SMOKE_EMAIL" "$SMOKE_TEMP_PASSWORD" \
    "$SMOKE_NEW_PASSWORD" "$SMOKE_WORKER_LOSS_STATE" \
    >>"$SMOKE_RUNTIME_DIR/stdout.log" 2>>"$SMOKE_RUNTIME_DIR/stderr.log"; then
    tail -n 1 "$SMOKE_RUNTIME_DIR/stderr.log" >&2
    die "worker-loss durable-running setup failed"
  fi
  wait_for_preview_state "running"
  wait_for_file "$SMOKE_BLOCK_STARTED_FILE" "preview provider fault gate"
  worker_container=$(compose_active ps -q worker)
  [ -n "$worker_container" ] || die "owning worker container is unavailable"
  docker kill --signal=KILL "$worker_container" >/dev/null
  rm -f "$SMOKE_BLOCK_FILE"
  compose_active rm -f worker >/dev/null
  compose_active up -d worker >/dev/null
  wait_for_worker
  max_bound=$(preview_max_terminalization_seconds)
  deadline=$((SECONDS + max_bound + 5))
  remaining=$((deadline - SECONDS))
  wait_for_preview_state "timed_out" "$remaining"
  grep -Fq "$terminal_error" "$SMOKE_RUNTIME_DIR/stdout.log" \
    || die "watchdog terminal error code was not observed"
  retry_preview_job "$remaining"
  wait_for_preview_state "succeeded" 60
  assert_original_preview_unchanged
  verify_no_secret_surfaces
  printf 'phase2 worker-loss %s overlay: PASS (timed_out/time_limit_exceeded, replacement retry succeeded)\n' \
    "$SMOKE_DEPLOYMENT_OVERLAY"
}

run_mock_provider_with_port_retry() {
  local attempt rc
  for attempt in 1 2 3; do
    set +e
    "$SCRIPT_DIR/phase2_smoke.sh" --mock-live-provider-once
    rc=$?
    set -e
    if [ "$rc" -eq 0 ]; then return 0; fi
    if [ "$rc" -ne 75 ]; then return "$rc"; fi
    if [ "$attempt" -lt 3 ]; then
      printf 'phase2 smoke: address already in use, retrying isolated attempt %s/3\n' \
        "$((attempt + 1))" >&2
    fi
  done
  die "host-port binding remained unavailable after three isolated attempts"
}

run_worker_loss_for_overlay_with_port_retry() {
  local deployment_overlay=$1 attempt rc
  compose_deployment_overlay "$deployment_overlay" >/dev/null
  for attempt in 1 2 3; do
    set +e
    "$SCRIPT_DIR/phase2_smoke.sh" --worker-loss-once "$deployment_overlay"
    rc=$?
    set -e
    if [ "$rc" -eq 0 ]; then return 0; fi
    if [ "$rc" -ne 75 ]; then return "$rc"; fi
    if [ "$attempt" -lt 3 ]; then
      printf 'phase2 %s worker-loss: address already in use, retrying isolated attempt %s/3\n' \
        "$deployment_overlay" "$((attempt + 1))" >&2
    fi
  done
  die "$deployment_overlay worker-loss host-port binding remained unavailable after three isolated attempts"
}

run_worker_loss_dual_overlay() {
  run_worker_loss_for_overlay_with_port_retry staging
  run_worker_loss_for_overlay_with_port_retry production
  printf 'phase2 dual-overlay worker-loss smoke: PASS (staging and production)\n'
}

live_provider_gate() {
  local live_env_file="${VERBOFLEX_PHASE2_LIVE_ENV_FILE:-$REPO_ROOT/.env.phase2-live}"
  if [ "${VERBOFLEX_PHASE2_LIVE_OPT_IN:-}" != "production-api-read-only-confirmed" ] \
    || [ ! -f "$live_env_file" ]; then
    printf 'phase2 live provider: SKIP (explicit opt-in and local server configuration required)\n'
    return 0
  fi
  "$BACKEND_ROOT/.venv/bin/python" "$REPO_ROOT/tools/phase2_live_provider.py" "$live_env_file"
}

run_gap_closure() {
  "$SCRIPT_DIR/phase2_smoke.sh" --base-client-credentials
  "$SCRIPT_DIR/phase2_smoke.sh" --mock-live-provider
  "$SCRIPT_DIR/phase2_smoke.sh" --mock-provider --worker-loss
  "$SCRIPT_DIR/phase2_smoke.sh" --live-provider-read-only
  printf 'phase2 deployment gap closure: PASS (base, mock, worker-loss; live gate evaluated)\n'
}

case "${1:-}:${2:-}" in
  --mock-provider:--worker-loss) run_worker_loss_dual_overlay ;;
  --worker-loss-once:staging|--worker-loss-once:production) run_worker_loss "$2" ;;
  --base-client-credentials:) run_base_client_credentials ;;
  --mock-live-provider:) run_mock_provider_with_port_retry ;;
  --mock-live-provider-once:) run_mock_live_provider ;;
  --mock-provider:) run_mock_provider_with_port_retry ;;
  --gap-closure:) run_gap_closure ;;
  --live-provider-read-only:) live_provider_gate ;;
  *) die "usage: tools/phase2_smoke.sh --gap-closure|--base-client-credentials|--mock-live-provider|--mock-provider --worker-loss|--live-provider-read-only" ;;
esac

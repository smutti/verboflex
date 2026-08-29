#!/usr/bin/env bash
set -euo pipefail

readonly SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
readonly REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
readonly BACKEND_ROOT="$REPO_ROOT/backend"

SMOKE_MODE=""
SMOKE_PROJECT=""
SMOKE_RUNTIME_DIR=""
SMOKE_ENV_FILE=""
SMOKE_OVERRIDE_FILE=""
SMOKE_PROBE_ENV_FILE=""
SMOKE_IMAGE_TAG=""
SMOKE_BACKEND_URL=""
SMOKE_EMAIL="phase02-smoke@example.com"
SMOKE_TEMP_PASSWORD=""
SMOKE_NEW_PASSWORD=""
SMOKE_CLIENT_SECRET=""
SMOKE_ACCESS_TOKEN=""
SMOKE_KEYRING=""

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

compose_mock() {
  docker compose --project-name "$SMOKE_PROJECT" --env-file "$SMOKE_ENV_FILE" \
    -f "$REPO_ROOT/docker-compose.yml" -f "$SMOKE_OVERRIDE_FILE" "$@"
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
    'keyUsage = critical,keyCertSign,cRLSign' >"$config"
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
    -CAcreateserial -out "$SMOKE_RUNTIME_DIR/server.pem" \
    -extensions server_ext -extfile "$config" >/dev/null 2>&1
  chmod 600 "$SMOKE_RUNTIME_DIR"/*.key "$SMOKE_RUNTIME_DIR"/*.pem
}

initialize_runtime() {
  local backend_port suffix
  suffix="$$-$(date +%s)"
  SMOKE_PROJECT="verboflex_phase02_35_${suffix//-/_}"
  SMOKE_RUNTIME_DIR=$(mktemp -d /tmp/verboflex-phase02-35.XXXXXX)
  SMOKE_ENV_FILE="$SMOKE_RUNTIME_DIR/owner-only.env"
  SMOKE_OVERRIDE_FILE="$SMOKE_RUNTIME_DIR/mock-provider.yml"
  SMOKE_PROBE_ENV_FILE="$SMOKE_RUNTIME_DIR/local-api-probe.env"
  SMOKE_IMAGE_TAG="phase02-35-$suffix"
  chmod 700 "$SMOKE_RUNTIME_DIR"
  backend_port=$(random_port)
  SMOKE_BACKEND_URL="http://localhost:$backend_port"
  SMOKE_TEMP_PASSWORD="PhaseTwoTemporary-$(openssl rand -hex 10)!"
  SMOKE_NEW_PASSWORD="PhaseTwoOrdinary-$(openssl rand -hex 10)!"
  SMOKE_CLIENT_SECRET="mock-client-secret-$(openssl rand -hex 24)"
  SMOKE_ACCESS_TOKEN="mock-provider-bearer-$(openssl rand -hex 24)"
  SMOKE_KEYRING=$(
    cd "$BACKEND_ROOT"
    uv run python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
  )
  printf '%s\n' \
    "VERBOFLEX_BACKEND_PORT=$backend_port" \
    "VERBOFLEX_IMAGE_TAG=$SMOKE_IMAGE_TAG" \
    'VERBOFLEX_BITBUCKET_OAUTH_CLIENT_ID=phase2-mock-consumer' \
    "VERBOFLEX_BITBUCKET_OAUTH_CLIENT_SECRET=$SMOKE_CLIENT_SECRET" \
    "VERBOFLEX_BITBUCKET_TOKEN_ENCRYPTION_KEYRING=$SMOKE_KEYRING" \
    "PHASE2_RUNTIME_DIR=$SMOKE_RUNTIME_DIR" \
    "PHASE2_REPO_ROOT=$REPO_ROOT" \
    "MOCK_ACCESS_TOKEN=$SMOKE_ACCESS_TOKEN" >"$SMOKE_ENV_FILE"
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
    '    command: ["python", "/mock/phase2_mock_provider.py"]' \
    '    volumes:' \
    '      - ${PHASE2_REPO_ROOT}/tools/phase2_mock_provider.py:/mock/phase2_mock_provider.py:ro' \
    '      - ${PHASE2_RUNTIME_DIR}:/run/phase2' \
    '    networks:' \
    '      default:' \
    '        aliases: [bitbucket.org, api.bitbucket.org]' \
    '  backend:' \
    '    environment:' \
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
    uv run python -m py_compile ../tools/phase2_live_provider.py ../tools/phase2_mock_provider.py
  )
  compose_active config --quiet >"$SMOKE_RUNTIME_DIR/stdout.log" \
    2>"$SMOKE_RUNTIME_DIR/stderr.log"
  printf 'phase2 smoke preflight: PASS\n'
}

prepare_base_stack() {
  local compose_start_log="$SMOKE_RUNTIME_DIR/compose-start.log" rc
  compose_active build backend >/dev/null
  compose_active up -d postgres redis >/dev/null
  compose_active run --rm -T backend alembic upgrade head >/dev/null
  set +e
  compose_active up -d backend worker >"$compose_start_log" 2>&1
  rc=$?
  set -e
  if [ "$rc" -ne 0 ]; then
    if grep -Fq "address already in use" "$compose_start_log"; then
      return 75
    fi
    return "$rc"
  fi
  wait_for_url "$SMOKE_BACKEND_URL/api/v1/health" 200 backend
  wait_for_worker
}

verify_provider_ready() {
  local ready_code
  ready_code='from verboflex.core.config import Settings; from verboflex.services.bitbucket_oauth import BitbucketOAuthService,BitbucketOAuthTokenExchange; BitbucketOAuthService(settings=Settings(),token_exchange=BitbucketOAuthTokenExchange()); print("provider-ready")'
  compose_active exec -T backend python -c "$ready_code" \
    >>"$SMOKE_RUNTIME_DIR/stdout.log" 2>>"$SMOKE_RUNTIME_DIR/stderr.log"
  compose_active exec -T worker python -c "$ready_code" \
    >>"$SMOKE_RUNTIME_DIR/stdout.log" 2>>"$SMOKE_RUNTIME_DIR/stderr.log"
  [ "$(grep -Fc 'provider-ready' "$SMOKE_RUNTIME_DIR/stdout.log")" = "2" ] \
    || die "backend and worker did not both become provider-ready"
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
assert len(exchanges) == 2
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
    "$SMOKE_ACCESS_TOKEN" "$SMOKE_KEYRING"; do
    for surface in "${traceback_surfaces[@]}"; do
      if [ -f "$surface" ] && grep -Fq -- "$secret" "$surface"; then
        die "captured evidence exposed seeded secret material"
      fi
    done
  done
  for surface in "${traceback_surfaces[@]}"; do
    if [ -f "$surface" ] \
      && grep -Eiq '(authorization:[[:space:]]*(bearer|basic)|client_secret[=:][^[:space:]]|access_token[=:][^[:space:]]|refresh_token[=:][^[:space:]]|gAAAAA[A-Za-z0-9_-]+)' "$surface"; then
      die "captured evidence contains credential or ciphertext shaped material"
    fi
  done
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
  bootstrap_admin
  "$BACKEND_ROOT/.venv/bin/python" "$REPO_ROOT/tools/phase2_live_provider.py" \
    "$SMOKE_PROBE_ENV_FILE" >"$SMOKE_RUNTIME_DIR/stdout.log" \
    2>"$SMOKE_RUNTIME_DIR/stderr.log"
  grep -Fq 'phase2 live provider production API smoke: PASS' "$SMOKE_RUNTIME_DIR/stdout.log" \
    || die "production API provider probe did not pass"
  verify_mock_audit
  verify_no_secret_surfaces
  printf 'phase2 mocked live-provider production API smoke: PASS\n'
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

live_provider_gate() {
  local live_env_file="${VERBOFLEX_PHASE2_LIVE_ENV_FILE:-$REPO_ROOT/.env.phase2-live}"
  if [ "${VERBOFLEX_PHASE2_LIVE_OPT_IN:-}" != "production-api-read-only-confirmed" ] \
    || [ ! -f "$live_env_file" ]; then
    printf 'phase2 live provider: SKIP (explicit opt-in and local server configuration required)\n'
    return 0
  fi
  "$BACKEND_ROOT/.venv/bin/python" "$REPO_ROOT/tools/phase2_live_provider.py" "$live_env_file"
}

case "${1:-}" in
  --base-client-credentials) run_base_client_credentials ;;
  --mock-live-provider) run_mock_provider_with_port_retry ;;
  --mock-live-provider-once) run_mock_live_provider ;;
  --mock-provider) run_mock_provider_with_port_retry ;;
  --live-provider-read-only) live_provider_gate ;;
  *) die "usage: tools/phase2_smoke.sh --base-client-credentials|--mock-live-provider|--live-provider-read-only" ;;
esac

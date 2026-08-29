#!/usr/bin/env bash
set -euo pipefail

readonly SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
readonly REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
readonly BACKEND_ROOT="$REPO_ROOT/backend"
readonly FRONTEND_ROOT="$REPO_ROOT/frontend"

SMOKE_PROJECT=""
SMOKE_RUNTIME_DIR=""
SMOKE_ENV_FILE=""
SMOKE_OVERRIDE_FILE=""
SMOKE_IMAGE_TAG=""
SMOKE_BACKEND_URL=""
SMOKE_FRONTEND_URL=""
SMOKE_EMAIL="phase02-smoke@example.com"
SMOKE_TEMP_PASSWORD=""
SMOKE_JWT_SECRET=""
SMOKE_CLIENT_SECRET=""
SMOKE_ACCESS_TOKEN=""
SMOKE_REFRESH_TOKEN=""

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

compose() {
  docker compose --project-name "$SMOKE_PROJECT" --env-file "$SMOKE_ENV_FILE" \
    -f "$REPO_ROOT/docker-compose.yml" \
    -f "$REPO_ROOT/docker-compose.staging.yml" \
    -f "$SMOKE_OVERRIDE_FILE" "$@"
}

cleanup() {
  local incoming_rc=$? cleanup_rc=0 image
  trap - EXIT INT TERM
  if [ "$incoming_rc" -ne 0 ] && [ -n "$SMOKE_RUNTIME_DIR" ] \
    && [ -s "$SMOKE_RUNTIME_DIR/provider-audit.jsonl" ]; then
    "$BACKEND_ROOT/.venv/bin/python" - "$SMOKE_RUNTIME_DIR/provider-audit.jsonl" <<'PY' >&2 || true
import collections
import json
import sys

rows = [json.loads(line) for line in open(sys.argv[1], encoding="utf-8") if line.strip()]
print("phase2-smoke bounded provider failure audit:", dict(collections.Counter(row["category"] for row in rows)))
PY
  fi
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
    for image in "verboflex-backend:$SMOKE_IMAGE_TAG" "verboflex-frontend:$SMOKE_IMAGE_TAG"; do
      docker image rm "$image" >/dev/null 2>&1 || true
    done
  fi
  if [ -n "$SMOKE_RUNTIME_DIR" ] && [ -d "$SMOKE_RUNTIME_DIR" ]; then
    rm -rf "$SMOKE_RUNTIME_DIR"
  fi
  if [ "$cleanup_rc" -ne 0 ]; then
    printf 'phase2-smoke error: isolated Compose teardown left resources behind\n' >&2
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
  compose ps >&2 || true
  compose logs --no-color --tail 80 >&2 || true
  die "$label readiness timed out"
}

wait_for_postgres() {
  local deadline rc=1
  deadline=$((SECONDS + 180))
  while [ "$SECONDS" -lt "$deadline" ]; do
    set +e
    compose exec -T postgres pg_isready -U verboflex -d verboflex >/dev/null 2>&1
    rc=$?
    set -e
    [ "$rc" -eq 0 ] && return 0
    sleep 1
  done
  die "PostgreSQL readiness timed out"
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
    'authorityKeyIdentifier = keyid:always,issuer' >"$config"
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
    'basicConstraints = critical,CA:FALSE' \
    'keyUsage = critical,digitalSignature,keyEncipherment' \
    'extendedKeyUsage = serverAuth' \
    'subjectKeyIdentifier = hash' \
    'subjectAltName = @alt_names' \
    '[server_ext]' \
    'basicConstraints = critical,CA:FALSE' \
    'keyUsage = critical,digitalSignature,keyEncipherment' \
    'extendedKeyUsage = serverAuth' \
    'subjectKeyIdentifier = hash' \
    'authorityKeyIdentifier = keyid:always,issuer' \
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
  local backend_port frontend_port postgres_password keyring suffix
  suffix="$$-$(date +%s)"
  SMOKE_PROJECT="verboflex_phase02_smoke_${suffix//-/_}"
  SMOKE_RUNTIME_DIR=$(mktemp -d /tmp/verboflex-phase02-smoke.XXXXXX)
  SMOKE_ENV_FILE="$SMOKE_RUNTIME_DIR/smoke.env"
  SMOKE_OVERRIDE_FILE="$SMOKE_RUNTIME_DIR/mock-provider.yml"
  SMOKE_IMAGE_TAG="phase02-smoke-$suffix"
  chmod 700 "$SMOKE_RUNTIME_DIR"
  : >"$SMOKE_ENV_FILE"
  : >"$SMOKE_RUNTIME_DIR/provider-audit.jsonl"
  chmod 600 "$SMOKE_ENV_FILE" "$SMOKE_RUNTIME_DIR/provider-audit.jsonl"
  backend_port=$(random_port)
  frontend_port=$(random_port)
  while [ "$frontend_port" = "$backend_port" ]; do frontend_port=$(random_port); done
  SMOKE_BACKEND_URL="http://localhost:$backend_port"
  SMOKE_FRONTEND_URL="http://localhost:$frontend_port"
  SMOKE_TEMP_PASSWORD="PhaseTwoTemporary-$(openssl rand -hex 10)!"
  SMOKE_JWT_SECRET=$(openssl rand -hex 32)
  SMOKE_CLIENT_SECRET=$(openssl rand -hex 24)
  SMOKE_ACCESS_TOKEN="mock-access-$(openssl rand -hex 24)"
  SMOKE_REFRESH_TOKEN="mock-refresh-$(openssl rand -hex 24)"
  postgres_password=$(openssl rand -hex 24)
  keyring=$(
    cd "$BACKEND_ROOT"
    uv run python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
  )
  make_tls_material
  printf '%s\n' \
    "VERBOFLEX_POSTGRES_PASSWORD=$postgres_password" \
    "VERBOFLEX_JWT_SECRET_KEY=$SMOKE_JWT_SECRET" \
    "VERBOFLEX_CORS_ORIGINS=[\"$SMOKE_FRONTEND_URL\"]" \
    'VERBOFLEX_REFRESH_COOKIE_SECURE=true' \
    "VERBOFLEX_BACKEND_PORT=$backend_port" \
    "VERBOFLEX_FRONTEND_PORT=$frontend_port" \
    "VITE_API_BASE_URL=$SMOKE_BACKEND_URL" \
    "VERBOFLEX_IMAGE_TAG=$SMOKE_IMAGE_TAG" \
    'BITBUCKET_CLIENT_ID=phase2-mock-consumer' \
    "BITBUCKET_CLIENT_SECRET=$SMOKE_CLIENT_SECRET" \
    "BITBUCKET_CALLBACK_URL=$SMOKE_BACKEND_URL/api/v1/admin/bitbucket/oauth/callback" \
    "BITBUCKET_TOKEN_ENCRYPTION_KEYRING=$keyring" \
    "PHASE2_RUNTIME_DIR=$SMOKE_RUNTIME_DIR" \
    "PHASE2_REPO_ROOT=$REPO_ROOT" \
    "MOCK_ACCESS_TOKEN=$SMOKE_ACCESS_TOKEN" \
    "MOCK_REFRESH_TOKEN=$SMOKE_REFRESH_TOKEN" >"$SMOKE_ENV_FILE"

  printf '%s\n' \
    'services:' \
    '  mock-bitbucket:' \
    '    image: python:3.14-slim' \
    '    environment:' \
    '      MOCK_AUDIT_FILE: /run/phase2/provider-audit.jsonl' \
    '      MOCK_ACCESS_TOKEN: ${MOCK_ACCESS_TOKEN}' \
    '      MOCK_REFRESH_TOKEN: ${MOCK_REFRESH_TOKEN}' \
    '      MOCK_CLIENT_ID: ${BITBUCKET_CLIENT_ID}' \
    '      MOCK_CLIENT_SECRET: ${BITBUCKET_CLIENT_SECRET}' \
    '      MOCK_CALLBACK_URL: ${BITBUCKET_CALLBACK_URL}' \
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
    '      VERBOFLEX_BITBUCKET_OAUTH_CLIENT_ID: ${BITBUCKET_CLIENT_ID}' \
    '      VERBOFLEX_BITBUCKET_OAUTH_CLIENT_SECRET: ${BITBUCKET_CLIENT_SECRET}' \
    '      VERBOFLEX_BITBUCKET_OAUTH_CALLBACK_URI: ${BITBUCKET_CALLBACK_URL}' \
    '      VERBOFLEX_BITBUCKET_TOKEN_ENCRYPTION_KEYRING: ${BITBUCKET_TOKEN_ENCRYPTION_KEYRING}' \
    '      SSL_CERT_FILE: /run/phase2/ca.pem' \
    '    volumes:' \
    '      - ${PHASE2_RUNTIME_DIR}/ca.pem:/run/phase2/ca.pem:ro' \
    '      - ${PHASE2_RUNTIME_DIR}/ca.pem:/opt/venv/lib/python3.14/site-packages/certifi/cacert.pem:ro' \
    '    depends_on:' \
    '      mock-bitbucket:' \
    '        condition: service_started' \
    '  worker:' \
    '    environment:' \
    '      VERBOFLEX_BITBUCKET_OAUTH_CLIENT_ID: ${BITBUCKET_CLIENT_ID}' \
    '      VERBOFLEX_BITBUCKET_OAUTH_CLIENT_SECRET: ${BITBUCKET_CLIENT_SECRET}' \
    '      VERBOFLEX_BITBUCKET_OAUTH_CALLBACK_URI: ${BITBUCKET_CALLBACK_URL}' \
    '      VERBOFLEX_BITBUCKET_TOKEN_ENCRYPTION_KEYRING: ${BITBUCKET_TOKEN_ENCRYPTION_KEYRING}' \
    '      SSL_CERT_FILE: /run/phase2/ca.pem' \
    '    volumes:' \
    '      - ${PHASE2_RUNTIME_DIR}/ca.pem:/run/phase2/ca.pem:ro' \
    '      - ${PHASE2_RUNTIME_DIR}/ca.pem:/opt/venv/lib/python3.14/site-packages/certifi/cacert.pem:ro' \
    '    depends_on:' \
    '      mock-bitbucket:' \
    '        condition: service_started' >"$SMOKE_OVERRIDE_FILE"
  chmod 600 "$SMOKE_OVERRIDE_FILE"
}

preflight() {
  command -v docker >/dev/null 2>&1 || die "Docker is unavailable"
  command -v openssl >/dev/null 2>&1 || die "OpenSSL is unavailable"
  command -v curl >/dev/null 2>&1 || die "curl is unavailable"
  docker info >/dev/null 2>&1 || die "Docker daemon is unavailable"
  (cd "$BACKEND_ROOT" && uv run python -m py_compile \
    ../tools/phase2_mock_provider.py ../tools/phase2_compose_flow.py)
  compose config >/dev/null
  printf 'phase2 smoke preflight: PASS\n'
}

prepare_stack() {
  compose build backend worker frontend
  compose up -d mock-bitbucket postgres redis
  wait_for_postgres
  compose run --rm -T backend alembic upgrade head
  compose run --rm -T backend alembic downgrade base
  compose run --rm -T backend alembic upgrade head
  printf '%s\n' "$SMOKE_TEMP_PASSWORD" | compose run --rm -T backend \
    python -m verboflex.cli bootstrap-admin --email "$SMOKE_EMAIL" --display-name 'Phase Two Admin' \
    >"$SMOKE_RUNTIME_DIR/bootstrap.out"
  grep -Fxq 'First administrator created.' "$SMOKE_RUNTIME_DIR/bootstrap.out" \
    || die "admin bootstrap did not reach its non-secret success checkpoint"
  compose up -d backend worker frontend
  wait_for_url "$SMOKE_BACKEND_URL/api/v1/health" 200 backend
  wait_for_url "$SMOKE_FRONTEND_URL/login" 200 frontend
  compose exec -T backend python -c \
    "import json,urllib.request; assert json.load(urllib.request.urlopen('https://bitbucket.org/_health', timeout=5)) == {'status':'ok'}"
  [ "$(compose ps -q backend)" != "$(compose ps -q worker)" ] \
    || die "backend and Celery worker are not distinct containers"
  [ "$(compose ps --status running -q worker | wc -l | tr -d ' ')" = "1" ] \
    || die "Celery worker is not running"
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
assert sum(row["category"] == "oauth-token-exchange" for row in rows) == 1
assert not [row for row in rows if row["category"] == "forbidden-mutation"]
repository_reads = [row for row in rows if row["category"] == "repository-read"]
assert repository_reads and all(row["method"] == "GET" for row in repository_reads)
paths = [row["path"] for row in repository_reads]
assert any("/refs/branches" in path for path in paths)
assert any("/src/" in path and path.endswith("strings.xml") for path in paths)
assert any("/src/" in path and path.endswith("app_en.ts") for path in paths)
assert any("/src/" in path and path.endswith("catalog.json") for path in paths)
assert any("/src/" in path and path.endswith("Localizable.strings") for path in paths)
allowed_keys = {"category", "method", "path"}
assert all(set(row) == allowed_keys for row in rows)
print(f"phase2 provider audit: PASS ({len(repository_reads)} GET reads, zero writes)")
PY
  )
}

verify_no_secret_logs() {
  local logs="$SMOKE_RUNTIME_DIR/compose.log" secret
  compose logs --no-color >"$logs"
  for secret in "$SMOKE_TEMP_PASSWORD" "$SMOKE_JWT_SECRET" "$SMOKE_CLIENT_SECRET" \
    "$SMOKE_ACCESS_TOKEN" "$SMOKE_REFRESH_TOKEN"; do
    if grep -Fq -- "$secret" "$logs"; then
      die "Compose logs exposed secret material"
    fi
  done
  if grep -Eiq '(authorization:[[:space:]]*(bearer|basic)|client_secret[=:][^[:space:]]|refresh_token[=:][^[:space:]])' "$logs"; then
    die "Compose logs contain credential-shaped material"
  fi
}

run_mock_provider() {
  trap cleanup EXIT INT TERM
  initialize_runtime
  preflight
  prepare_stack
  "$BACKEND_ROOT/.venv/bin/python" "$REPO_ROOT/tools/phase2_compose_flow.py" \
    "$SMOKE_BACKEND_URL" "$SMOKE_EMAIL" "$SMOKE_TEMP_PASSWORD"
  verify_mock_audit
  (
    cd "$FRONTEND_ROOT"
    PLAYWRIGHT_BASE_URL="$SMOKE_FRONTEND_URL" \
    PLAYWRIGHT_OUTPUT_DIR="$SMOKE_RUNTIME_DIR/playwright" \
      npm run e2e -- admin-configuration.spec.ts
  )
  verify_no_secret_logs
  printf 'phase2 mocked deployment smoke: PASS\n'
}

live_provider_gate() {
  local live_env_file="${VERBOFLEX_PHASE2_LIVE_ENV_FILE:-$REPO_ROOT/.env.phase2-live}"
  [ -x "$BACKEND_ROOT/.venv/bin/python" ] || die "backend Python environment is unavailable"
  [ -f "$live_env_file" ] || die "secure live provider environment file is unavailable"
  "$BACKEND_ROOT/.venv/bin/python" "$REPO_ROOT/tools/phase2_live_provider.py" "$live_env_file"
}

case "${1:-}" in
  --mock-provider) run_mock_provider ;;
  --live-provider-read-only) live_provider_gate ;;
  *) die "usage: tools/phase2_smoke.sh --mock-provider|--live-provider-read-only" ;;
esac

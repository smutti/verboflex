#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH='' cd -- "$SCRIPT_DIR/.." && pwd)
readonly SCRIPT_DIR REPO_ROOT
readonly BACKEND_ROOT="$REPO_ROOT/backend"
readonly FRONTEND_ROOT="$REPO_ROOT/frontend"

SMOKE_PROJECT=""
SMOKE_RUNTIME_DIR=""
SMOKE_ENV_FILE=""
SMOKE_OVERRIDE_FILE=""
SMOKE_PROVIDER_SCRIPT=""
SMOKE_PROVIDER_CONTROL_FILE=""
SMOKE_PROVIDER_AUDIT_FILE=""
SMOKE_PROVIDER_BLOCK_STARTED_FILE=""
SMOKE_IMAGE_TAG=""
SMOKE_BACKEND_URL=""
SMOKE_FRONTEND_URL=""
SMOKE_POSTGRES_PORT=""
SMOKE_CLIENT_SECRET=""
SMOKE_POSTGRES_PASSWORD=""
SMOKE_JWT_SECRET_KEY=""
SMOKE_ACCESS_TOKEN=""
SMOKE_KEYRING=""

die() {
  printf 'phase3-smoke error: %s\n' "$1" >&2
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
    -f "$REPO_ROOT/docker-compose.yml" -f "$SMOKE_OVERRIDE_FILE" "$@"
}

cleanup() {
  local incoming_rc=$? cleanup_rc=0 runtime_dir="$SMOKE_RUNTIME_DIR"
  trap - EXIT INT TERM
  if [ -n "$SMOKE_PROJECT" ] && [ -n "$SMOKE_ENV_FILE" ] && [ -f "$SMOKE_ENV_FILE" ]; then
    set +e
    if ! compose down --volumes --remove-orphans --timeout 10 >/dev/null 2>&1; then
      cleanup_rc=1
    fi
    [ -z "$(docker ps -aq --filter "label=com.docker.compose.project=$SMOKE_PROJECT")" ] \
      || cleanup_rc=1
    [ -z "$(docker volume ls -q --filter "label=com.docker.compose.project=$SMOKE_PROJECT")" ] \
      || cleanup_rc=1
    [ -z "$(docker network ls -q --filter "label=com.docker.compose.project=$SMOKE_PROJECT")" ] \
      || cleanup_rc=1
    set -e
  fi
  if [ -n "$SMOKE_IMAGE_TAG" ]; then
    docker image rm "verboflex-backend:$SMOKE_IMAGE_TAG" >/dev/null 2>&1 || true
    docker image rm "verboflex-frontend:$SMOKE_IMAGE_TAG" >/dev/null 2>&1 || true
  fi
  if [ -n "$runtime_dir" ] && [ -d "$runtime_dir" ]; then
    rm -rf "$runtime_dir"
  fi
  [ -z "$runtime_dir" ] || [ ! -e "$runtime_dir" ] || cleanup_rc=1
  if [ "$cleanup_rc" -ne 0 ]; then
    printf 'phase3-smoke error: disposable resources or owner-only files remain\n' >&2
    incoming_rc=1
  fi
  if [ "$cleanup_rc" -ne 0 ]; then
    exit 1
  fi
  return "$incoming_rc"
}

wait_for_url() {
  local url=$1 expected=$2 label=$3 deadline status rc
  deadline=$((SECONDS + 180))
  while [ "$SECONDS" -lt "$deadline" ]; do
    set +e
    status=$(curl --silent --show-error --max-time 3 --output /dev/null \
      --write-out '%{http_code}' "$url")
    rc=$?
    set -e
    if [ "$rc" -eq 0 ] && [ "$status" = "$expected" ]; then return 0; fi
    sleep 1
  done
  compose ps >&2 || true
  die "$label readiness timed out"
}

wait_for_worker() {
  local deadline
  deadline=$((SECONDS + 180))
  while [ "$SECONDS" -lt "$deadline" ]; do
    if [ "$(compose ps --status running -q worker | wc -l | tr -d ' ')" = "1" ] \
      && compose exec -T worker celery -A verboflex.worker.celery_app inspect ping \
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
    if [ "$(compose ps --status running -q scheduler | wc -l | tr -d ' ')" = "1" ] \
      && compose exec -T scheduler python -c \
        'from verboflex.worker.celery_app import app; assert {"preview-stale-job-watchdog", "import-stale-execution-watchdog"} <= set(app.conf.beat_schedule)' \
        >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  die "Celery Beat readiness timed out"
}

write_mock_provider() {
  cat >"$SMOKE_PROVIDER_SCRIPT" <<'PY'
#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import os
import ssl
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

AUDIT = Path(os.environ["MOCK_AUDIT_FILE"])
CONTROL = Path(os.environ["MOCK_CONTROL_FILE"])
BLOCK_STARTED = Path(os.environ["MOCK_BLOCK_STARTED_FILE"])
ACCESS_TOKEN = os.environ["MOCK_ACCESS_TOKEN"]
CLIENT_ID = os.environ["MOCK_CLIENT_ID"]
CLIENT_SECRET = os.environ["MOCK_CLIENT_SECRET"]
SCOPE = "pullrequest:write pullrequest repository:write repository"
LOCK = threading.Lock()


def state():
    return json.loads(CONTROL.read_text(encoding="utf-8"))


def record(*, category, method, resource_family, status):
    row = json.dumps(
        {
            "category": category,
            "method": method,
            "resource_family": resource_family,
            "status": int(status),
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    with LOCK, AUDIT.open("a", encoding="utf-8") as stream:
        stream.write(row + "\n")


class Handler(BaseHTTPRequestHandler):
    server_version = "VerboFlexPhase3Mock/1"
    sys_version = ""

    def log_message(self, _format, *_args):
        return

    def reply(self, status, payload, *, media_type="application/json"):
        body = (
            json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
            if media_type == "application/json"
            else payload
        )
        self.send_response(status)
        self.send_header("Content-Type", media_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-OAuth-Scopes", SCOPE)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def authorized(self):
        if self.headers.get("Authorization") == f"Bearer {ACCESS_TOKEN}":
            return True
        self.reply(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
        return False

    def do_POST(self):  # noqa: N802
        parsed = urlsplit(self.path)
        if parsed.path != "/site/oauth2/access_token":
            record(
                category="resource",
                method="POST",
                resource_family="forbidden-mutation",
                status=HTTPStatus.METHOD_NOT_ALLOWED,
            )
            self.reply(HTTPStatus.METHOD_NOT_ALLOWED, {"error": "read_only"})
            return
        expected = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
        length = int(self.headers.get("Content-Length", "0"))
        form = parse_qs(self.rfile.read(length).decode("ascii"), strict_parsing=True)
        valid = (
            self.headers.get("Authorization") == f"Basic {expected}"
            and form.get("grant_type") == ["client_credentials"]
            and form.get("scope") == ["pullrequest:write"]
        )
        status = HTTPStatus.OK if valid else HTTPStatus.UNAUTHORIZED
        record(
            category="oauth-token-exchange",
            method="POST",
            resource_family="oauth-token",
            status=status,
        )
        if not valid:
            self.reply(status, {"error": "invalid_client"})
            return
        self.reply(
            status,
            {
                "access_token": ACCESS_TOKEN,
                "expires_in": 3600,
                "scope": SCOPE,
                "token_type": "bearer",
            },
        )

    def do_GET(self):  # noqa: N802
        parsed = urlsplit(self.path)
        if parsed.path == "/_health":
            self.reply(HTTPStatus.OK, {"status": "ok"})
            return
        parts = parsed.path.removeprefix("/2.0/repositories/").strip("/").split("/")
        if not parsed.path.startswith("/2.0/repositories/") or len(parts) < 2:
            self.reply(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        if not self.authorized():
            return
        workspace, slug, *resource = (unquote(part) for part in parts)
        family = self.family(resource)
        fault = state().get("faults", {}).get(slug)
        fault_status = {
            "permission_denied": HTTPStatus.FORBIDDEN,
            "rate_limited": HTTPStatus.TOO_MANY_REQUESTS,
            "not_found": HTTPStatus.NOT_FOUND,
            "timeout": HTTPStatus.GATEWAY_TIMEOUT,
            "unavailable": HTTPStatus.SERVICE_UNAVAILABLE,
        }.get(fault)
        if fault == "block":
            BLOCK_STARTED.touch(mode=0o600, exist_ok=True)
            deadline = time.monotonic() + 60
            while state().get("faults", {}).get(slug) == "block" and time.monotonic() < deadline:
                time.sleep(0.05)
            fault_status = HTTPStatus.GATEWAY_TIMEOUT
        if fault_status is not None:
            record(category="resource", method="GET", resource_family=family, status=fault_status)
            self.reply(fault_status, {"error": "bounded_failure"})
            return
        record(category="resource", method="GET", resource_family=family, status=HTTPStatus.OK)
        self.repository_read(workspace, slug, resource, parse_qs(parsed.query))

    def do_PUT(self):  # noqa: N802
        self.reject_mutation()

    def do_PATCH(self):  # noqa: N802
        self.reject_mutation()

    def do_DELETE(self):  # noqa: N802
        self.reject_mutation()

    def reject_mutation(self):
        record(
            category="resource",
            method=self.command,
            resource_family="forbidden-mutation",
            status=HTTPStatus.METHOD_NOT_ALLOWED,
        )
        self.reply(HTTPStatus.METHOD_NOT_ALLOWED, {"error": "read_only"})

    @staticmethod
    def family(resource):
        if resource[:2] == ["refs", "branches"]:
            return "branch-read"
        if resource[:1] == ["commits"]:
            return "commit-ancestry"
        if resource[:1] == ["diffstat"]:
            return "commit-diffstat"
        if resource[:1] == ["src"]:
            return "source-read"
        return "repository-metadata"

    def repository_read(self, workspace, slug, resource, query):
        current = state()
        head = current["heads"].get(slug)
        if head is None:
            self.reply(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        base = f"https://api.bitbucket.org/2.0/repositories/{workspace}/{slug}"
        if not resource:
            self.reply(HTTPStatus.OK, {"full_name": f"{workspace}/{slug}", "scm": "git"})
            return
        if resource[:2] == ["refs", "branches"]:
            branch = "/".join(resource[2:])
            if branch != "main":
                self.reply(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                return
            self.reply(HTTPStatus.OK, {"name": "main", "target": {"hash": head}})
            return
        if resource[:1] == ["commits"] and len(resource) == 2:
            proposed = resource[1]
            values = [{"hash": proposed}]
            if proposed == "2" * 40:
                values.append({"hash": "1" * 40})
            self.reply(HTTPStatus.OK, {"values": values})
            return
        if resource[:1] == ["diffstat"] and len(resource) == 2:
            proposed = resource[1].split("..", 1)[0]
            values = [] if proposed == "4" * 40 else [
                {"status": "added", "old": None, "new": {"type": "commit_file", "path": "locales/added.json"}},
                {"status": "modified", "old": {"type": "commit_file", "path": "locales/messages.json"}, "new": {"type": "commit_file", "path": "locales/messages.json"}},
                {"status": "removed", "old": {"type": "commit_file", "path": "locales/removed.json"}, "new": None},
            ]
            self.reply(HTTPStatus.OK, {"values": values})
            return
        if resource[:1] == ["src"] and len(resource) >= 2:
            commit = resource[1]
            path = "/".join(resource[2:]).strip("/")
            if commit not in {"1" * 40, "2" * 40, "3" * 40, "4" * 40}:
                self.reply(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                return
            source_path = f"locales/{slug}.json"
            content = json.dumps({"hello": f"phase3-{slug}-{commit[0]}"}, separators=(",", ":")).encode()
            if "pagelen" in query:
                self.reply(
                    HTTPStatus.OK,
                    {"values": [{"path": source_path, "size": len(content), "type": "commit_file"}]},
                )
            elif path == source_path:
                self.reply(HTTPStatus.OK, content, media_type="application/octet-stream")
            else:
                self.reply(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        self.reply(HTTPStatus.NOT_FOUND, {"error": "not_found"})


def main():
    server = ThreadingHTTPServer(("0.0.0.0", 443), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(os.environ["MOCK_TLS_CERT"], os.environ["MOCK_TLS_KEY"])
    server.socket = context.wrap_socket(server.socket, server_side=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
PY
  chmod 600 "$SMOKE_PROVIDER_SCRIPT"
}

make_tls_material() {
  local config="$SMOKE_RUNTIME_DIR/openssl.cnf"
  printf '%s\n' \
    '[req]' \
    'distinguished_name = dn' \
    'x509_extensions = v3_ca' \
    'prompt = no' \
    '[dn]' \
    'CN = VerboFlex Phase 3 Smoke CA' \
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
  local backend_port frontend_port postgres_port suffix
  suffix="$$-$(date +%s)"
  SMOKE_PROJECT="verboflex_phase03_14_${suffix//-/_}"
  SMOKE_RUNTIME_DIR=$(mktemp -d /tmp/verboflex-phase03-14.XXXXXX)
  SMOKE_ENV_FILE="$SMOKE_RUNTIME_DIR/owner-only.env"
  SMOKE_OVERRIDE_FILE="$SMOKE_RUNTIME_DIR/mock-provider.yml"
  SMOKE_PROVIDER_SCRIPT="$SMOKE_RUNTIME_DIR/phase3_mock_provider.py"
  SMOKE_PROVIDER_CONTROL_FILE="$SMOKE_RUNTIME_DIR/provider-control.json"
  SMOKE_PROVIDER_AUDIT_FILE="$SMOKE_RUNTIME_DIR/provider-audit.jsonl"
  SMOKE_PROVIDER_BLOCK_STARTED_FILE="$SMOKE_RUNTIME_DIR/provider-block-started"
  SMOKE_IMAGE_TAG="phase03-14-$suffix"
  chmod 700 "$SMOKE_RUNTIME_DIR"
  backend_port=$(random_port)
  frontend_port=$(random_port)
  while [ "$frontend_port" = "$backend_port" ]; do frontend_port=$(random_port); done
  postgres_port=$(random_port)
  while [ "$postgres_port" = "$backend_port" ] || [ "$postgres_port" = "$frontend_port" ]; do
    postgres_port=$(random_port)
  done
  SMOKE_BACKEND_URL="http://localhost:$backend_port"
  SMOKE_FRONTEND_URL="http://localhost:$frontend_port"
  SMOKE_POSTGRES_PORT="$postgres_port"
  SMOKE_CLIENT_SECRET="phase3-client-$(openssl rand -hex 24)"
  SMOKE_POSTGRES_PASSWORD="phase3-postgres-$(openssl rand -hex 24)"
  SMOKE_JWT_SECRET_KEY="phase3-jwt-$(openssl rand -hex 32)"
  SMOKE_ACCESS_TOKEN="phase3-provider-$(openssl rand -hex 24)"
  SMOKE_KEYRING=$(
    cd "$BACKEND_ROOT"
    uv run python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
  )
  printf '%s\n' \
    "VERBOFLEX_BACKEND_PORT=$backend_port" \
    "VERBOFLEX_FRONTEND_PORT=$frontend_port" \
    "VERBOFLEX_IMAGE_TAG=$SMOKE_IMAGE_TAG" \
    "VITE_API_BASE_URL=$SMOKE_BACKEND_URL" \
    'VERBOFLEX_BITBUCKET_OAUTH_CLIENT_ID=phase3-smoke-consumer' \
    "VERBOFLEX_BITBUCKET_OAUTH_CLIENT_SECRET=$SMOKE_CLIENT_SECRET" \
    "VERBOFLEX_BITBUCKET_TOKEN_ENCRYPTION_KEYRING=$SMOKE_KEYRING" \
    "VERBOFLEX_POSTGRES_PASSWORD=$SMOKE_POSTGRES_PASSWORD" \
    "VERBOFLEX_JWT_SECRET_KEY=$SMOKE_JWT_SECRET_KEY" \
    "PHASE3_RUNTIME_DIR=$SMOKE_RUNTIME_DIR" \
    "PHASE3_FRONTEND_ORIGIN=$SMOKE_FRONTEND_URL" \
    "PHASE3_POSTGRES_PORT=$SMOKE_POSTGRES_PORT" \
    "MOCK_ACCESS_TOKEN=$SMOKE_ACCESS_TOKEN" \
    'VERBOFLEX_IMPORT_SOFT_TIME_LIMIT_SECONDS=8' \
    'VERBOFLEX_IMPORT_HARD_TIME_LIMIT_SECONDS=10' \
    'VERBOFLEX_IMPORT_WATCHDOG_GRACE_SECONDS=4' \
    'VERBOFLEX_IMPORT_WATCHDOG_INTERVAL_SECONDS=2' >"$SMOKE_ENV_FILE"
  chmod 600 "$SMOKE_ENV_FILE"
  printf '%s' '{"faults":{},"heads":{"phase3-direct":"1111111111111111111111111111111111111111","phase3-keys":"1111111111111111111111111111111111111111","phase3-translations":"1111111111111111111111111111111111111111","phase3-zero-delta":"1111111111111111111111111111111111111111"}}' \
    >"$SMOKE_PROVIDER_CONTROL_FILE"
  : >"$SMOKE_PROVIDER_AUDIT_FILE"
  chmod 600 "$SMOKE_PROVIDER_CONTROL_FILE" "$SMOKE_PROVIDER_AUDIT_FILE"
  write_mock_provider
  make_tls_material
}

configure_compose() {
  cat >"$SMOKE_OVERRIDE_FILE" <<'YAML'
services:
  postgres:
    ports:
      - "127.0.0.1:${PHASE3_POSTGRES_PORT}:5432"
  mock-bitbucket:
    image: python:3.14-slim
    environment:
      MOCK_ACCESS_TOKEN: ${MOCK_ACCESS_TOKEN}
      MOCK_AUDIT_FILE: /run/phase3/provider-audit.jsonl
      MOCK_BLOCK_STARTED_FILE: /run/phase3/provider-block-started
      MOCK_CLIENT_ID: ${VERBOFLEX_BITBUCKET_OAUTH_CLIENT_ID}
      MOCK_CLIENT_SECRET: ${VERBOFLEX_BITBUCKET_OAUTH_CLIENT_SECRET}
      MOCK_CONTROL_FILE: /run/phase3/provider-control.json
      MOCK_TLS_CERT: /run/phase3/server.pem
      MOCK_TLS_KEY: /run/phase3/server.key
    command: ["python", "/run/phase3/phase3_mock_provider.py"]
    volumes:
      - ${PHASE3_RUNTIME_DIR}:/run/phase3
    networks:
      default:
        aliases: [bitbucket.org, api.bitbucket.org]
  backend:
    environment:
      VERBOFLEX_CORS_ORIGINS: '["${PHASE3_FRONTEND_ORIGIN}"]'
      VERBOFLEX_IMPORT_SOFT_TIME_LIMIT_SECONDS: ${VERBOFLEX_IMPORT_SOFT_TIME_LIMIT_SECONDS}
      VERBOFLEX_IMPORT_HARD_TIME_LIMIT_SECONDS: ${VERBOFLEX_IMPORT_HARD_TIME_LIMIT_SECONDS}
      VERBOFLEX_IMPORT_WATCHDOG_GRACE_SECONDS: ${VERBOFLEX_IMPORT_WATCHDOG_GRACE_SECONDS}
      VERBOFLEX_IMPORT_WATCHDOG_INTERVAL_SECONDS: ${VERBOFLEX_IMPORT_WATCHDOG_INTERVAL_SECONDS}
      SSL_CERT_FILE: /run/phase3/ca.pem
    volumes:
      - ${PHASE3_RUNTIME_DIR}/ca.pem:/run/phase3/ca.pem:ro
      - ${PHASE3_RUNTIME_DIR}/ca.pem:/opt/venv/lib/python3.14/site-packages/certifi/cacert.pem:ro
    depends_on:
      mock-bitbucket:
        condition: service_started
  worker:
    environment:
      VERBOFLEX_IMPORT_SOFT_TIME_LIMIT_SECONDS: ${VERBOFLEX_IMPORT_SOFT_TIME_LIMIT_SECONDS}
      VERBOFLEX_IMPORT_HARD_TIME_LIMIT_SECONDS: ${VERBOFLEX_IMPORT_HARD_TIME_LIMIT_SECONDS}
      VERBOFLEX_IMPORT_WATCHDOG_GRACE_SECONDS: ${VERBOFLEX_IMPORT_WATCHDOG_GRACE_SECONDS}
      VERBOFLEX_IMPORT_WATCHDOG_INTERVAL_SECONDS: ${VERBOFLEX_IMPORT_WATCHDOG_INTERVAL_SECONDS}
      SSL_CERT_FILE: /run/phase3/ca.pem
    volumes:
      - ${PHASE3_RUNTIME_DIR}/ca.pem:/run/phase3/ca.pem:ro
      - ${PHASE3_RUNTIME_DIR}/ca.pem:/opt/venv/lib/python3.14/site-packages/certifi/cacert.pem:ro
    depends_on:
      mock-bitbucket:
        condition: service_started
  scheduler:
    environment:
      VERBOFLEX_IMPORT_SOFT_TIME_LIMIT_SECONDS: ${VERBOFLEX_IMPORT_SOFT_TIME_LIMIT_SECONDS}
      VERBOFLEX_IMPORT_HARD_TIME_LIMIT_SECONDS: ${VERBOFLEX_IMPORT_HARD_TIME_LIMIT_SECONDS}
      VERBOFLEX_IMPORT_WATCHDOG_GRACE_SECONDS: ${VERBOFLEX_IMPORT_WATCHDOG_GRACE_SECONDS}
      VERBOFLEX_IMPORT_WATCHDOG_INTERVAL_SECONDS: ${VERBOFLEX_IMPORT_WATCHDOG_INTERVAL_SECONDS}
      SSL_CERT_FILE: /run/phase3/ca.pem
    volumes:
      - ${PHASE3_RUNTIME_DIR}/ca.pem:/run/phase3/ca.pem:ro
      - ${PHASE3_RUNTIME_DIR}/ca.pem:/opt/venv/lib/python3.14/site-packages/certifi/cacert.pem:ro
    depends_on:
      mock-bitbucket:
        condition: service_started
YAML
  chmod 600 "$SMOKE_OVERRIDE_FILE"
}

preflight() {
  command -v docker >/dev/null 2>&1 || die "Docker is unavailable"
  command -v openssl >/dev/null 2>&1 || die "OpenSSL is unavailable"
  command -v curl >/dev/null 2>&1 || die "curl is unavailable"
  docker info >/dev/null 2>&1 || die "Docker daemon is unavailable"
  "$BACKEND_ROOT/.venv/bin/python" -m py_compile "$SMOKE_PROVIDER_SCRIPT"
  compose config --quiet >/dev/null
  (
    cd "$FRONTEND_ROOT"
    npm run api:check >/dev/null
  )
  printf 'phase3 smoke preflight: PASS\n'
}

prepare_stack() {
  local start_log="$SMOKE_RUNTIME_DIR/compose-start.log" rc
  compose build backend frontend >/dev/null
  compose up -d postgres redis mock-bitbucket >/dev/null
  compose run --rm -T backend alembic upgrade head >/dev/null
  compose run --rm -T backend alembic downgrade 0011_active_revision_revalidations >/dev/null
  compose run --rm -T backend alembic upgrade head >/dev/null
  set +e
  compose up -d backend worker scheduler frontend >"$start_log" 2>&1
  rc=$?
  set -e
  if [ "$rc" -ne 0 ]; then
    grep -Fqi 'address already in use' "$start_log" && return 75
    sed -n '1,160p' "$start_log" >&2
    return "$rc"
  fi
  wait_for_url "$SMOKE_BACKEND_URL/api/v1/health" 200 backend
  wait_for_url "$SMOKE_FRONTEND_URL/login" 200 frontend
  wait_for_worker
  wait_for_scheduler
  for service in postgres redis backend worker scheduler frontend mock-bitbucket; do
    [ "$(compose ps --status running -q "$service" | wc -l | tr -d ' ')" = "1" ] \
      || die "$service did not remain running"
  done
}

run_migration_contract() {
  (
    cd "$BACKEND_ROOT"
    VERBOFLEX_TEST_POSTGRES_ADMIN_URL="postgresql://verboflex@localhost:$SMOKE_POSTGRES_PORT/postgres" \
      uv run pytest -q tests/integration/test_migrations.py \
        -k 'complete_schema_upgrades_downgrades_and_upgrades_reversibly or phase3_deployment_cycle_removes_and_recreates_every_import_table'
  )
  printf 'phase3 migration contract: PASS (head -> pre-import -> head)\n'
}

run_browser_journey() {
  local backend_container worker_container
  backend_container=$(compose ps -q backend)
  worker_container=$(compose ps -q worker)
  [ -n "$backend_container" ] && [ -n "$worker_container" ] \
    || die "backend and worker containers are required for Playwright"
  (
    cd "$FRONTEND_ROOT"
    PLAYWRIGHT_BASE_URL="$SMOKE_FRONTEND_URL" \
    PLAYWRIGHT_OUTPUT_DIR="$SMOKE_RUNTIME_DIR/playwright" \
    E2E_BACKEND_CONTAINER="$backend_container" \
    E2E_PHASE3_WORKER_CONTAINER="$worker_container" \
    E2E_PHASE3_PROVIDER_CONTROL_FILE="$SMOKE_PROVIDER_CONTROL_FILE" \
    E2E_PHASE3_PROVIDER_AUDIT_FILE="$SMOKE_PROVIDER_AUDIT_FILE" \
    E2E_PHASE3_PROVIDER_BLOCK_STARTED_FILE="$SMOKE_PROVIDER_BLOCK_STARTED_FILE" \
    E2E_PHASE3_DISPOSABLE_STACK=1 \
    E2E_EMAIL=phase3-loader@example.com \
    E2E_TEMP_PASSWORD='Phase3LoaderTemporary1!' \
    E2E_PASSWORD='Phase3LoaderOrdinary1!' \
      npm run e2e -- --grep 'deployment-like Phase 3 import, recovery, watchdog, and rewrite journeys'
  )
}

verify_provider_audit() {
  "$BACKEND_ROOT/.venv/bin/python" - "$SMOKE_PROVIDER_AUDIT_FILE" <<'PY'
import json
import sys

rows = [json.loads(line) for line in open(sys.argv[1], encoding="utf-8") if line.strip()]
assert rows
assert all(set(row) == {"category", "method", "resource_family", "status"} for row in rows)
oauth = [row for row in rows if row["category"] == "oauth-token-exchange"]
resources = [row for row in rows if row["category"] == "resource"]
assert oauth and all(row["method"] == "POST" for row in oauth)
assert resources and all(row["method"] == "GET" for row in resources)
assert not [
    row for row in resources
    if row["resource_family"] in {
        "branch-create",
        "source-commit",
        "pull-request-create",
        "forbidden-mutation",
    }
]
for status in (403, 404, 429):
    assert len([row for row in resources if row["status"] == status]) == 1
assert len([row for row in resources if row["status"] == 504]) >= 1
print(
    "phase3 provider audit: PASS "
    f"(oauth_post={len(oauth)}, resource_get={len(resources)}, resource_mutations=0)"
)
PY
}

verify_redis_boundary() {
  local secret
  for secret in "$SMOKE_CLIENT_SECRET" "$SMOKE_POSTGRES_PASSWORD" \
    "$SMOKE_JWT_SECRET_KEY" "$SMOKE_ACCESS_TOKEN" "$SMOKE_KEYRING" \
    'phase3-direct-1'; do
    compose exec -T -e PHASE3_FORBIDDEN_VALUE="$secret" backend python - <<'PY'
import os
from redis import Redis
from verboflex.core.config import get_settings

needle = os.environ["PHASE3_FORBIDDEN_VALUE"].encode()
client = Redis.from_url(str(get_settings().redis_url), decode_responses=False)
try:
    for key in client.scan_iter(match="*"):
        kind = client.type(key)
        values = []
        if kind == b"string":
            values = [client.get(key)]
        elif kind == b"list":
            values = client.lrange(key, 0, -1)
        elif kind == b"set":
            values = list(client.smembers(key))
        elif kind == b"zset":
            values = [value for value, _score in client.zrange(key, 0, -1, withscores=True)]
        elif kind == b"hash":
            values = list(client.hgetall(key).values())
        assert all(value is None or needle not in value for value in values)
finally:
    client.close()
PY
  done
  printf 'phase3 Redis boundary: PASS (UUID-only work, no credentials or source bytes)\n'
}

verify_no_sensitive_surfaces() {
  local logs="$SMOKE_RUNTIME_DIR/compose.log" secret surface
  compose logs --no-color >"$logs" 2>"$SMOKE_RUNTIME_DIR/compose-errors.log"
  for secret in "$SMOKE_CLIENT_SECRET" "$SMOKE_POSTGRES_PASSWORD" \
    "$SMOKE_JWT_SECRET_KEY" "$SMOKE_ACCESS_TOKEN" "$SMOKE_KEYRING"; do
    for surface in "$logs" "$SMOKE_PROVIDER_AUDIT_FILE" \
      "$SMOKE_RUNTIME_DIR/compose-errors.log"; do
      if grep -Fq -- "$secret" "$surface"; then
        die "captured logs or audit exposed seeded secret material"
      fi
    done
    if [ -d "$SMOKE_RUNTIME_DIR/playwright" ] \
      && grep -R -a -Fq -- "$secret" "$SMOKE_RUNTIME_DIR/playwright"; then
      die "Playwright evidence exposed seeded secret material"
    fi
  done
  for surface in "$logs" "$SMOKE_PROVIDER_AUDIT_FILE" \
    "$SMOKE_RUNTIME_DIR/compose-errors.log"; do
    if grep -Eiq \
      '(authorization:[[:space:]]*(bearer|basic)|client_secret[=:][^[:space:]]|access_token[=:][^[:space:]]|refresh_token[=:][^[:space:]]|gAAAAA[A-Za-z0-9_-]+)' \
      "$surface"; then
      die "captured logs or audit contain credential-shaped material"
    fi
  done
  printf 'phase3 sensitive-surface scan: PASS\n'
}

run_mock_once() {
  local rc
  trap cleanup EXIT INT TERM
  initialize_runtime
  configure_compose
  preflight
  set +e
  prepare_stack
  rc=$?
  set -e
  [ "$rc" -eq 0 ] || return "$rc"
  run_migration_contract
  run_browser_journey
  verify_provider_audit
  verify_redis_boundary
  verify_no_sensitive_surfaces
  cleanup
  trap - EXIT INT TERM
  printf 'phase3 deployment-like mock smoke: PASS\n'
}

run_mock_with_port_retry() {
  local attempt rc
  for attempt in 1 2 3; do
    set +e
    "$SCRIPT_DIR/phase3_smoke.sh" --mock-provider-once
    rc=$?
    set -e
    if [ "$rc" -eq 0 ]; then return 0; fi
    if [ "$rc" -ne 75 ]; then return "$rc"; fi
    [ "$attempt" -ge 3 ] || printf \
      'phase3 smoke: address already in use, retrying isolated attempt %s/3\n' \
      "$((attempt + 1))" >&2
  done
  die "host-port binding remained unavailable after three isolated attempts"
}

case "${1:-}" in
  --mock-provider) run_mock_with_port_retry ;;
  --mock-provider-once) run_mock_once ;;
  *) die "usage: tools/phase3_smoke.sh --mock-provider" ;;
esac

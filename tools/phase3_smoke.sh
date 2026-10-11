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
SMOKE_LIVE_PROXY_SCRIPT=""
SMOKE_LIVE_DRIVER_SCRIPT=""
SMOKE_LIVE_RESULT_FILE=""
SMOKE_LIVE_BRANCH=""
SMOKE_LIVE_ADMIN_EMAIL=""
SMOKE_LIVE_ADMIN_PASSWORD=""
SMOKE_LIVE_ADMIN_NEW_PASSWORD=""
SMOKE_LIVE_API_IP=""
SMOKE_LIVE_TOKEN_IP=""

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
  # The public CA is mounted into non-root app containers. Linux preserves the
  # host mode on bind mounts; private keys and the enclosing directory stay private.
  chmod 644 "$SMOKE_RUNTIME_DIR/ca.pem"
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
    "PHASE3_HOST_UID=$(id -u)" \
    "PHASE3_HOST_GID=$(id -g)" \
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
    user: "${PHASE3_HOST_UID}:${PHASE3_HOST_GID}"
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

write_live_audit_proxy() {
  cat >"$SMOKE_LIVE_PROXY_SCRIPT" <<'PY'
#!/usr/bin/env python3
from __future__ import annotations

import http.client
import json
import os
import socket
import ssl
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

AUDIT = Path(os.environ["LIVE_AUDIT_FILE"])
UPSTREAM = {
    "api.bitbucket.org": os.environ["LIVE_API_IP"],
    "bitbucket.org": os.environ["LIVE_TOKEN_IP"],
}
LOCK = threading.Lock()
MAX_REQUEST_BYTES = 1_048_576
MAX_RESPONSE_BYTES = 2_097_152
HOP_HEADERS = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailer", "transfer-encoding", "upgrade",
}


class DirectHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, address: str) -> None:
        super().__init__(host, timeout=25, context=ssl.create_default_context())
        self._address = address

    def connect(self) -> None:
        raw = socket.create_connection((self._address, 443), self.timeout)
        self.sock = self._context.wrap_socket(raw, server_hostname=self.host)


def family(path: str) -> str:
    segments = urlsplit(path).path.strip("/").split("/")
    resource = segments[4:] if len(segments) >= 4 else []
    if resource[:2] == ["refs", "branches"]:
        return "branch-read"
    if resource[:1] == ["commits"]:
        return "commit-ancestry"
    if resource[:1] == ["diffstat"]:
        return "commit-diffstat"
    if resource[:1] == ["src"]:
        return "source-read"
    return "repository-metadata"


def record(category: str, method: str, resource_family: str, status: int) -> None:
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
    server_version = "VerboFlexLiveAudit/1"
    sys_version = ""

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def do_GET(self) -> None:  # noqa: N802
        self.forward()

    def do_POST(self) -> None:  # noqa: N802
        self.forward()

    def do_PUT(self) -> None:  # noqa: N802
        self.forward()

    def do_PATCH(self) -> None:  # noqa: N802
        self.forward()

    def do_DELETE(self) -> None:  # noqa: N802
        self.forward()

    def do_HEAD(self) -> None:  # noqa: N802
        self.forward()

    def reject(self, category: str, resource_family: str) -> None:
        record(category, self.command, resource_family, HTTPStatus.METHOD_NOT_ALLOWED)
        self.send_response(HTTPStatus.METHOD_NOT_ALLOWED)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def forward(self) -> None:
        host = self.headers.get("Host", "").split(":", 1)[0].casefold()
        path = urlsplit(self.path).path
        if host == "api.bitbucket.org":
            category = "resource"
            resource_family = family(self.path)
            if self.command != "GET":
                self.reject(category, "forbidden-mutation")
                return
        elif host == "bitbucket.org" and path == "/site/oauth2/access_token":
            category = "oauth-token-exchange"
            resource_family = "oauth-token"
            if self.command != "POST":
                self.reject(category, resource_family)
                return
        else:
            self.send_response(HTTPStatus.BAD_GATEWAY)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", "0"))
        if length < 0 or length > MAX_REQUEST_BYTES:
            self.reject(category, resource_family)
            return
        body = self.rfile.read(length) if length else None
        headers = {
            name: value
            for name, value in self.headers.items()
            if name.casefold() not in HOP_HEADERS | {"host", "content-length"}
        }
        headers["Host"] = host
        if body is not None:
            headers["Content-Length"] = str(len(body))

        connection = DirectHTTPSConnection(host, UPSTREAM[host])
        try:
            connection.request(self.command, self.path, body=body, headers=headers)
            response = connection.getresponse()
            response_body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(response_body) > MAX_RESPONSE_BYTES:
                raise OSError("bounded upstream response exceeded")
            record(category, self.command, resource_family, response.status)
            self.send_response(response.status)
            for name, value in response.getheaders():
                if name.casefold() not in HOP_HEADERS | {"content-length"}:
                    self.send_header(name, value)
            self.send_header("Content-Length", str(len(response_body)))
            self.end_headers()
            self.wfile.write(response_body)
        except (OSError, ssl.SSLError, http.client.HTTPException):
            record(category, self.command, resource_family, HTTPStatus.BAD_GATEWAY)
            self.send_response(HTTPStatus.BAD_GATEWAY)
            self.send_header("Content-Length", "0")
            self.end_headers()
        finally:
            connection.close()


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", 443), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(os.environ["LIVE_TLS_CERT"], os.environ["LIVE_TLS_KEY"])
    server.socket = context.wrap_socket(server.socket, server_side=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
PY
  chmod 600 "$SMOKE_LIVE_PROXY_SCRIPT"
}

write_live_api_driver() {
  cat >"$SMOKE_LIVE_DRIVER_SCRIPT" <<'PY'
#!/usr/bin/env python3
"""Drive one live provider read through authenticated VerboFlex APIs only."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import stat
import sys
import time
from http import HTTPStatus
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

MAX_ENV_BYTES = 65_536
MAX_RESPONSE_BYTES = 1_048_576
TIMEOUT_SECONDS = 20
POLL_SECONDS = 120
ENV_NAME = re.compile(r"[A-Z][A-Z0-9_]*")
IDENTITY_PART = re.compile(r"[A-Za-z0-9._-]+")
STAGE = "configuration"


class Rejected(RuntimeError):
    pass


class RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, *_args: object, **_kwargs: object) -> None:
        return None


def reject() -> None:
    raise Rejected(f"live provider read rejected during {STAGE}")


def dotenv(path: Path) -> dict[str, str]:
    try:
        metadata = path.lstat()
    except OSError:
        reject()
    if (
        not stat.S_ISREG(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o600
        or metadata.st_uid != os.getuid()
        or metadata.st_size > MAX_ENV_BYTES
    ):
        reject()
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        reject()
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            reject()
        name, raw_value = line.split("=", 1)
        if ENV_NAME.fullmatch(name) is None or name in values:
            reject()
        value = raw_value.strip()
        if value[:1] in {"'", '"'}:
            try:
                value = ast.literal_eval(value)
            except (SyntaxError, ValueError):
                reject()
        if not isinstance(value, str) or not value:
            reject()
        values[name] = value
    return values


class LocalApi:
    def __init__(self, base_url: str) -> None:
        parsed = urlsplit(base_url)
        if (
            parsed.scheme != "http"
            or parsed.hostname not in {"127.0.0.1", "localhost"}
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            reject()
        self.base_url = base_url.rstrip("/")
        self.opener = build_opener(RejectRedirects())

    def request(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        payload: object | None = None,
        form: dict[str, str] | None = None,
        expected: int | tuple[int, ...] = HTTPStatus.OK,
    ) -> dict[str, object]:
        if not path.startswith("/api/v1/") or "://" in path:
            reject()
        headers = {"Accept": "application/json"}
        body = None
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        if payload is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(payload, separators=(",", ":")).encode()
        elif form is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            body = urlencode(form).encode()
        request = Request(self.base_url + path, data=body, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=TIMEOUT_SECONDS) as opened:
                status = opened.status
                response_body = opened.read(MAX_RESPONSE_BYTES + 1)
        except HTTPError as error:
            status = error.code
            response_body = error.read(MAX_RESPONSE_BYTES + 1)
        except (URLError, OSError, TimeoutError):
            reject()
        allowed = (expected,) if isinstance(expected, int) else expected
        if status not in allowed or len(response_body) > MAX_RESPONSE_BYTES:
            reject()
        if not response_body:
            return {}
        try:
            decoded = json.loads(response_body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            reject()
        if not isinstance(decoded, dict):
            reject()
        return decoded


def require_string(payload: dict[str, object], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value:
        reject()
    return value


def assert_connection(payload: dict[str, object], expected: str) -> None:
    if set(payload) != {
        "status", "scope_profile", "scope_label", "capability_profile",
        "connected_at", "expires_at", "revoked_at",
    }:
        reject()
    capabilities = payload.get("capability_profile")
    if not isinstance(capabilities, dict) or set(capabilities) != {
        "source_read", "source_write", "pull_request", "evaluated_at",
    }:
        reject()
    if payload.get("status") != expected:
        reject()
    if expected == "Connected" and (
        payload.get("scope_profile") != "repository_and_pull_request"
        or capabilities.get("source_read") != "ready"
        or capabilities.get("source_write") != "ready_for_later_phase"
        or capabilities.get("pull_request") != "ready_for_later_phase"
    ):
        reject()


def login(api: LocalApi, values: dict[str, str]) -> str:
    response = api.request(
        "POST",
        "/api/v1/auth/token",
        form={
            "username": values["PHASE3_LIVE_ADMIN_EMAIL"],
            "password": values["PHASE3_LIVE_ADMIN_PASSWORD"],
        },
    )
    token = require_string(response, "access_token")
    if response.get("must_change_password") is True:
        api.request(
            "POST",
            "/api/v1/auth/change-password",
            token=token,
            payload={
                "current_password": values["PHASE3_LIVE_ADMIN_PASSWORD"],
                "new_password": values["PHASE3_LIVE_ADMIN_NEW_PASSWORD"],
            },
            expected=HTTPStatus.NO_CONTENT,
        )
        response = api.request(
            "POST",
            "/api/v1/auth/token",
            form={
                "username": values["PHASE3_LIVE_ADMIN_EMAIL"],
                "password": values["PHASE3_LIVE_ADMIN_NEW_PASSWORD"],
            },
        )
        token = require_string(response, "access_token")
    return token


def poll(api: LocalApi, path: str, token: str, terminal: set[str]) -> dict[str, object]:
    deadline = time.monotonic() + POLL_SECONDS
    while time.monotonic() < deadline:
        response = api.request("GET", path, token=token)
        state = response.get("state")
        if state in terminal:
            return response
        time.sleep(1)
    reject()


def run(env_path: Path, result_path: Path) -> None:
    global STAGE
    values = dotenv(env_path)
    required = {
        "PHASE3_LIVE_BACKEND_URL", "PHASE3_LIVE_ADMIN_EMAIL",
        "PHASE3_LIVE_ADMIN_PASSWORD", "PHASE3_LIVE_ADMIN_NEW_PASSWORD",
        "VERBOFLEX_BITBUCKET_LIVE_WORKSPACE",
        "VERBOFLEX_BITBUCKET_LIVE_REPOSITORY", "PHASE3_LIVE_BRANCH",
        "PHASE3_LIVE_RUN_ID",
    }
    if required.difference(values):
        reject()
    workspace = values["VERBOFLEX_BITBUCKET_LIVE_WORKSPACE"]
    repository = values["VERBOFLEX_BITBUCKET_LIVE_REPOSITORY"]
    branch = values["PHASE3_LIVE_BRANCH"]
    if IDENTITY_PART.fullmatch(workspace) is None or IDENTITY_PART.fullmatch(repository) is None:
        reject()
    if not branch or len(branch) > 255 or any(part in {"", ".", ".."} for part in branch.split("/")):
        reject()

    started = time.monotonic()
    api = LocalApi(values["PHASE3_LIVE_BACKEND_URL"])
    token = ""
    connected = False
    completed: dict[str, object] | None = None
    try:
        STAGE = "administrator-login"
        token = login(api, values)
        STAGE = "connect"
        assert_connection(api.request("POST", "/api/v1/admin/bitbucket/connect", token=token), "Connected")
        connected = True
        STAGE = "reconnect"
        assert_connection(api.request("POST", "/api/v1/admin/bitbucket/reconnect", token=token), "Connected")

        STAGE = "repository-registration"
        registered = api.request(
            "POST",
            "/api/v1/admin/repositories",
            token=token,
            payload={
                "workspace": workspace,
                "repository_slug": repository,
                "descriptive_name": "Phase 3 live-read smoke",
            },
            expected=HTTPStatus.CREATED,
        )
        repository_id = require_string(registered, "id")
        STAGE = "branch-resolution"
        resolved = api.request(
            "GET",
            f"/api/v1/admin/repositories/{repository_id}/branch?{urlencode({'branch_name': branch})}",
            token=token,
        )
        commit_hash = require_string(resolved, "commit_hash")
        if resolved.get("name") != branch or re.fullmatch(r"[0-9a-fA-F]{40}", commit_hash) is None:
            reject()

        STAGE = "product-creation"
        product = api.request(
            "POST",
            "/api/v1/admin/products",
            token=token,
            payload={
                "name": f"Phase 3 live read {values['PHASE3_LIVE_RUN_ID']}",
                "description": "Disposable read-only provider verification",
            },
            expected=HTTPStatus.CREATED,
        )
        product_id = require_string(product, "id")
        candidate = product.get("candidate_revision")
        if not isinstance(candidate, dict):
            reject()
        candidate_id = require_string(candidate, "id")
        candidate_version = candidate.get("version")
        if not isinstance(candidate_version, int):
            reject()

        STAGE = "mapping-creation"
        mapping = api.request(
            "POST",
            f"/api/v1/admin/products/{product_id}/candidate/mappings",
            token=token,
            payload={
                "topology": "direct",
                "repository_id": repository_id,
                "source_branch": branch,
                "allowed_target_branches": [branch],
                "default_target_branch": branch,
                "expected_candidate_version": candidate_version,
            },
            expected=HTTPStatus.CREATED,
        )
        mapping_id = require_string(mapping, "id")
        mapping_version = mapping.get("candidate_version")
        if not isinstance(mapping_version, int):
            reject()

        STAGE = "preview-start"
        preview = api.request(
            "POST",
            f"/api/v1/admin/products/{product_id}/candidate/mappings/{mapping_id}/preview-jobs",
            token=token,
            payload={
                "expected_candidate_version": mapping_version,
                "commits": [{"role": "direct", "commit_hash": commit_hash}],
            },
            expected=HTTPStatus.ACCEPTED,
        )
        preview_id = require_string(preview, "id")
        STAGE = "preview-poll"
        preview = poll(
            api,
            f"/api/v1/admin/preview-jobs/{preview_id}",
            token,
            {"succeeded", "failed", "timed_out"},
        )
        if preview.get("state") != "succeeded" or preview.get("is_current") is not True:
            reject()
        preview_result = preview.get("result")
        if not isinstance(preview_result, dict):
            reject()
        layouts = preview_result.get("layout_candidates")
        if not isinstance(layouts, list) or not layouts or not isinstance(layouts[0], dict):
            reject()
        layout = layouts[0]

        STAGE = "preview-confirmation"
        api.request(
            "POST",
            f"/api/v1/admin/preview-jobs/{preview_id}/confirmation",
            token=token,
            payload={
                "preview_digest": require_string(preview_result, "digest"),
                "layout_candidate_id": require_string(layout, "id"),
                "layout_candidate_version": layout.get("version"),
            },
        )
        STAGE = "publication"
        api.request(
            "POST",
            f"/api/v1/admin/products/{product_id}/publish",
            token=token,
            payload={
                "candidate_revision_id": candidate_id,
                "expected_candidate_version": mapping_version,
            },
        )
        STAGE = "import-start"
        imported = api.request(
            "POST",
            f"/api/v1/admin/products/{product_id}/published/mappings/{mapping_id}/imports",
            token=token,
            expected=HTTPStatus.ACCEPTED,
        )
        import_id = require_string(imported, "id")
        STAGE = "import-poll"
        imported = poll(
            api,
            f"/api/v1/admin/products/{product_id}/imports/{import_id}",
            token,
            {"current", "review_required", "import_failed"},
        )
        baseline = imported.get("active_baseline")
        references = baseline.get("source_references") if isinstance(baseline, dict) else None
        if imported.get("state") != "current" or not isinstance(references, list) or not references:
            reject()
        reference_hashes = []
        for reference in references:
            if not isinstance(reference, dict) or reference.get("commit_hash") != commit_hash.casefold():
                reject()
            reference_hashes.append(require_string(reference, "sha256"))
        completed = {
            "readiness": "ready",
            "duration_ms": int((time.monotonic() - started) * 1000),
            "result_count": len(references),
            "repository_identity_sha256": hashlib.sha256(
                f"{workspace.casefold()}/{repository.casefold()}".encode()
            ).hexdigest(),
            "branch_identity_sha256": hashlib.sha256(branch.encode()).hexdigest(),
            "commit_identity_sha256": hashlib.sha256(commit_hash.casefold().encode()).hexdigest(),
            "result_identity_sha256": hashlib.sha256("".join(reference_hashes).encode()).hexdigest(),
        }
    finally:
        if token and connected:
            STAGE = "local-revoke"
            assert_connection(
                api.request("POST", "/api/v1/admin/bitbucket/revoke", token=token),
                "Disconnected",
            )

    if completed is None:
        reject()
    completed["final_local_revoke"] = "PASS"
    result_path.write_text(
        json.dumps(completed, separators=(",", ":"), sort_keys=True) + "\n",
        encoding="utf-8",
    )
    result_path.chmod(0o600)


def main() -> int:
    if len(sys.argv) != 3:
        print("phase3-live error: bounded local configuration required", file=sys.stderr)
        return 1
    try:
        run(Path(sys.argv[1]), Path(sys.argv[2]))
    except Exception as error:
        if isinstance(error, Rejected):
            print(f"phase3-live error: {error}", file=sys.stderr)
        else:
            print("phase3-live error: live provider read rejected", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
PY
  chmod 600 "$SMOKE_LIVE_DRIVER_SCRIPT"
}

live_configuration_ready() {
  local name
  for name in \
    VERBOFLEX_BITBUCKET_OAUTH_CLIENT_ID \
    VERBOFLEX_BITBUCKET_OAUTH_CLIENT_SECRET \
    VERBOFLEX_BITBUCKET_LIVE_WORKSPACE \
    VERBOFLEX_BITBUCKET_LIVE_REPOSITORY; do
    [ -n "${!name:-}" ] || return 1
  done
}

resolve_external_ipv4() {
  local host=$1
  "$BACKEND_ROOT/.venv/bin/python" - "$host" <<'PY'
import socket
import sys

addresses = sorted(
    {
        row[4][0]
        for row in socket.getaddrinfo(sys.argv[1], 443, socket.AF_INET, socket.SOCK_STREAM)
    }
)
if not addresses:
    raise SystemExit(1)
print(addresses[0])
PY
}

initialize_live_runtime() {
  local backend_port frontend_port postgres_port suffix
  suffix="$$-$(date +%s)"
  SMOKE_PROJECT="verboflex_phase03_14_live_${suffix//-/_}"
  SMOKE_RUNTIME_DIR=$(mktemp -d /tmp/verboflex-phase03-14-live.XXXXXX)
  SMOKE_ENV_FILE="$SMOKE_RUNTIME_DIR/owner-only.env"
  SMOKE_OVERRIDE_FILE="$SMOKE_RUNTIME_DIR/live-provider.yml"
  SMOKE_LIVE_PROXY_SCRIPT="$SMOKE_RUNTIME_DIR/live_audit_proxy.py"
  SMOKE_LIVE_DRIVER_SCRIPT="$SMOKE_RUNTIME_DIR/live_api_driver.py"
  SMOKE_PROVIDER_AUDIT_FILE="$SMOKE_RUNTIME_DIR/provider-audit.jsonl"
  SMOKE_LIVE_RESULT_FILE="$SMOKE_RUNTIME_DIR/live-result.json"
  SMOKE_IMAGE_TAG="phase03-14-live-$suffix"
  chmod 700 "$SMOKE_RUNTIME_DIR"

  case "${VERBOFLEX_BITBUCKET_OAUTH_CLIENT_ID}${VERBOFLEX_BITBUCKET_OAUTH_CLIENT_SECRET}" in
    *$'\n'*|*$'\r'*) die "live OAuth configuration is invalid" ;;
  esac
  case "${VERBOFLEX_BITBUCKET_LIVE_WORKSPACE}/${VERBOFLEX_BITBUCKET_LIVE_REPOSITORY}" in
    *[!A-Za-z0-9._/-]*) die "live repository identity is invalid" ;;
  esac
  SMOKE_LIVE_BRANCH="${VERBOFLEX_BITBUCKET_LIVE_BRANCH:-main}"
  case "$SMOKE_LIVE_BRANCH" in
    ""|*\\*|*$'\n'*|*$'\r'*|/*|*/../*|../*|*/..|.|..) die "live branch identity is invalid" ;;
  esac

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
  SMOKE_CLIENT_SECRET="$VERBOFLEX_BITBUCKET_OAUTH_CLIENT_SECRET"
  SMOKE_POSTGRES_PASSWORD="phase3-live-postgres-$(openssl rand -hex 24)"
  SMOKE_JWT_SECRET_KEY="phase3-live-jwt-$(openssl rand -hex 32)"
  SMOKE_KEYRING=$(
    cd "$BACKEND_ROOT"
    uv run python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
  )
  SMOKE_LIVE_ADMIN_EMAIL="phase3-live-$suffix@example.com"
  SMOKE_LIVE_ADMIN_PASSWORD="Phase3LiveTemporary$(openssl rand -hex 12)!"
  SMOKE_LIVE_ADMIN_NEW_PASSWORD="Phase3LiveOrdinary$(openssl rand -hex 12)!"
  SMOKE_LIVE_API_IP=$(resolve_external_ipv4 api.bitbucket.org) \
    || die "live Bitbucket API address is unavailable"
  SMOKE_LIVE_TOKEN_IP=$(resolve_external_ipv4 bitbucket.org) \
    || die "live Bitbucket token address is unavailable"

  printf '%s\n' \
    "VERBOFLEX_BACKEND_PORT=$backend_port" \
    "VERBOFLEX_FRONTEND_PORT=$frontend_port" \
    "VERBOFLEX_IMAGE_TAG=$SMOKE_IMAGE_TAG" \
    "VITE_API_BASE_URL=$SMOKE_BACKEND_URL" \
    "VERBOFLEX_BITBUCKET_OAUTH_CLIENT_ID=$VERBOFLEX_BITBUCKET_OAUTH_CLIENT_ID" \
    "VERBOFLEX_BITBUCKET_OAUTH_CLIENT_SECRET=$SMOKE_CLIENT_SECRET" \
    "VERBOFLEX_BITBUCKET_TOKEN_ENCRYPTION_KEYRING=$SMOKE_KEYRING" \
    "VERBOFLEX_POSTGRES_PASSWORD=$SMOKE_POSTGRES_PASSWORD" \
    "VERBOFLEX_JWT_SECRET_KEY=$SMOKE_JWT_SECRET_KEY" \
    "PHASE3_RUNTIME_DIR=$SMOKE_RUNTIME_DIR" \
    "PHASE3_FRONTEND_ORIGIN=$SMOKE_FRONTEND_URL" \
    "PHASE3_POSTGRES_PORT=$SMOKE_POSTGRES_PORT" \
    "PHASE3_LIVE_BACKEND_URL=$SMOKE_BACKEND_URL" \
    "PHASE3_LIVE_ADMIN_EMAIL=$SMOKE_LIVE_ADMIN_EMAIL" \
    "PHASE3_LIVE_ADMIN_PASSWORD=$SMOKE_LIVE_ADMIN_PASSWORD" \
    "PHASE3_LIVE_ADMIN_NEW_PASSWORD=$SMOKE_LIVE_ADMIN_NEW_PASSWORD" \
    "PHASE3_LIVE_BRANCH=$SMOKE_LIVE_BRANCH" \
    "PHASE3_LIVE_RUN_ID=${suffix//-/_}" \
    "VERBOFLEX_BITBUCKET_LIVE_WORKSPACE=$VERBOFLEX_BITBUCKET_LIVE_WORKSPACE" \
    "VERBOFLEX_BITBUCKET_LIVE_REPOSITORY=$VERBOFLEX_BITBUCKET_LIVE_REPOSITORY" \
    "LIVE_API_IP=$SMOKE_LIVE_API_IP" \
    "LIVE_TOKEN_IP=$SMOKE_LIVE_TOKEN_IP" >"$SMOKE_ENV_FILE"
  chmod 600 "$SMOKE_ENV_FILE"
  : >"$SMOKE_PROVIDER_AUDIT_FILE"
  chmod 600 "$SMOKE_PROVIDER_AUDIT_FILE"
  write_live_audit_proxy
  write_live_api_driver
  make_tls_material
}

configure_live_compose() {
  cat >"$SMOKE_OVERRIDE_FILE" <<'YAML'
services:
  postgres:
    ports:
      - "127.0.0.1:${PHASE3_POSTGRES_PORT}:5432"
  live-bitbucket-audit:
    image: python:3.14-slim
    environment:
      LIVE_API_IP: ${LIVE_API_IP}
      LIVE_TOKEN_IP: ${LIVE_TOKEN_IP}
      LIVE_AUDIT_FILE: /run/phase3/provider-audit.jsonl
      LIVE_TLS_CERT: /run/phase3/server.pem
      LIVE_TLS_KEY: /run/phase3/server.key
    command: ["python", "/run/phase3/live_audit_proxy.py"]
    volumes:
      - ${PHASE3_RUNTIME_DIR}:/run/phase3
    networks:
      default:
        aliases: [bitbucket.org, api.bitbucket.org]
  backend:
    environment:
      VERBOFLEX_CORS_ORIGINS: '["${PHASE3_FRONTEND_ORIGIN}"]'
      SSL_CERT_FILE: /run/phase3/ca.pem
    volumes:
      - ${PHASE3_RUNTIME_DIR}/ca.pem:/run/phase3/ca.pem:ro
      - ${PHASE3_RUNTIME_DIR}/ca.pem:/opt/venv/lib/python3.14/site-packages/certifi/cacert.pem:ro
    depends_on:
      live-bitbucket-audit:
        condition: service_started
  worker:
    environment:
      SSL_CERT_FILE: /run/phase3/ca.pem
    volumes:
      - ${PHASE3_RUNTIME_DIR}/ca.pem:/run/phase3/ca.pem:ro
      - ${PHASE3_RUNTIME_DIR}/ca.pem:/opt/venv/lib/python3.14/site-packages/certifi/cacert.pem:ro
    depends_on:
      live-bitbucket-audit:
        condition: service_started
  scheduler:
    environment:
      SSL_CERT_FILE: /run/phase3/ca.pem
    volumes:
      - ${PHASE3_RUNTIME_DIR}/ca.pem:/run/phase3/ca.pem:ro
      - ${PHASE3_RUNTIME_DIR}/ca.pem:/opt/venv/lib/python3.14/site-packages/certifi/cacert.pem:ro
    depends_on:
      live-bitbucket-audit:
        condition: service_started
YAML
  chmod 600 "$SMOKE_OVERRIDE_FILE"
}

preflight_live() {
  command -v docker >/dev/null 2>&1 || die "Docker is unavailable"
  command -v openssl >/dev/null 2>&1 || die "OpenSSL is unavailable"
  docker info >/dev/null 2>&1 || die "Docker daemon is unavailable"
  "$BACKEND_ROOT/.venv/bin/python" -m py_compile \
    "$SMOKE_LIVE_PROXY_SCRIPT" "$SMOKE_LIVE_DRIVER_SCRIPT"
  compose config --quiet >/dev/null
  printf 'phase3 live provider preflight: PASS\n'
}

wait_for_live_proxy() {
  local deadline=$((SECONDS + 60))
  while [ "$SECONDS" -lt "$deadline" ]; do
    if compose exec -T live-bitbucket-audit python -c \
      'import socket,ssl; r=socket.create_connection(("127.0.0.1",443),2); s=ssl._create_unverified_context().wrap_socket(r,server_hostname="api.bitbucket.org"); s.close()' \
      >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  die "live provider audit proxy readiness timed out"
}

prepare_live_stack() {
  compose build backend >/dev/null
  compose up -d postgres redis live-bitbucket-audit >/dev/null
  wait_for_live_proxy
  compose run --rm -T backend alembic upgrade head >/dev/null
  printf '%s\n' "$SMOKE_LIVE_ADMIN_PASSWORD" | compose run --rm -T backend \
    python -m verboflex.cli bootstrap-admin \
      --email "$SMOKE_LIVE_ADMIN_EMAIL" --display-name 'Phase 3 live read' \
      >"$SMOKE_RUNTIME_DIR/bootstrap.out"
  grep -Fxq 'First administrator created.' "$SMOKE_RUNTIME_DIR/bootstrap.out" \
    || die "live smoke administrator bootstrap failed"
  compose up -d backend worker scheduler >/dev/null
  wait_for_url "$SMOKE_BACKEND_URL/api/v1/health" 200 backend
  wait_for_worker
  wait_for_scheduler
}

verify_live_provider_audit() {
  "$BACKEND_ROOT/.venv/bin/python" - "${1:-$SMOKE_PROVIDER_AUDIT_FILE}" <<'PY'
import json
import sys

try:
    rows = [json.loads(line) for line in open(sys.argv[1], encoding="utf-8") if line.strip()]
    assert rows
    assert all(set(row) == {"category", "method", "resource_family", "status"} for row in rows)
    oauth = [row for row in rows if row["category"] == "oauth-token-exchange"]
    resources = [row for row in rows if row["category"] == "resource"]
    assert len(oauth) >= 2 and all(row["method"] == "POST" for row in oauth)
    assert resources and all(row["method"] == "GET" for row in resources)
    mutations = [
        row for row in resources
        if row["resource_family"] in {
            "branch-create", "source-commit", "pull-request-create", "forbidden-mutation"
        }
    ]
    assert not mutations
    assert all(isinstance(row["status"], int) and 100 <= row["status"] <= 599 for row in rows)
except (AssertionError, OSError, ValueError, TypeError, json.JSONDecodeError):
    print("phase3-live error: provider method audit rejected", file=sys.stderr)
    raise SystemExit(1)
print(
    "phase3 live provider audit: PASS "
    f"(oauth_post={len(oauth)}, resource_get={len(resources)}, resource_mutations=0)"
)
PY
}

verify_live_result() {
  "$BACKEND_ROOT/.venv/bin/python" - "${1:-$SMOKE_LIVE_RESULT_FILE}" <<'PY'
import json
import re
import sys

expected = {
    "readiness", "duration_ms", "result_count", "repository_identity_sha256",
    "branch_identity_sha256", "commit_identity_sha256", "result_identity_sha256",
    "final_local_revoke",
}
try:
    result = json.load(open(sys.argv[1], encoding="utf-8"))
    assert set(result) == expected
    assert result["readiness"] == "ready"
    assert result["final_local_revoke"] == "PASS"
    assert isinstance(result["duration_ms"], int) and result["duration_ms"] >= 0
    assert isinstance(result["result_count"], int) and 1 <= result["result_count"] <= 500
    for key in expected:
        if key.endswith("_sha256"):
            assert isinstance(result[key], str) and re.fullmatch(r"[0-9a-f]{64}", result[key])
except (AssertionError, OSError, ValueError, TypeError, json.JSONDecodeError):
    print("phase3-live error: sanitized result rejected", file=sys.stderr)
    raise SystemExit(1)
print(
    "phase3 live provider result: PASS "
    f"(readiness=ready, duration_ms={result['duration_ms']}, "
    f"result_count={result['result_count']}, "
    f"repository_sha256={result['repository_identity_sha256']}, "
    f"branch_sha256={result['branch_identity_sha256']}, "
    f"commit_sha256={result['commit_identity_sha256']}, "
    f"result_sha256={result['result_identity_sha256']}, final_local_revoke=PASS)"
)
PY
}

verify_live_no_sensitive_surfaces() {
  local logs="$SMOKE_RUNTIME_DIR/compose.log" secret surface
  compose logs --no-color >"$logs" 2>"$SMOKE_RUNTIME_DIR/compose-errors.log"
  for secret in \
    "$VERBOFLEX_BITBUCKET_OAUTH_CLIENT_ID" \
    "$SMOKE_CLIENT_SECRET" \
    "$SMOKE_POSTGRES_PASSWORD" \
    "$SMOKE_JWT_SECRET_KEY" \
    "$SMOKE_KEYRING" \
    "$SMOKE_LIVE_ADMIN_PASSWORD" \
    "$SMOKE_LIVE_ADMIN_NEW_PASSWORD" \
    "$VERBOFLEX_BITBUCKET_LIVE_WORKSPACE" \
    "$VERBOFLEX_BITBUCKET_LIVE_REPOSITORY" \
    "$SMOKE_LIVE_BRANCH"; do
    for surface in "$logs" "$SMOKE_PROVIDER_AUDIT_FILE" "$SMOKE_LIVE_RESULT_FILE" \
      "$SMOKE_RUNTIME_DIR/compose-errors.log" "$SMOKE_RUNTIME_DIR/driver.out" \
      "$SMOKE_RUNTIME_DIR/driver.err"; do
      if [ -s "$surface" ] && grep -Fq -- "$secret" "$surface"; then
        die "live smoke exposed credential or provider identity material"
      fi
    done
  done
  for surface in "$logs" "$SMOKE_PROVIDER_AUDIT_FILE" "$SMOKE_LIVE_RESULT_FILE" \
    "$SMOKE_RUNTIME_DIR/compose-errors.log" "$SMOKE_RUNTIME_DIR/driver.out" \
    "$SMOKE_RUNTIME_DIR/driver.err"; do
    if [ -s "$surface" ] && grep -Eiq \
      '(authorization:[[:space:]]*(bearer|basic)|client_secret[=:][^[:space:]]|access_token[=:][^[:space:]]|refresh_token[=:][^[:space:]]|gAAAAA[A-Za-z0-9_-]+)' \
      "$surface"; then
      die "live smoke captured credential-shaped material"
    fi
  done
}

run_live_api_driver() {
  if ! "$BACKEND_ROOT/.venv/bin/python" "$SMOKE_LIVE_DRIVER_SCRIPT" \
    "$SMOKE_ENV_FILE" "$SMOKE_LIVE_RESULT_FILE" \
    >"$SMOKE_RUNTIME_DIR/driver.out" 2>"$SMOKE_RUNTIME_DIR/driver.err"; then
    sed -n '1p' "$SMOKE_RUNTIME_DIR/driver.err" >&2
    die "live provider production API journey rejected"
  fi
}

run_live_provider_read_only() {
  local skip_if_unconfigured=${1:-false}
  if ! live_configuration_ready; then
    if [ "$skip_if_unconfigured" = "true" ]; then
      printf 'phase3 live provider: SKIP (supplemental variables are not configured)\n'
      return 0
    fi
    die "supplemental live variables are not configured"
  fi
  trap cleanup EXIT INT TERM
  initialize_live_runtime
  configure_live_compose
  preflight_live
  prepare_live_stack
  run_live_api_driver
  verify_live_provider_audit
  verify_live_result
  verify_live_no_sensitive_surfaces
  cleanup
  trap - EXIT INT TERM
  printf 'phase3 supplemental live provider read: PASS\n'
}

self_test_live_mode() {
  local audit result output self_test_secret runtime_dir
  self_test_secret="phase3-self-test-secret-$(openssl rand -hex 12)"
  runtime_dir=$(mktemp -d /tmp/verboflex-phase03-live-self-test.XXXXXX)
  SMOKE_RUNTIME_DIR="$runtime_dir"
  audit="$runtime_dir/audit.jsonl"
  result="$runtime_dir/result.json"
  output="$runtime_dir/output.log"
  trap cleanup EXIT INT TERM
  chmod 700 "$runtime_dir"
  SMOKE_LIVE_PROXY_SCRIPT="$runtime_dir/live_audit_proxy.py"
  SMOKE_LIVE_DRIVER_SCRIPT="$runtime_dir/live_api_driver.py"
  write_live_audit_proxy
  write_live_api_driver
  "$BACKEND_ROOT/.venv/bin/python" -m py_compile \
    "$SMOKE_LIVE_PROXY_SCRIPT" "$SMOKE_LIVE_DRIVER_SCRIPT"
  printf '%s\n' \
    '{"category":"oauth-token-exchange","method":"POST","resource_family":"oauth-token","status":200}' \
    '{"category":"oauth-token-exchange","method":"POST","resource_family":"oauth-token","status":200}' \
    '{"category":"resource","method":"GET","resource_family":"branch-read","status":200}' \
    '{"category":"resource","method":"GET","resource_family":"source-read","status":200}' >"$audit"
  printf '%s\n' \
    '{"branch_identity_sha256":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","commit_identity_sha256":"cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc","duration_ms":1,"final_local_revoke":"PASS","readiness":"ready","repository_identity_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","result_count":1,"result_identity_sha256":"dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"}' >"$result"
  : >"$output"
  chmod 600 "$audit" "$result" "$output"
  verify_live_provider_audit "$audit" >"$output"
  verify_live_result "$result" >>"$output"
  printf '%s\n' \
    '{"category":"resource","method":"POST","resource_family":"forbidden-mutation","status":405}' \
    >>"$audit"
  if verify_live_provider_audit "$audit" >/dev/null 2>&1; then
    die "live method-audit negative control unexpectedly passed"
  fi
  if grep -Fq -- "$self_test_secret" "$output"; then
    die "live self-test exposed secret material"
  fi
  cleanup
  trap - EXIT INT TERM
  [ ! -e "$runtime_dir" ] || die "live self-test cleanup left temporary material"
  printf 'phase3 live provider self-test: PASS\n'
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

case "${1:-}:${2:-}" in
  --mock-provider:) run_mock_with_port_retry ;;
  --mock-provider-once:) run_mock_once ;;
  --self-test-live-mode:) self_test_live_mode ;;
  --live-provider-read-only:--skip-if-unconfigured) run_live_provider_read_only true ;;
  --live-provider-read-only:) run_live_provider_read_only false ;;
  *) die "usage: tools/phase3_smoke.sh --mock-provider|--self-test-live-mode|--live-provider-read-only [--skip-if-unconfigured]" ;;
esac

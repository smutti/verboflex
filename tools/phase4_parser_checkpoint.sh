#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH='' cd -- "$SCRIPT_DIR/.." && pwd)
readonly SCRIPT_DIR REPO_ROOT
readonly BACKEND_ROOT="$REPO_ROOT/backend"
readonly FRONTEND_ROOT="$REPO_ROOT/frontend"
readonly EVIDENCE_PATH="$REPO_ROOT/docs/evidence/phase-04-parser.md"

HOST_RUNTIME_DIR=""
RECORDS_FILE=""
LICENSE_FILE=""
LAST_OUTPUT=""

SMOKE_PROJECT=""
SMOKE_RUNTIME_DIR=""
SMOKE_ENV_FILE=""
SMOKE_OVERRIDE_FILE=""
SMOKE_IMAGE_TAG=""
SMOKE_BACKEND_URL=""
SMOKE_SOURCE=""
SMOKE_CLIENT_SECRET=""
SMOKE_JWT_SECRET=""
SMOKE_KEYRING=""

CONTAINER_BACKEND_DIGEST=""
CONTAINER_WORKER_DIGEST=""
CONTAINER_IMAGE_DIGEST=""
CONTAINER_PING_COUNT=""
CONTAINER_BACKEND_VALUE_COUNT=""
CONTAINER_WORKER_VALUE_COUNT=""
CONTAINER_DURATION_MS=""
CONTAINER_SECRET_SCAN=""
CONTAINER_SOURCE_SCAN=""
CONTAINER_CLEANUP=""

die() {
  printf 'phase4-parser-checkpoint error: %s\n' "$1" >&2
  exit 1
}

now_ms() {
  "$BACKEND_ROOT/.venv/bin/python" -c 'import time; print(time.time_ns() // 1_000_000)'
}

sha256_file() {
  openssl dgst -sha256 -r "$1" | awk '{print $1}'
}

random_port() {
  "$BACKEND_ROOT/.venv/bin/python" -c \
    'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()'
}

safe_remove_runtime() {
  local target=$1
  [ -z "$target" ] && return 0
  case "$target" in
    /tmp/verboflex-phase04-parser.*|/tmp/verboflex-phase04-parser-host.*)
      [ ! -e "$target" ] || find "$target" -depth -delete
      ;;
    *)
      printf 'phase4-parser-checkpoint error: refused unsafe temporary path cleanup\n' >&2
      return 1
      ;;
  esac
}

compose() {
  docker compose --progress quiet --project-name "$SMOKE_PROJECT" --env-file "$SMOKE_ENV_FILE" \
    -f "$REPO_ROOT/docker-compose.yml" -f "$SMOKE_OVERRIDE_FILE" "$@"
}

cleanup_container() {
  local cleanup_rc=0 container_count volume_count network_count

  if [ -n "$SMOKE_PROJECT" ] && [ -f "$SMOKE_ENV_FILE" ] && [ -f "$SMOKE_OVERRIDE_FILE" ]; then
    compose down --volumes --remove-orphans --timeout 10 >/dev/null 2>&1 || cleanup_rc=1
    container_count=$(docker ps -aq --filter "label=com.docker.compose.project=$SMOKE_PROJECT" | wc -l | tr -d ' ')
    volume_count=$(docker volume ls -q --filter "label=com.docker.compose.project=$SMOKE_PROJECT" | wc -l | tr -d ' ')
    network_count=$(docker network ls -q --filter "label=com.docker.compose.project=$SMOKE_PROJECT" | wc -l | tr -d ' ')
    [ "$container_count" = "0" ] || cleanup_rc=1
    [ "$volume_count" = "0" ] || cleanup_rc=1
    [ "$network_count" = "0" ] || cleanup_rc=1
  fi
  if [ -n "$SMOKE_IMAGE_TAG" ]; then
    if docker image inspect "verboflex-backend:$SMOKE_IMAGE_TAG" >/dev/null 2>&1; then
      docker image rm "verboflex-backend:$SMOKE_IMAGE_TAG" >/dev/null 2>&1 || cleanup_rc=1
    fi
    if docker image inspect "verboflex-backend:$SMOKE_IMAGE_TAG" >/dev/null 2>&1; then
      cleanup_rc=1
    fi
  fi
  safe_remove_runtime "$SMOKE_RUNTIME_DIR" || cleanup_rc=1
  if [ -n "$SMOKE_RUNTIME_DIR" ] && [ -e "$SMOKE_RUNTIME_DIR" ]; then cleanup_rc=1; fi

  if [ "$cleanup_rc" -eq 0 ]; then
    CONTAINER_CLEANUP="PASS"
  else
    CONTAINER_CLEANUP="FAIL"
  fi
  return "$cleanup_rc"
}

cleanup_all() {
  local incoming_rc=$? cleanup_rc=0
  trap - EXIT INT TERM
  set +e
  if [ -n "$SMOKE_RUNTIME_DIR" ] || [ -n "$SMOKE_PROJECT" ]; then
    cleanup_container || cleanup_rc=1
  fi
  safe_remove_runtime "$HOST_RUNTIME_DIR" || cleanup_rc=1
  set -e
  if [ "$incoming_rc" -ne 0 ] || [ "$cleanup_rc" -ne 0 ]; then
    exit 1
  fi
}

preflight() {
  command -v uv >/dev/null 2>&1 || die "uv is unavailable"
  command -v docker >/dev/null 2>&1 || die "Docker is unavailable"
  command -v openssl >/dev/null 2>&1 || die "OpenSSL is unavailable"
  command -v curl >/dev/null 2>&1 || die "curl is unavailable"
  [ -x "$BACKEND_ROOT/.venv/bin/python" ] || die "backend virtual environment is unavailable"
  docker info >/dev/null 2>&1 || die "Docker daemon is unavailable"
}

record_command() {
  local record_id=$1 label=$2 command_text=$3
  shift 3
  local output start end duration rc count="-" digest
  output="$HOST_RUNTIME_DIR/${record_id}.log"
  : >"$output"
  chmod 600 "$output"
  start=$(now_ms)
  set +e
  if [ "$record_id" = "container-smoke" ]; then
    (trap 'cleanup_container' EXIT INT TERM; "$@") >"$output" 2>&1
  else
    ("$@") >"$output" 2>&1
  fi
  rc=$?
  set -e
  end=$(now_ms)
  duration=$((end - start))
  LAST_OUTPUT="$output"
  digest=$(sha256_file "$output")

  if [ "$rc" -ne 0 ]; then
    printf 'phase4-parser-checkpoint error: %s failed (return_code=%s, output_sha256=%s)\n' \
      "$label" "$rc" "$digest" >&2
    # This command may contain source text or credentials. Only its digest is
    # public evidence; discard the own temporary raw failure artifact.
    rm -f -- "$output"
    exit "$rc"
  fi

  case "$record_id" in
    parser-coverage)
      count=$(grep -Eo '[0-9]+ passed' "$output" | tail -1 | awk '{print $1}')
      [ -n "$count" ] || die "parser test count was unavailable"
      ;;
    python-licenses)
      count=$("$BACKEND_ROOT/.venv/bin/python" -c \
        'import json,sys; print(len(json.load(open(sys.argv[1], encoding="utf-8"))))' "$output")
      ;;
    license-policy)
      count=$(grep -Eo 'packages=[0-9]+' "$output" | tail -1 | cut -d= -f2)
      [ -n "$count" ] || die "license policy count was unavailable"
      ;;
    container-smoke)
      load_container_result "$output"
      count="$CONTAINER_BACKEND_VALUE_COUNT"
      ;;
  esac

  printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$label" "$command_text" "$duration" "$rc" "$count" "$digest" >>"$RECORDS_FILE"
  printf 'phase4 parser checkpoint: PASS — %s (%sms, sha256=%s)\n' \
    "$label" "$duration" "$digest"
}

container_result_field() {
  local path=$1 field=$2
  "$BACKEND_ROOT/.venv/bin/python" -c '
import re
import sys

line = next(
    value for value in open(sys.argv[1], encoding="utf-8")
    if value.startswith("container-smoke: PASS ")
)
match = re.search(r"(?:^| )" + re.escape(sys.argv[2]) + r"=([^ ]+)", line)
assert match is not None
print(match.group(1))
' "$path" "$field"
}

load_container_result() {
  local path=$1
  CONTAINER_DURATION_MS=$(container_result_field "$path" duration_ms)
  CONTAINER_PING_COUNT=$(container_result_field "$path" worker_ping_responses)
  CONTAINER_BACKEND_VALUE_COUNT=$(container_result_field "$path" value_count)
  CONTAINER_WORKER_VALUE_COUNT="$CONTAINER_BACKEND_VALUE_COUNT"
  CONTAINER_BACKEND_DIGEST=$(container_result_field "$path" canonical_digest)
  CONTAINER_WORKER_DIGEST="$CONTAINER_BACKEND_DIGEST"
  CONTAINER_IMAGE_DIGEST=$(container_result_field "$path" image_digest)
  CONTAINER_SECRET_SCAN=$(container_result_field "$path" secret_scan)
  CONTAINER_SOURCE_SCAN=$(container_result_field "$path" source_scan)
  CONTAINER_CLEANUP=$(container_result_field "$path" cleanup)
  [ "$(container_result_field "$path" persistence_writes)" = "0" ] \
    || die "container parser smoke crossed the persistence boundary"
}

license_policy() {
  local inventory=$1
  [ -f "$inventory" ] || die "license inventory is missing"
  [ ! -L "$inventory" ] || die "license inventory must not be a symbolic link"
  [ "$(wc -c <"$inventory" | tr -d ' ')" -le 2097152 ] \
    || die "license inventory exceeds the bounded size"
  "$BACKEND_ROOT/.venv/bin/python" - "$inventory" <<'PY'
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ALLOWED = {
    "0BSD",
    "Apache Software License",
    "Apache Software License; BSD License",
    "Apache Software License; MIT License",
    "Apache-2.0",
    "Apache-2.0 OR BSD-2-Clause",
    "Apache-2.0 OR BSD-3-Clause",
    "BSD License",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "ISC License (ISCL)",
    "LGPL-3.0-only",
    "MIT",
    "MIT License",
    "MIT OR Apache-2.0",
    "MIT-0",
    "MPL-2.0",
    "Mozilla Public License 2.0 (MPL 2.0)",
    "PSF-2.0",
    "Python Software Foundation License",
    "The Unlicense (Unlicense)",
}

path = Path(sys.argv[1])
try:
    raw = path.read_bytes()
    rows = json.loads(raw)
    assert isinstance(rows, list) and rows
    identities: set[tuple[str, str]] = set()
    accepted = 0
    for row in rows:
        assert isinstance(row, dict)
        name = row.get("Name")
        version = row.get("Version")
        license_name = row.get("License")
        url = row.get("URL")
        assert all(isinstance(value, str) and value for value in (name, version, license_name, url))
        identity = (name.casefold(), version)
        assert identity not in identities
        identities.add(identity)
        if identity == ("verboflex", "0.1.0"):
            assert license_name == "UNKNOWN" and url == "UNKNOWN"
            continue
        # Approved exact release: 04-07-SUMMARY; exact SPDX recorded in 04-14-SUMMARY.
        # This is not a general allowance for CNRI-Python or other regex releases.
        approved_regex = (
            identity == ("regex", "2026.9.3")
            and license_name == "Apache-2.0 AND CNRI-Python"
        )
        assert license_name in ALLOWED or approved_regex
        accepted += 1
    assert accepted > 0
except (AssertionError, OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError):
    print("license-policy: FAIL", file=sys.stderr)
    raise SystemExit(1)

print(
    "license-policy: PASS "
    f"packages={accepted} inventory_sha256={hashlib.sha256(raw).hexdigest()}"
)
PY
}

assert_flagged_packages_absent() {
  "$BACKEND_ROOT/.venv/bin/python" - "$BACKEND_ROOT/pyproject.toml" \
    "$BACKEND_ROOT/uv.lock" "$FRONTEND_ROOT/package.json" "$FRONTEND_ROOT/package-lock.json" <<'PY'
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

pyproject, uv_lock, package_json, package_lock = (Path(value) for value in sys.argv[1:])
python_inputs = pyproject.read_text(encoding="utf-8") + "\n" + uv_lock.read_text(encoding="utf-8")
frontend = json.loads(package_json.read_text(encoding="utf-8"))
lock = json.loads(package_lock.read_text(encoding="utf-8"))

assert re.search(r'(?m)^name = "regex"$', python_inputs) is None
assert "regex==2026.9.3" not in python_inputs
assert "@tanstack/react-virtual" not in frontend.get("dependencies", {})
assert "@tanstack/react-virtual" not in frontend.get("devDependencies", {})
assert "node_modules/@tanstack/react-virtual" not in lock.get("packages", {})
print("flagged-package-installation: ABSENT")
PY
}

write_smoke_files() {
  local backend_port=$1
  printf '%s\n' \
    "VERBOFLEX_BACKEND_PORT=$backend_port" \
    "VERBOFLEX_IMAGE_TAG=$SMOKE_IMAGE_TAG" \
    'VERBOFLEX_BITBUCKET_OAUTH_CLIENT_ID=phase4-parser-checkpoint' \
    "VERBOFLEX_BITBUCKET_OAUTH_CLIENT_SECRET=$SMOKE_CLIENT_SECRET" \
    "VERBOFLEX_BITBUCKET_TOKEN_ENCRYPTION_KEYRING=$SMOKE_KEYRING" \
    "PHASE4_JWT_SECRET_KEY=$SMOKE_JWT_SECRET" >"$SMOKE_ENV_FILE"
  chmod 600 "$SMOKE_ENV_FILE"
  cat >"$SMOKE_OVERRIDE_FILE" <<'YAML'
services:
  backend:
    environment:
      VERBOFLEX_JWT_SECRET_KEY: ${PHASE4_JWT_SECRET_KEY}
  worker:
    environment:
      VERBOFLEX_JWT_SECRET_KEY: ${PHASE4_JWT_SECRET_KEY}
YAML
  chmod 600 "$SMOKE_OVERRIDE_FILE"
}

initialize_container_runtime() {
  local suffix backend_port
  suffix="$$-$(date +%s)-$(openssl rand -hex 4)"
  SMOKE_PROJECT="verboflex_phase04_parser_${suffix//-/_}"
  SMOKE_RUNTIME_DIR=$(mktemp -d /tmp/verboflex-phase04-parser.XXXXXX)
  SMOKE_ENV_FILE="$SMOKE_RUNTIME_DIR/owner-only.env"
  SMOKE_OVERRIDE_FILE="$SMOKE_RUNTIME_DIR/parser-smoke.yml"
  SMOKE_IMAGE_TAG="phase04-parser-$suffix"
  chmod 700 "$SMOKE_RUNTIME_DIR"
  backend_port=$(random_port)
  SMOKE_BACKEND_URL="http://127.0.0.1:$backend_port"
  SMOKE_CLIENT_SECRET="phase4-client-$(openssl rand -hex 24)"
  SMOKE_JWT_SECRET="phase4-jwt-$(openssl rand -hex 32)"
  SMOKE_SOURCE="phase4-source-$(openssl rand -hex 24)"
  SMOKE_KEYRING=$(
    cd "$BACKEND_ROOT"
    uv run python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
  )
  write_smoke_files "$backend_port"
}

wait_for_backend() {
  local deadline=$((SECONDS + 180)) status rc
  while [ "$SECONDS" -lt "$deadline" ]; do
    set +e
    status=$(curl --silent --show-error --max-time 3 --output /dev/null \
      --write-out '%{http_code}' "$SMOKE_BACKEND_URL/api/v1/health")
    rc=$?
    set -e
    if [ "$rc" -eq 0 ] && [ "$status" = "200" ]; then return 0; fi
    sleep 1
  done
  compose ps >&2 || true
  die "backend readiness timed out"
}

wait_for_service_health() {
  local service=$1 deadline=$((SECONDS + 180)) container status
  while [ "$SECONDS" -lt "$deadline" ]; do
    container=$(compose ps -q "$service")
    if [ -n "$container" ]; then
      status=$(docker inspect --format '{{.State.Health.Status}}' "$container" 2>/dev/null || true)
      [ "$status" = "healthy" ] && return 0
      [ "$status" = "unhealthy" ] && die "$service became unhealthy"
    fi
    sleep 1
  done
  compose ps >&2 || true
  die "$service health readiness timed out"
}

run_parser_in_service() {
  local service=$1 destination=$2
  compose exec -T -e PHASE4_SCALAR_SOURCE="$SMOKE_SOURCE" "$service" python -c '
import hashlib
import json
import os
from contextlib import ExitStack
from unittest.mock import patch

from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session


def reject_persistence(*args, **kwargs):
    raise AssertionError("parser crossed the persistence boundary")

source = os.environ["PHASE4_SCALAR_SOURCE"]
content = (
    "<resources><string name=\"checkpoint.scalar\">"
    + source
    + "</string></resources>"
).encode("utf-8")
with ExitStack() as guards:
    for owner, method in (
        (Engine, "connect"),
        (Engine, "begin"),
        (Connection, "execute"),
        (Connection, "exec_driver_sql"),
        (Session, "add"),
        (Session, "add_all"),
        (Session, "delete"),
        (Session, "execute"),
        (Session, "flush"),
        (Session, "commit"),
    ):
        guards.enter_context(patch.object(owner, method, reject_persistence))
    from verboflex.localization.importing.core import CanonicalParserInput
    from verboflex.localization.importing.registry import parse_canonical_mapping

    result = parse_canonical_mapping((CanonicalParserInput(
        format="android_xml",
        repository_side="direct",
        path="app/src/main/res/values/strings.xml",
        content=content,
        layout_identity="app/src/main/res",
        layout_version=1,
        base_language="en",
    ),))
assert result.issues == () and len(result.values) == 1
assert result.values[0].display_text == source
payload = json.dumps(
    result.to_mapping(), ensure_ascii=False, separators=(",", ":"), sort_keys=True
).encode("utf-8")
print(json.dumps({
    "canonical_digest": hashlib.sha256(payload).hexdigest(),
    "persistence_writes": 0,
    "value_count": len(result.values),
}, separators=(",", ":"), sort_keys=True))
' >"$destination"
  chmod 600 "$destination"
}

parse_runtime_result() {
  local path=$1 field=$2
  "$BACKEND_ROOT/.venv/bin/python" -c \
    'import json,re,sys; value=json.load(open(sys.argv[1], encoding="utf-8"))[sys.argv[2]]; assert isinstance(value, (int,str)); print(value)' \
    "$path" "$field"
}

run_single_worker_ping() {
  local destination=$1
  compose exec -T backend python -c '
import json
from verboflex.worker.celery_app import app

responses = app.control.inspect(timeout=8).ping() or {}
assert len(responses) == 1
assert list(responses.values()) == [{"ok": "pong"}]
print(json.dumps({"worker_ping_responses": len(responses)}, separators=(",", ":")))
' >"$destination"
  chmod 600 "$destination"
}

scan_container_surfaces() {
  local logs=$1 errors=$2 backend_result=$3 worker_result=$4 ping_result=$5 secret surface
  for secret in "$SMOKE_CLIENT_SECRET" "$SMOKE_JWT_SECRET" "$SMOKE_KEYRING" "$SMOKE_SOURCE"; do
    for surface in "$logs" "$errors" "$backend_result" "$worker_result" "$ping_result"; do
      if grep -Fq -- "$secret" "$surface"; then
        die "container evidence exposed seeded secret or source material"
      fi
    done
  done
  for surface in "$logs" "$errors" "$backend_result" "$worker_result" "$ping_result"; do
    if grep -Eiq \
      '(authorization:[[:space:]]*(bearer|basic)|client_secret[=:][^[:space:]]|access_token[=:][^[:space:]]|refresh_token[=:][^[:space:]]|gAAAAA[A-Za-z0-9_-]+)' \
      "$surface"; then
      die "container evidence exposed credential-shaped material"
    fi
    if grep -Fq '<resources' "$surface" || grep -Fq 'checkpoint.scalar' "$surface"; then
      die "container evidence exposed parser source content"
    fi
  done
  CONTAINER_SECRET_SCAN="PASS"
  CONTAINER_SOURCE_SCAN="PASS"
}

container_smoke() {
  local started backend_result worker_result ping_result logs errors
  local backend_container worker_container backend_image worker_image
  started=$(now_ms)
  initialize_container_runtime
  backend_result="$SMOKE_RUNTIME_DIR/backend-result.json"
  worker_result="$SMOKE_RUNTIME_DIR/worker-result.json"
  ping_result="$SMOKE_RUNTIME_DIR/worker-ping.json"
  logs="$SMOKE_RUNTIME_DIR/compose.log"
  errors="$SMOKE_RUNTIME_DIR/compose-errors.log"

  compose config --quiet >/dev/null
  compose build backend >/dev/null
  compose up -d postgres redis backend worker >/dev/null
  wait_for_backend
  wait_for_service_health postgres
  wait_for_service_health redis
  wait_for_service_health backend
  wait_for_service_health worker

  [ "$(compose ps --status running -q worker | wc -l | tr -d ' ')" = "1" ] \
    || die "the isolated stack did not contain exactly one running worker"
  run_single_worker_ping "$ping_result"
  CONTAINER_PING_COUNT=$(parse_runtime_result "$ping_result" worker_ping_responses)
  [ "$CONTAINER_PING_COUNT" = "1" ] || die "Celery ping did not return exactly one worker"

  run_parser_in_service backend "$backend_result"
  run_parser_in_service worker "$worker_result"
  CONTAINER_BACKEND_DIGEST=$(parse_runtime_result "$backend_result" canonical_digest)
  CONTAINER_WORKER_DIGEST=$(parse_runtime_result "$worker_result" canonical_digest)
  CONTAINER_BACKEND_VALUE_COUNT=$(parse_runtime_result "$backend_result" value_count)
  CONTAINER_WORKER_VALUE_COUNT=$(parse_runtime_result "$worker_result" value_count)
  [ "$CONTAINER_BACKEND_VALUE_COUNT" = "1" ] || die "backend parser smoke returned no value"
  [ "$CONTAINER_WORKER_VALUE_COUNT" = "1" ] || die "worker parser smoke returned no value"
  [ -n "$CONTAINER_BACKEND_DIGEST" ] \
    && [ "$CONTAINER_BACKEND_DIGEST" = "$CONTAINER_WORKER_DIGEST" ] \
    || die "backend and worker parser digests differ"
  [[ "$CONTAINER_BACKEND_DIGEST" =~ ^[0-9a-f]{64}$ ]] \
    || die "container parser digest is invalid"
  [ "$(parse_runtime_result "$backend_result" persistence_writes)" = "0" ] \
    || die "backend parser smoke crossed the persistence boundary"
  [ "$(parse_runtime_result "$worker_result" persistence_writes)" = "0" ] \
    || die "worker parser smoke crossed the persistence boundary"

  backend_container=$(compose ps -q backend)
  worker_container=$(compose ps -q worker)
  backend_image=$(docker inspect --format '{{.Image}}' "$backend_container")
  worker_image=$(docker inspect --format '{{.Image}}' "$worker_container")
  [ -n "$backend_image" ] && [ "$backend_image" = "$worker_image" ] \
    || die "backend and worker did not execute the same runtime image"
  CONTAINER_IMAGE_DIGEST=${backend_image#sha256:}

  compose logs --no-color >"$logs" 2>"$errors"
  chmod 600 "$logs" "$errors"
  scan_container_surfaces "$logs" "$errors" "$backend_result" "$worker_result" "$ping_result"
  cleanup_container || die "disposable container resources remained after cleanup"
  CONTAINER_DURATION_MS=$(($(now_ms) - started))
  printf 'container-smoke: PASS duration_ms=%s worker_ping_responses=1 value_count=1 canonical_digest=%s image_digest=%s secret_scan=PASS source_scan=PASS persistence_writes=0 cleanup=PASS\n' \
    "$CONTAINER_DURATION_MS" "$CONTAINER_BACKEND_DIGEST" "$CONTAINER_IMAGE_DIGEST"
}

collect_versions() {
  UV_VERSION=$(uv --version | awk '{print $2}')
  PYTHON_VERSION=$("$BACKEND_ROOT/.venv/bin/python" -c 'import platform; print(platform.python_version())')
  PYTEST_VERSION=$("$BACKEND_ROOT/.venv/bin/python" -c 'import importlib.metadata as m; print(m.version("pytest"))')
  COVERAGE_VERSION=$("$BACKEND_ROOT/.venv/bin/python" -c 'import importlib.metadata as m; print(m.version("pytest-cov"))')
  RUFF_VERSION=$("$BACKEND_ROOT/.venv/bin/python" -c 'import importlib.metadata as m; print(m.version("ruff"))')
  MYPY_VERSION=$("$BACKEND_ROOT/.venv/bin/python" -c 'import importlib.metadata as m; print(m.version("mypy"))')
  PIP_AUDIT_VERSION=$("$BACKEND_ROOT/.venv/bin/python" -c 'import importlib.metadata as m; print(m.version("pip-audit"))')
  PIP_LICENSES_VERSION=$("$BACKEND_ROOT/.venv/bin/python" -c 'import importlib.metadata as m; print(m.version("pip-licenses"))')
  DOCKER_VERSION=$(docker version --format '{{.Server.Version}}')
  COMPOSE_VERSION=$(docker compose version --short)
  export UV_VERSION PYTHON_VERSION PYTEST_VERSION COVERAGE_VERSION RUFF_VERSION MYPY_VERSION
  export PIP_AUDIT_VERSION PIP_LICENSES_VERSION DOCKER_VERSION COMPOSE_VERSION
}

write_evidence() {
  local parser_count license_count manifest path relative digest evidence_tmp secret
  parser_count=$(awk -F '\t' '$1 == "Parser package branch coverage" {print $5}' "$RECORDS_FILE")
  license_count=$(awk -F '\t' '$1 == "Repository Python license policy" {print $5}' "$RECORDS_FILE")
  [ -n "$parser_count" ] && [ -n "$license_count" ] || die "evidence counts are incomplete"
  evidence_tmp="$HOST_RUNTIME_DIR/phase-04-parser.md"

  {
    printf '%s\n' \
      '# Phase 04 Parser Checkpoint Evidence' \
      '' \
      'This ledger contains only fixed commands, tool versions, counts, durations, return codes, manifest hashes, and redacted output digests. It contains no localization source, provider payload, credential, environment value, or diagnostic body.' \
      '' \
      '## Verdict' \
      '' \
      '- Gate-status: PASS' \
      '- Persistence-authority: NOT STARTED' \
      '- Flagged-package-installation: ABSENT' \
      "- Parser-test-count: $parser_count" \
      "- Approved-third-party-license-count: $license_count" \
      '- Worker-ping-responses: 1' \
      "- Backend-value-count: $CONTAINER_BACKEND_VALUE_COUNT" \
      "- Worker-value-count: $CONTAINER_WORKER_VALUE_COUNT" \
      "- Backend-canonical-digest: $CONTAINER_BACKEND_DIGEST" \
      "- Worker-canonical-digest: $CONTAINER_WORKER_DIGEST" \
      "- Runtime-image-digest: $CONTAINER_IMAGE_DIGEST" \
      '- Persistence-writes: 0' \
      "- Secret-scan: $CONTAINER_SECRET_SCAN" \
      "- Source-body-scan: $CONTAINER_SOURCE_SCAN" \
      "- Cleanup: $CONTAINER_CLEANUP" \
      '' \
      '## Tool Versions' \
      '' \
      "- uv: $UV_VERSION" \
      "- Python: $PYTHON_VERSION" \
      "- pytest: $PYTEST_VERSION" \
      "- pytest-cov: $COVERAGE_VERSION" \
      "- Ruff: $RUFF_VERSION" \
      "- mypy: $MYPY_VERSION" \
      "- pip-audit: $PIP_AUDIT_VERSION" \
      "- pip-licenses: $PIP_LICENSES_VERSION" \
      "- Docker Engine: $DOCKER_VERSION" \
      "- Docker Compose: $COMPOSE_VERSION" \
      '' \
      '## Command Records' \
      '' \
      '| Check | Command | Duration (ms) | Return code | Count | Redacted output SHA-256 |' \
      '|---|---|---:|---:|---:|---|'
    while IFS=$'\t' read -r label command duration rc count output_digest; do
      printf '| %s | `%s` | %s | %s | %s | `%s` |\n' \
        "$label" "$command" "$duration" "$rc" "$count" "$output_digest"
    done <"$RECORDS_FILE"
    printf '%s\n' '' '## Fixture Manifest Hashes' '' \
      '| Manifest | SHA-256 |' '|---|---|'
    while IFS= read -r manifest; do
      relative=${manifest#"$REPO_ROOT/"}
      digest=$(sha256_file "$manifest")
      printf '| `%s` | `%s` |\n' "$relative" "$digest"
    done < <(find "$BACKEND_ROOT/tests/fixtures/localization" -name manifest.json -type f -print | sort)
    printf '%s\n' '' '## Boundary Proof' '' \
      '- The complete four-format parser package passed with the configured 100% statement and branch threshold.' \
      '- The exact supported/rejected category manifests passed the named equality test.' \
      '- Dependency vulnerability and repository license policy checks passed before either flagged dependency was installed.' \
      '- A unique disposable Compose stack returned one Celery ping response and byte-equal, nonempty backend/worker canonical digests.' \
      '- The container parser probes ran with SQLAlchemy persistence methods fail-closed and reported zero persistence writes.' \
      '- Runtime logs and result records passed seeded-secret, credential-shape, and source-body scans before complete cleanup.'
  } >"$evidence_tmp"
  chmod 644 "$evidence_tmp"

  for secret in "$SMOKE_CLIENT_SECRET" "$SMOKE_JWT_SECRET" "$SMOKE_KEYRING" "$SMOKE_SOURCE"; do
    if [ -n "$secret" ] && grep -Fq -- "$secret" "$evidence_tmp"; then
      die "generated evidence exposed seeded secret or source material"
    fi
  done
  if grep -Eiq \
    '(<resources|checkpoint\.scalar|authorization:[[:space:]]*(bearer|basic)|client_secret[=:][^[:space:]]|access_token[=:][^[:space:]]|refresh_token[=:][^[:space:]]|gAAAAA[A-Za-z0-9_-]+|Traceback|Exception)' \
    "$evidence_tmp"; then
    die "generated evidence contains a forbidden secret, source, or exception surface"
  fi
  mv "$evidence_tmp" "$EVIDENCE_PATH"
}

verify_evidence() {
  [ -s "$EVIDENCE_PATH" ] || die "parser evidence is missing"
  [ ! -L "$EVIDENCE_PATH" ] || die "parser evidence must not be a symbolic link"
  "$BACKEND_ROOT/.venv/bin/python" - "$EVIDENCE_PATH" "$REPO_ROOT" <<'PY'
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

evidence_path = Path(sys.argv[1])
repository = Path(sys.argv[2])
text = evidence_path.read_text(encoding="utf-8")

required = {
    "# Phase 04 Parser Checkpoint Evidence",
    "- Gate-status: PASS",
    "- Persistence-authority: NOT STARTED",
    "- Flagged-package-installation: ABSENT",
    "- Worker-ping-responses: 1",
    "- Backend-value-count: 1",
    "- Worker-value-count: 1",
    "- Persistence-writes: 0",
    "- Secret-scan: PASS",
    "- Source-body-scan: PASS",
    "- Cleanup: PASS",
}
assert required <= set(text.splitlines())
parser_count = re.search(r"(?m)^- Parser-test-count: ([1-9][0-9]*)$", text)
license_count = re.search(r"(?m)^- Approved-third-party-license-count: ([1-9][0-9]*)$", text)
assert parser_count and license_count
backend = re.search(r"(?m)^- Backend-canonical-digest: ([0-9a-f]{64})$", text)
worker = re.search(r"(?m)^- Worker-canonical-digest: ([0-9a-f]{64})$", text)
image = re.search(r"(?m)^- Runtime-image-digest: ([0-9a-f]{64})$", text)
assert backend and worker and image and backend.group(1) == worker.group(1)

command_rows = re.findall(
    r"^\| [^|]+ \| `[^`]+` \| ([0-9]+) \| ([0-9]+) \| ([0-9]+|-) \| `([0-9a-f]{64})` \|$",
    text,
    re.MULTILINE,
)
assert len(command_rows) == 10
assert all(return_code == "0" for _, return_code, _, _ in command_rows)

manifest_rows = re.findall(
    r"^\| `(backend/tests/fixtures/localization/[^`]+/manifest\.json)` \| `([0-9a-f]{64})` \|$",
    text,
    re.MULTILINE,
)
assert len(manifest_rows) == 5
for relative, recorded in manifest_rows:
    source = repository / relative
    assert source.is_file()
    assert hashlib.sha256(source.read_bytes()).hexdigest() == recorded

assert not re.search(
    r"<resources|checkpoint\.scalar|authorization:\s*(?:bearer|basic)|"
    r"client_secret\s*[=:]|access_token\s*[=:]|refresh_token\s*[=:]|"
    r"gAAAAA[A-Za-z0-9_-]+|Traceback|Exception",
    text,
    re.IGNORECASE,
)
print(
    "evidence-verification: PASS "
    f"commands={len(command_rows)} manifests={len(manifest_rows)} "
    f"evidence_sha256={hashlib.sha256(text.encode()).hexdigest()}"
)
PY
}

run_full_checkpoint() {
  preflight
  HOST_RUNTIME_DIR=$(mktemp -d /tmp/verboflex-phase04-parser-host.XXXXXX)
  chmod 700 "$HOST_RUNTIME_DIR"
  RECORDS_FILE="$HOST_RUNTIME_DIR/records.tsv"
  LICENSE_FILE="$HOST_RUNTIME_DIR/python-licenses.json"
  export COVERAGE_FILE="$HOST_RUNTIME_DIR/coverage-data"
  : >"$RECORDS_FILE"
  chmod 600 "$RECORDS_FILE"
  collect_versions

  record_command parser-coverage "Parser package branch coverage" \
    "uv run --project backend pytest backend/tests/unit/localization/importing --cov=verboflex.localization.importing --cov-branch --cov-report=term-missing --cov-fail-under=100 -q" \
    uv run --project "$BACKEND_ROOT" pytest "$BACKEND_ROOT/tests/unit/localization/importing" \
      --cov=verboflex.localization.importing --cov-branch --cov-report=term-missing \
      --cov-fail-under=100 -q
  record_command ruff-format "Parser Ruff format" \
    "uv run --project backend ruff format --check backend/src/verboflex/localization/importing backend/tests/unit/localization/importing" \
    uv run --project "$BACKEND_ROOT" ruff format --check \
      "$BACKEND_ROOT/src/verboflex/localization/importing" \
      "$BACKEND_ROOT/tests/unit/localization/importing"
  record_command ruff-lint "Parser Ruff lint" \
    "uv run --project backend ruff check backend/src/verboflex/localization/importing backend/tests/unit/localization/importing" \
    uv run --project "$BACKEND_ROOT" ruff check \
      "$BACKEND_ROOT/src/verboflex/localization/importing" \
      "$BACKEND_ROOT/tests/unit/localization/importing"
  record_command mypy "Parser mypy" \
    "uv run --project backend mypy backend/src/verboflex/localization/importing" \
    uv run --project "$BACKEND_ROOT" mypy "$BACKEND_ROOT/src/verboflex/localization/importing"
  record_command pip-audit "Python dependency audit" \
    "uv run --project backend pip-audit" \
    uv run --project "$BACKEND_ROOT" pip-audit
  record_command python-licenses "Python license inventory" \
    "uv run --project backend pip-licenses --format=json --with-urls" \
    uv run --project "$BACKEND_ROOT" pip-licenses --format=json --with-urls
  cp "$LAST_OUTPUT" "$LICENSE_FILE"
  chmod 600 "$LICENSE_FILE"
  record_command license-policy "Repository Python license policy" \
    "bash tools/phase4_parser_checkpoint.sh --license-policy [owner-only inventory]" \
    license_policy "$LICENSE_FILE"
  record_command flagged-absence "Flagged package absence" \
    "repository manifests exclude regex==2026.9.3 and @tanstack/react-virtual==3.14.10" \
    assert_flagged_packages_absent
  record_command manifest-equality "Conformance manifest equality" \
    "uv run --project backend pytest backend/tests/unit/localization/importing/test_conformance.py::test_fixture_manifest_category_equality -q" \
    uv run --project "$BACKEND_ROOT" pytest \
      "$BACKEND_ROOT/tests/unit/localization/importing/test_conformance.py::test_fixture_manifest_category_equality" -q
  record_command container-smoke "Backend and worker parser container smoke" \
    "bash tools/phase4_parser_checkpoint.sh --container-smoke" \
    container_smoke

  write_evidence
  verify_evidence
  printf 'phase4 complete parser checkpoint: PASS\n'
}

trap cleanup_all EXIT INT TERM

case "${1:-}" in
  --run)
    [ "$#" -eq 1 ] || die "--run accepts no additional arguments"
    run_full_checkpoint
    ;;
  --license-policy)
    [ "$#" -eq 2 ] || die "--license-policy requires one inventory path"
    license_policy "$2"
    ;;
  --container-smoke)
    [ "$#" -eq 1 ] || die "--container-smoke accepts no additional arguments"
    preflight
    container_smoke
    ;;
  --verify-evidence)
    [ "$#" -eq 1 ] || die "--verify-evidence accepts no additional arguments"
    verify_evidence
    ;;
  *)
    die "usage: tools/phase4_parser_checkpoint.sh --run|--license-policy PATH|--container-smoke|--verify-evidence"
    ;;
esac

trap - EXIT INT TERM
cleanup_all

#!/usr/bin/env bash
set -euo pipefail
umask 077
if [ "$#" -gt 1 ]; then printf 'phase4 smoke: unknown option\n' >&2; exit 2; fi
case "${1:-}" in
  --dry-run)
    printf '%s\n' \
      'Phase 4 disposable Compose smoke: postgres redis backend worker frontend mock-bitbucket (TLS).' \
      'Build application images; unique project, volumes, image tags and loopback ports.' \
      'Anonymous temporary Docker client; current Dockerfiles use bundled BuildKit, every external command capped at 600 seconds.' \
      'Provision pg_trgm only in the new isolated smoke database before Alembic upgrade head.' \
      'Health: API/frontend/worker at most 180 seconds; each import at most 120 seconds.' \
      'Queue four UUID-only jobs with worker paused; inspect exact broker args then resume worker.' \
      'Fixtures: android_xml qt_ts json ios_strings; canonical import through production API and Celery.' \
      'Real search/detail and constraint PUT/DELETE: four roles, anonymous denial, version conflict.' \
      'Built browser: login, search, detail, constraint create/remove, Back focus, direct-route reload.' \
      'Redaction: fixed stage/count output; private logs destroyed, no source or credentials printed.' \
      'Trap cleanup: compose down --volumes --remove-orphans --timeout 10 for owned project only; remove owned images and temporary files.'
    exit 0 ;;
  '') ;;
  *) printf 'phase4 smoke: unknown option\n' >&2; exit 2 ;;
esac
PHASE4_SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
# Phase 3 owns the audited TLS, unique resource, Compose and cleanup lifecycle.
# Load its function library without executing its command dispatcher.
eval "$(sed '/^case "${1:-}:${2:-}" in/,$d' "$PHASE4_SCRIPT_DIR/phase3_smoke.sh")"
compose() {
  "$BACKEND_ROOT/.venv/bin/python" "$PHASE4_SCRIPT_DIR/phase4_smoke.py" bounded \
    docker compose --project-name "$SMOKE_PROJECT" --env-file "$SMOKE_ENV_FILE" \
    -f "$REPO_ROOT/docker-compose.yml" -f "$SMOKE_OVERRIDE_FILE" \
    -f "$SMOKE_RUNTIME_DIR/build.json" "$@"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
initialize_runtime
configure_compose
# Public pinned images require no registry credentials. Scope client auth to
# this run so a desktop keychain prompt cannot hang automated smoke builds.
PHASE4_DOCKER_HOST=${DOCKER_HOST:-$(docker context inspect --format '{{.Endpoints.docker.Host}}')}
PHASE4_DOCKER_CONFIG=${DOCKER_CONFIG:-$HOME/.docker}
"$BACKEND_ROOT/.venv/bin/python" - "$SMOKE_RUNTIME_DIR" "$PHASE4_DOCKER_CONFIG" <<'PY'
import json, sys
from pathlib import Path
runtime, original = map(Path, sys.argv[1:])
target = runtime / "docker-config"
target.mkdir(mode=0o700)
plugins = [str(original / "cli-plugins")]
config = original / "config.json"
if config.is_file():
    plugins.extend(json.loads(config.read_text()).get("cliPluginsExtraDirs", []))
(target / "config.json").write_text(json.dumps({"auths": {}, "cliPluginsExtraDirs": plugins}))
PY
export DOCKER_HOST="$PHASE4_DOCKER_HOST"
export DOCKER_CONFIG="$SMOKE_RUNTIME_DIR/docker-config"
unset DOCKER_CONTEXT
# These Dockerfiles use no external frontend-only features. Docker's bundled
# BuildKit frontend avoids a registry lookup for the syntax image while building
# the exact current source, lockfiles, stages and pinned base images.
"$BACKEND_ROOT/.venv/bin/python" - "$REPO_ROOT" "$SMOKE_RUNTIME_DIR" <<'PY'
import json, sys
from pathlib import Path
root, runtime = map(Path, sys.argv[1:])
services = {}
for name in ("backend", "frontend"):
    source = (root / "docker" / (name + ".Dockerfile")).read_text()
    assert source.startswith("# syntax=docker/dockerfile:1.8\n")
    target = runtime / (name + ".Dockerfile")
    target.write_text(source.split("\n", 1)[1])
    services[name] = {"build": {"dockerfile": str(target)}}
(runtime / "build.json").write_text(json.dumps({"services": services}))
PY
PHASE4_STARTED=$SECONDS
PHASE4_STAGE=preflight
die() { printf 'phase4 smoke failed: %s\n' "$PHASE4_STAGE" >&2; exit 1; }
step() {
  PHASE4_STAGE=$1; shift
  if ! "$@" >"$SMOKE_RUNTIME_DIR/step.log" 2>&1; then
    "$BACKEND_ROOT/.venv/bin/python" - "$SMOKE_RUNTIME_DIR/step.log" <<'PY'
import re, sys
from pathlib import Path
data = Path(sys.argv[1]).read_text(errors="replace")
for term in ("No space left", "ENOSPC", "network", "certificate", "not found", "npm ci", "uv sync", "tsc", "TypeScript", "permission denied", "unhealthy", "exit code: 1", "exit code: 2", "credentials", "context deadline exceeded", "connection refused", "failed to solve"):
    if term.lower() in data.lower():
        print("phase4 failure category: " + term, file=sys.stderr)
for stage in re.findall(r"^phase4 smoke failed: ([a-zA-Z0-9_-]+)$", data, re.M):
    print("phase4 driver stage: " + stage, file=sys.stderr)
PY
    die "$PHASE4_STAGE"
  fi
  printf 'phase4 smoke %s: PASS\n' "$PHASE4_STAGE"
}
step preflight preflight
cp "$SMOKE_PROVIDER_SCRIPT" "$SMOKE_RUNTIME_DIR/phase3_provider_base.py"
cp "$PHASE4_SCRIPT_DIR/phase4_smoke.py" "$SMOKE_PROVIDER_SCRIPT"
"$BACKEND_ROOT/.venv/bin/python" - "$SMOKE_PROVIDER_CONTROL_FILE" <<'PY'
import json, sys
from pathlib import Path
Path(sys.argv[1]).write_text(json.dumps({"faults": {}, "heads": {"phase4-" + name: "1" * 40 for name in ("android_xml", "qt_ts", "json", "ios_strings")}}))
PY
step build compose build backend frontend
step infrastructure compose up -d --wait --wait-timeout 180 postgres redis mock-bitbucket
# This fresh project volume is the ONLY database changed by smoke infrastructure.
step extension compose exec -T postgres psql -U verboflex -d verboflex -v ON_ERROR_STOP=1 -c 'CREATE EXTENSION pg_trgm'
step migrations compose run --rm -T backend alembic upgrade head
step applications compose up -d --wait --wait-timeout 180 backend worker frontend
step api-health wait_for_url "$SMOKE_BACKEND_URL/api/v1/health" 200 backend
step frontend-health wait_for_url "$SMOKE_FRONTEND_URL/login" 200 frontend
step worker-health wait_for_worker
PHASE4_STAGE=seed
compose exec -T -e PHASE4_DISPOSABLE=1 backend python -c "$(<"$PHASE4_SCRIPT_DIR/phase4_smoke.py")" seed >"$SMOKE_RUNTIME_DIR/fixture.json" 2>"$SMOKE_RUNTIME_DIR/seed.err" || die seed
step worker-pause compose stop --timeout 10 worker
step enqueue "$BACKEND_ROOT/.venv/bin/python" "$PHASE4_SCRIPT_DIR/phase4_smoke.py" bounded node "$PHASE4_SCRIPT_DIR/phase4_smoke_browser.mjs" enqueue "$SMOKE_RUNTIME_DIR/fixture.json" "$SMOKE_BACKEND_URL" "$SMOKE_FRONTEND_URL"
PHASE4_STAGE=queue-boundary
"$BACKEND_ROOT/.venv/bin/python" -c 'import json,sys; print(json.dumps([m["job"] for m in json.load(open(sys.argv[1]))["mappings"]]))' "$SMOKE_RUNTIME_DIR/fixture.json" |
  compose exec -T backend python -c "$(<"$PHASE4_SCRIPT_DIR/phase4_smoke.py")" queue >"$SMOKE_RUNTIME_DIR/queue.log" 2>&1 || die queue
printf 'phase4 smoke queue-boundary: PASS (UUID-only jobs=4)\n'
step preview-authority compose exec -T backend python -c "$(<"$PHASE4_SCRIPT_DIR/phase4_smoke.py")" authority
step worker-resume compose start worker
step browser "$BACKEND_ROOT/.venv/bin/python" "$PHASE4_SCRIPT_DIR/phase4_smoke.py" bounded node "$PHASE4_SCRIPT_DIR/phase4_smoke_browser.mjs" verify "$SMOKE_RUNTIME_DIR/fixture.json" "$SMOKE_BACKEND_URL" "$SMOKE_FRONTEND_URL"
step provider-audit "$BACKEND_ROOT/.venv/bin/python" "$PHASE4_SCRIPT_DIR/phase4_smoke.py" audit "$SMOKE_PROVIDER_AUDIT_FILE"
step redis-redaction verify_redis_boundary
step redis-content compose exec -T backend python -c "$(<"$PHASE4_SCRIPT_DIR/phase4_smoke.py")" redis-content
step log-redaction verify_no_sensitive_surfaces
step cleanup cleanup
trap - EXIT INT TERM
printf 'phase4 deployment-like smoke: PASS (formats=4, roles=4, duration_seconds=%s, cleanup=PASS)\n' "$((SECONDS - PHASE4_STARTED))"

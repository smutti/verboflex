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
# Closed Phase 6 profile shares only this audited build/runtime lifecycle.
PHASE4_DRIVER="$PHASE4_SCRIPT_DIR/phase4_smoke.py"
PHASE4_BROWSER="$PHASE4_SCRIPT_DIR/phase4_smoke_browser.mjs"
PHASE4_SEED_SERVICE=backend
PHASE4_JOB_COUNT=4
case "${PHASE4_PROFILE:-4}" in
  4) ;;
  6|7) PHASE4_DRIVER="$PHASE4_SCRIPT_DIR/phase6_smoke.py"
     PHASE4_BROWSER="$PHASE4_SCRIPT_DIR/phase6_smoke_browser.mjs"
     PHASE4_SEED_SERVICE=worker
     PHASE4_JOB_COUNT=5 ;;
  *) printf 'phase4 smoke: unknown profile\n' >&2; exit 2 ;;
esac
# Phase 3 owns the audited TLS, unique resource, Compose and cleanup lifecycle.
# Load its function library without executing its command dispatcher.
eval "$(sed '/^case "${1:-}:${2:-}" in/,$d' "$PHASE4_SCRIPT_DIR/phase3_smoke.sh")"
compose() {
  "$BACKEND_ROOT/.venv/bin/python" "$PHASE4_SCRIPT_DIR/phase4_smoke.py" bounded \
    docker compose --project-name "$SMOKE_PROJECT" --env-file "$SMOKE_ENV_FILE" \
    -f "$REPO_ROOT/docker-compose.yml" -f "$SMOKE_OVERRIDE_FILE" "$@"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
initialize_runtime
if [ "${PHASE4_PROFILE:-4}" = 7 ]; then
  # Full write verification includes bounded read-after-write checks. Only this
  # owned stack receives the longer worker limits; the crash test kills it.
  "$BACKEND_ROOT/.venv/bin/python" - "$SMOKE_ENV_FILE" <<'PY'
import sys
from pathlib import Path
p = Path(sys.argv[1])
p.write_text(p.read_text().replace("SOFT_TIME_LIMIT_SECONDS=8", "SOFT_TIME_LIMIT_SECONDS=60").replace("HARD_TIME_LIMIT_SECONDS=10", "HARD_TIME_LIMIT_SECONDS=90"))
PY
fi
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
# Build the checked-in Dockerfiles inside the repository context. Modern Bake
# requires extra filesystem entitlements for temporary Dockerfiles outside it.
# Keeping the real files also exercises the same build used by installations.
PHASE4_STARTED=$SECONDS
PHASE4_STAGE=preflight
die() { printf 'phase4 smoke failed: %s\n' "$PHASE4_STAGE" >&2; exit 1; }
step() {
  PHASE4_STAGE=$1; shift
  if ! "$@" >"$SMOKE_RUNTIME_DIR/step.log" 2>&1; then
    "$BACKEND_ROOT/.venv/bin/python" - "$SMOKE_RUNTIME_DIR/step.log" "$SMOKE_ENV_FILE" "$PHASE4_STAGE" <<'PY'
import re, sys
from pathlib import Path
data = Path(sys.argv[1]).read_text(errors="replace")
# Build output contains no application requests. Redact every generated runtime
# value before emitting a bounded diagnostic; never dump Compose config or logs.
if sys.argv[3] in {"build-backend", "build-frontend"}:
    safe = data
    for line in Path(sys.argv[2]).read_text().splitlines():
        if "=" in line:
            value = line.split("=", 1)[1].strip().strip("\"'")
            if len(value) >= 8:
                safe = safe.replace(value, "[redacted]")
    print("\n".join(safe.splitlines()[-30:])[-8000:], file=sys.stderr)
for term in ("No space left", "ENOSPC", "network", "certificate", "not found", "npm ci", "uv sync", "tsc", "TypeScript", "permission denied", "unhealthy", "no healthcheck", "healthcheck is disabled", "dependency failed", "is not running", "already in use", "already allocated", "pull access denied", "manifest unknown", "invalid", "unknown flag", "no such", "exit code: 1", "exit code: 2", "credentials", "context deadline exceeded", "connection refused", "failed to solve", "buildx", "bake", "requires", "unsupported", "outside", "stat "):
    if term.lower() in data.lower():
        print("phase4 failure category: " + term, file=sys.stderr)
for stage in re.findall(r"^phase4 smoke failed: ([a-zA-Z0-9_-]+)$", data, re.M):
    print("phase4 driver stage: " + stage, file=sys.stderr)
for stage in re.findall(r"^phase5 smoke failed: ([a-zA-Z0-9_-]+)$", data, re.M):
    print("phase5 driver stage: " + stage, file=sys.stderr)
for stage in re.findall(r"^phase6 (?:smoke|driver) failed: ([a-zA-Z0-9_-]+)$", data, re.M):
    print("phase6 driver failed: " + stage, file=sys.stderr)
for stage in re.findall(r"^phase7 smoke failed: ([a-zA-Z0-9_-]+)$", data, re.M):
    print("phase7 driver failed: " + stage, file=sys.stderr)
PY
    die "$PHASE4_STAGE"
  fi
  printf 'phase4 smoke %s: PASS\n' "$PHASE4_STAGE"
}
step preflight preflight
cp "$SMOKE_PROVIDER_SCRIPT" "$SMOKE_RUNTIME_DIR/phase3_provider_base.py"
cp "$PHASE4_DRIVER" "$SMOKE_PROVIDER_SCRIPT"
if [ "${PHASE4_PROFILE:-4}" = 7 ]; then
  cp "$PHASE4_SCRIPT_DIR/phase7_mock_provider.py" "$SMOKE_PROVIDER_SCRIPT"
  cp "$PHASE4_SCRIPT_DIR/phase6_smoke.py" "$SMOKE_RUNTIME_DIR/phase6_smoke.py"
fi
if [ "${PHASE4_PROFILE:-4}" = 6 ] || [ "${PHASE4_PROFILE:-4}" = 7 ]; then
  "$BACKEND_ROOT/.venv/bin/python" "$PHASE4_DRIVER" control "$SMOKE_PROVIDER_CONTROL_FILE" reset
else
"$BACKEND_ROOT/.venv/bin/python" - "$SMOKE_PROVIDER_CONTROL_FILE" <<'PY'
import json, sys
from pathlib import Path
Path(sys.argv[1]).write_text(json.dumps({"faults": {}, "heads": {"phase4-" + name: "1" * 40 for name in ("android_xml", "qt_ts", "json", "ios_strings")}}))
PY
fi
# Build sequentially so a cold npm registry response cannot consume the shared
# 600-second budget while uv is also resolving. Each image remains bounded by
# the audited command cap and is still tagged to this unique smoke project.
step build-backend compose build backend
step build-frontend compose build frontend
step infrastructure compose up -d --wait --wait-timeout 180 postgres redis mock-bitbucket
# This fresh project volume is the ONLY database changed by smoke infrastructure.
step extension compose exec -T postgres psql -U verboflex -d verboflex -v ON_ERROR_STOP=1 -c 'CREATE EXTENSION pg_trgm'
step migrations compose run --rm -T backend alembic upgrade head
step applications compose up -d --wait --wait-timeout 180 backend worker frontend
step api-health wait_for_url "$SMOKE_BACKEND_URL/api/v1/health" 200 backend
step frontend-health wait_for_url "$SMOKE_FRONTEND_URL/login" 200 frontend
step worker-health wait_for_worker
PHASE4_STAGE=seed
compose exec -T -e PHASE4_DISPOSABLE=1 -e PHASE8_HTTP_SETUP="${PHASE8_HTTP_SETUP:-0}" "$PHASE4_SEED_SERVICE" python -c "$(<"$PHASE4_DRIVER")" seed >"$SMOKE_RUNTIME_DIR/fixture.json" 2>"$SMOKE_RUNTIME_DIR/seed.err" || {
  sed -n '/^phase6 driver failed: [a-zA-Z0-9_-]*$/p' "$SMOKE_RUNTIME_DIR/seed.err" >&2
  die seed
}
step worker-pause compose stop --timeout 10 worker
step enqueue "$BACKEND_ROOT/.venv/bin/python" "$PHASE4_SCRIPT_DIR/phase4_smoke.py" bounded node "$PHASE4_BROWSER" enqueue "$SMOKE_RUNTIME_DIR/fixture.json" "$SMOKE_BACKEND_URL" "$SMOKE_FRONTEND_URL"
PHASE4_STAGE=queue-boundary
"$BACKEND_ROOT/.venv/bin/python" -c 'import json,sys; print(json.dumps([m["job"] for m in json.load(open(sys.argv[1]))["mappings"]]))' "$SMOKE_RUNTIME_DIR/fixture.json" |
  compose exec -T backend python -c "$(<"$PHASE4_DRIVER")" queue >"$SMOKE_RUNTIME_DIR/queue.log" 2>&1 || die queue
printf 'phase4 smoke queue-boundary: PASS (UUID-only jobs=%s)\n' "$PHASE4_JOB_COUNT"
step preview-authority compose exec -T backend python -c "$(<"$PHASE4_DRIVER")" authority
step worker-resume compose start worker
step browser "$BACKEND_ROOT/.venv/bin/python" "$PHASE4_SCRIPT_DIR/phase4_smoke.py" bounded node "$PHASE4_BROWSER" verify "$SMOKE_RUNTIME_DIR/fixture.json" "$SMOKE_BACKEND_URL" "$SMOKE_FRONTEND_URL"
if [ "${PHASE4_PROFILE:-4}" = 7 ]; then
  step driver-copy compose cp "$PHASE4_SCRIPT_DIR/phase7_smoke.py" backend:/tmp/phase7_smoke.py
  step fixture-copy compose cp "$PHASE4_SCRIPT_DIR/phase6_smoke.py" backend:/tmp/phase6_smoke.py
  "$BACKEND_ROOT/.venv/bin/python" "$PHASE4_SCRIPT_DIR/phase7_smoke.py" configure "$SMOKE_RUNTIME_DIR/fixture.json" "$SMOKE_PROJECT" "$SMOKE_ENV_FILE" "$SMOKE_OVERRIDE_FILE" "$SMOKE_BACKEND_URL" "$SMOKE_FRONTEND_URL"
fi
if [ "${PHASE4_PROFILE:-4}" = 6 ]; then
  worker_verify() {
    compose exec -T worker python -c "$(<"$PHASE4_DRIVER")" "$1" <"$SMOKE_RUNTIME_DIR/fixture.json" >"$SMOKE_RUNTIME_DIR/worker-$1.json"
  }
  step worker-prepare worker_verify prepare
  for scenario in stale-direct stale-keys tamper markup; do
    "$BACKEND_ROOT/.venv/bin/python" "$PHASE4_DRIVER" control "$SMOKE_PROVIDER_CONTROL_FILE" "$scenario"
    step "worker-$scenario" worker_verify "$scenario"
  done
  "$BACKEND_ROOT/.venv/bin/python" "$PHASE4_DRIVER" control "$SMOKE_PROVIDER_CONTROL_FILE" reset
  step worker-duplicate compose exec -T worker python -c "$(<"$PHASE4_DRIVER")" duplicate
fi
if [ -n "${PHASE4_BROWSER_EXTENSION:-}" ]; then
  case "$PHASE4_BROWSER_EXTENSION" in
    "$PHASE4_SCRIPT_DIR"/*) ;;
    *) die browser-extension-path ;;
  esac
  step browser-extension "$BACKEND_ROOT/.venv/bin/python" "$PHASE4_SCRIPT_DIR/phase4_smoke.py" bounded node "$PHASE4_BROWSER_EXTENSION" verify "$SMOKE_RUNTIME_DIR/fixture.json" "$SMOKE_BACKEND_URL" "$SMOKE_FRONTEND_URL"
fi
if [ "${PHASE4_PROFILE:-4}" = 7 ]; then
  step happy-oracle "$BACKEND_ROOT/.venv/bin/python" "$PHASE4_SCRIPT_DIR/phase7_smoke.py" happy-oracle "$SMOKE_RUNTIME_DIR/fixture.json"
  start_smoke_scheduler() {
    # Compose 2.38 rejects --wait for this intentionally non-HTTP service.
    # Dependencies are already verified; require a running container and Beat's
    # initialized persistent schedule before testing real scheduled recovery.
    compose up -d --no-deps scheduler || return 1
    local deadline=$((SECONDS + 180))
    while [ "$SECONDS" -lt "$deadline" ]; do
      if compose exec -T scheduler python -c 'from pathlib import Path; assert any(p.is_file() and p.stat().st_size > 0 for p in Path("/tmp").glob("celerybeat-schedule*"))'; then
        return 0
      fi
      sleep 1
    done
    return 1
  }
  step scheduler start_smoke_scheduler
  step fault-scenarios "$BACKEND_ROOT/.venv/bin/python" "$PHASE4_SCRIPT_DIR/phase4_smoke.py" bounded "$BACKEND_ROOT/.venv/bin/python" "$PHASE4_SCRIPT_DIR/phase7_smoke.py" faults "$SMOKE_RUNTIME_DIR/fixture.json"
  step provider-audit "$BACKEND_ROOT/.venv/bin/python" "$PHASE4_SCRIPT_DIR/phase7_smoke.py" audit "$SMOKE_RUNTIME_DIR/fixture.json"
else
  step provider-audit "$BACKEND_ROOT/.venv/bin/python" "$PHASE4_DRIVER" audit "$SMOKE_PROVIDER_AUDIT_FILE"
fi
step redis-redaction verify_redis_boundary
step redis-content compose exec -T backend python -c "$(<"$PHASE4_DRIVER")" redis-content
step log-redaction verify_no_sensitive_surfaces
if [ "${PHASE4_PROFILE:-4}" = 6 ]; then
  PHASE6_EVIDENCE=$("$BACKEND_ROOT/.venv/bin/python" - "$SMOKE_RUNTIME_DIR" <<'PY'
import json, sys
from pathlib import Path
runtime = Path(sys.argv[1])
proof = json.loads((runtime / "worker-prepare.json").read_text())
for name, key in (("stale-direct", "stale_direct"), ("stale-keys", "stale_keys"), ("tamper", "tampered_file"), ("markup", "mixed_markup")):
    result = json.loads((runtime / f"worker-{name}.json").read_text())
    assert result[name] is True and result["localization_unchanged"] is True
    proof[key] = True
proof.update(duplicate_snapshot=True, resource_mutations=0, cleanup=True)
print(json.dumps(proof, sort_keys=True))
PY
  )
fi
if [ "${PHASE4_PROFILE:-4}" = 7 ]; then
  PHASE7_EVIDENCE=$("$BACKEND_ROOT/.venv/bin/python" "$PHASE4_SCRIPT_DIR/phase7_smoke.py" evidence "$SMOKE_RUNTIME_DIR/fixture.json")
fi
step cleanup cleanup
trap - EXIT INT TERM
if [ "${PHASE4_PROFILE:-4}" = 7 ]; then
  printf 'phase7 evidence: %s\n' "$PHASE7_EVIDENCE"
elif [ "${PHASE4_PROFILE:-4}" = 6 ]; then
  printf 'phase6 evidence: %s\n' "$PHASE6_EVIDENCE"
else
  printf 'phase4 deployment-like smoke: PASS (formats=4, roles=4, duration_seconds=%s, cleanup=PASS)\n' "$((SECONDS - PHASE4_STARTED))"
fi

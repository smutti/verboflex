#!/usr/bin/env bash
set -euo pipefail
ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
exec "$ROOT/backend/.venv/bin/python" "$ROOT/tools/phase5_gate.py" run "$@"

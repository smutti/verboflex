#!/usr/bin/env bash
set -euo pipefail
umask 077
PHASE7_GATE_ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
cd "$PHASE7_GATE_ROOT"
exec "$PHASE7_GATE_ROOT/backend/.venv/bin/python" tools/phase7_gate.py run

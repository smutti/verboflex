#!/usr/bin/env bash
set -euo pipefail

repo_root=$(git rev-parse --show-toplevel)
output_file=$(mktemp)
trap 'rm -f "$output_file"' EXIT

if ! "$repo_root/tools/real_smoke.sh" --preflight >"$output_file" 2>&1; then
  printf 'expected real-smoke preflight to pass; output follows:\n' >&2
  sed -n '1,120p' "$output_file" >&2
  exit 1
fi

grep -Fq 'real smoke preflight: PASS' "$output_file"

for overlay in docker-compose.staging.yml docker-compose.prod.yml; do
  VERBOFLEX_POSTGRES_PASSWORD=fixture \
  VERBOFLEX_JWT_SECRET_KEY=fixture \
  VITE_API_BASE_URL=https://api.example.invalid \
    docker compose -f "$repo_root/docker-compose.yml" -f "$repo_root/$overlay" \
      config --format json >"$output_file"
  python3 -c \
    'import json,sys; d=json.load(open(sys.argv[1])); assert all(len(d["services"][s]["ports"]) == 1 and d["services"][s]["ports"][0].get("host_ip") == "127.0.0.1" for s in ("backend","frontend"))' \
    "$output_file"
done

grep -Fq 'TLS termination boundary' "$repo_root/docs/phase-01-smoke.md"

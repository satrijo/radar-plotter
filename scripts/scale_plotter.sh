#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MIN_REPLICAS="${MIN_REPLICAS:-1}"
MAX_REPLICAS="${MAX_REPLICAS:-3}"
SCALE_UP_LAG="${SCALE_UP_LAG:-50}"
SCALE_MAX_LAG="${SCALE_MAX_LAG:-100}"
SCALE_DOWN_LAG="${SCALE_DOWN_LAG:-20}"

lag="$(docker exec radar-redis redis-cli --raw XINFO GROUPS radar:jobs | awk '
  previous == "lag" { print; exit }
  { previous = $0 }
')"
lag="${lag:-0}"
if ! [[ "$lag" =~ ^[0-9]+$ ]]; then
  echo "invalid Redis lag: $lag" >&2
  exit 1
fi

if (( lag >= SCALE_MAX_LAG )); then
  desired="$MAX_REPLICAS"
elif (( lag >= SCALE_UP_LAG )); then
  desired=2
elif (( lag <= SCALE_DOWN_LAG )); then
  desired="$MIN_REPLICAS"
else
  desired=2
fi

current="$(docker compose ps -q radar-plotter | wc -l | tr -d ' ')"
echo "plotter lag=$lag current=$current desired=$desired"
if [[ "$current" != "$desired" ]]; then
  docker compose up -d --no-build --scale radar-plotter="$desired" radar-plotter
fi

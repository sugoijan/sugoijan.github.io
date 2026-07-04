#!/usr/bin/env sh

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PORT="${1:-8000}"

python3 "$ROOT/scripts/build.py"
exec python3 -m http.server "$PORT" --bind 127.0.0.1 --directory "$ROOT"

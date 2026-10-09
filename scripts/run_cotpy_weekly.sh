#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${COTPY_PROJECT_DIR:-/Users/fox/Private/Projects/cotpy}"
PYTHON="${COTPY_PYTHON:-$PROJECT_DIR/.venv/bin/python}"
mkdir -p "$PROJECT_DIR/logs" "$PROJECT_DIR/.cache/matplotlib"
export MPLCONFIGDIR="$PROJECT_DIR/.cache/matplotlib"
export PYTHONUNBUFFERED=1
cd "$PROJECT_DIR"
# Keep unattended network requests moving while the Mac would otherwise idle
# to sleep. caffeinate releases its assertion when the child exits.
if [[ "$(uname -s)" == "Darwin" ]]; then
  exec /usr/bin/caffeinate -i "$PYTHON" scripts/run_cotpy_weekly.py >> "$PROJECT_DIR/logs/weekly.log" 2>&1
fi
exec "$PYTHON" scripts/run_cotpy_weekly.py >> "$PROJECT_DIR/logs/weekly.log" 2>&1

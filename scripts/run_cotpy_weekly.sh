#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${COTPY_PROJECT_DIR:-/Users/fox/Private/Projects/cotpy}"
PYTHON="${COTPY_PYTHON:-$PROJECT_DIR/.venv/bin/python}"
mkdir -p "$PROJECT_DIR/logs" "$PROJECT_DIR/.cache/matplotlib"
export MPLCONFIGDIR="$PROJECT_DIR/.cache/matplotlib"
export PYTHONUNBUFFERED=1
cd "$PROJECT_DIR"
exec "$PYTHON" scripts/run_cotpy_weekly.py >> "$PROJECT_DIR/logs/weekly.log" 2>&1

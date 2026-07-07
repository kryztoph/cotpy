#!/bin/sh
set -eu

PROJECT_DIR="${COTPY_PROJECT_DIR:-/Users/fox/Private/Projects/cotpy}"
PYTHON_BIN="${COTPY_PYTHON:-$PROJECT_DIR/.venv/bin/python}"

cd "$PROJECT_DIR"
exec "$PYTHON_BIN" scripts/publish_to_csfox_gh.py

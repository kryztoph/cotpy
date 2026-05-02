#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/Users/fox/Private/Projects/cotpy"
PYTHON="$PROJECT_DIR/.venv/bin/python"
LOG_DIR="$PROJECT_DIR/logs"
LOCK_DIR="$PROJECT_DIR/.cotpy-weekly.lock"
MPLCONFIGDIR="$PROJECT_DIR/.cache/matplotlib"

mkdir -p "$LOG_DIR"
mkdir -p "$MPLCONFIGDIR"
export MPLCONFIGDIR

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "$(date '+%Y-%m-%d %H:%M:%S %Z') cotpy weekly job already running"
  exit 0
fi
trap 'rmdir "$LOCK_DIR"' EXIT

cd "$PROJECT_DIR"

{
  echo "================================================================"
  echo "$(date '+%Y-%m-%d %H:%M:%S %Z') starting cotpy weekly refresh"
  echo "Project: $PROJECT_DIR"
  echo "Python: $PYTHON"
  echo "================================================================"

  "$PYTHON" main.py --update --force

  current_year="$(date '+%Y')"
  current_legacy_file="$PROJECT_DIR/data/legacy_${current_year}.txt"
  current_disaggregated_file="$PROJECT_DIR/data/disaggregated_${current_year}.txt"

  if [ ! -s "$current_legacy_file" ] || [ ! -s "$current_disaggregated_file" ]; then
    echo "Missing current-year COT files after update: $current_legacy_file or $current_disaggregated_file"
    exit 1
  fi

  refreshed_count="$(find "$current_legacy_file" "$current_disaggregated_file" -mtime -1 -print | wc -l | tr -d ' ')"
  if [ "$refreshed_count" -ne 2 ]; then
    echo "Current-year COT files were not refreshed in the last 24 hours; refusing to regenerate stale reports"
    exit 1
  fi

  "$PYTHON" main.py --analyze --signals --export --dashboard
  "$PYTHON" report.py
  "$PYTHON" summary_report.py

  echo "================================================================"
  echo "$(date '+%Y-%m-%d %H:%M:%S %Z') cotpy weekly refresh completed"
  echo "================================================================"
} >> "$LOG_DIR/weekly.log" 2>&1

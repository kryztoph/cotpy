# cotpy — COT Data Analysis Tool

A Python CLI for analyzing CFTC Commitments of Traders (COT) data. It compares
commercial hedgers against non-reportable traders ("small specs") and generates
contrarian-style signals based on divergences in their positioning.

---

## Table of Contents

- [Overview](#overview)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Pipeline](#pipeline)
- [CLI Reference](#cli-reference)
- [Signal Logic](#signal-logic)
- [Key Metrics](#key-metrics)
- [Configuration](#configuration)
- [contracts.json](#contractsjson)
- [Outputs](#outputs)
- [Weekly Automation](#weekly-automation)
- [Report Scripts](#report-scripts)
- [Source Layout](#source-layout)
- [Data Sources](#data-sources)

---

## Overview

cotpy downloads weekly CFTC COT reports, parses them into structured data, and
looks for divergences between trader groups. The core idea is contrarian:
commercial hedgers are often considered "smart money," while small speculators
are frequently wrong at extremes. When the two groups diverge significantly,
the tool flags a potential trade setup.

The tool works primarily with **Legacy** COT reports. Disaggregated data is also
downloaded and parsed but is not used by the current analysis pipeline.

---

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Quick Start

```bash
# Download data and run the full pipeline
python main.py --all

# Generate the trade setup report
python report.py

# Generate the position summary
python summary_report.py
```

---

## Pipeline

The main code path:

```
COTFetcher → COTParser → COTAnalyzer → SignalGenerator → COTVisualizer
```

Step by step:

1. **COTFetcher** discovers and downloads `data/legacy_*.txt` and
   `data/disaggregated_*.txt` from the CFTC.
2. **COTParser.parse_all_legacy()** reads and combines Legacy files, normalizes
   market names via `contracts.json`, and filters to enabled contracts.
3. **COTParser.calculate_derived_fields()** computes net positions and
   percent-of-open-interest fields.
4. **COTAnalyzer.run_full_analysis()** adds divergence and percentile columns,
   flags extreme readings.
5. **SignalGenerator.generate_signals()** converts latest readings into
   bullish/bearish signal objects.
6. **COTVisualizer** or the report scripts format results for charts, console
   output, CSV, or text files.

Note: each `main.py` command handler reloads and reanalyzes data independently.
There is no shared in-memory pipeline across handlers.

---

## CLI Reference

### main.py

| Flag | Description |
|------|-------------|
| `--update, -u` | Download latest COT data from CFTC |
| `--force, -f` | Force re-download of data files |
| `--analyze, -a` | Run analysis and show market summary |
| `--signals, -s` | Display current trading signals |
| `--strong-only` | Show only strong signals |
| `--chart MARKET, -c` | Generate charts for a specific market |
| `--interactive, -i` | Generate interactive Plotly chart (use with `--chart`) |
| `--export, -e` | Export analysis results to CSV |
| `--dashboard, -d` | Generate interactive dashboard |
| `--key-charts` | Generate static and interactive charts for all key markets |
| `--market-charts` | Generate static and interactive charts for all enabled markets |
| `--list-markets, -l` | List all available markets |
| `--all` | Run complete pipeline (update, analyze, signals, export, market charts) |
| `--years N` | Number of years of historical data (default: 3) |

`--all` does **not** run `report.py` or `summary_report.py`.

`--chart` expects the normalized display name from `contracts.json`, not the raw
CFTC market string.

### Examples

```bash
python main.py --update
python main.py --analyze --signals
python main.py --signals --strong-only
python main.py --chart "GOLD" --interactive
python main.py --chart "CRUDE OIL, LIGHT SWEET"
python main.py --export
python main.py --dashboard
python main.py --key-charts
python main.py --market-charts
python main.py --list-markets
python main.py --years 5
```

---

## Signal Logic

Signals are percentile-based, computed per market using `rank(pct=True) * 100`.

| Signal | Condition |
|--------|-----------|
| **Strong Bullish** | Commercial percentile >= 90 AND Small Spec percentile <= 10 |
| **Moderate Bullish** | Commercial percentile >= 75 AND Small Spec percentile <= 25 |
| **Strong Bearish** | Commercial percentile <= 10 AND Small Spec percentile >= 90 |
| **Moderate Bearish** | Commercial percentile <= 25 AND Small Spec percentile >= 75 |
| **Weak Bullish** | Divergence percentile >= 90 |
| **Weak Bearish** | Divergence percentile <= 10 |

Signals are sorted by how extreme the divergence percentile is (distance from 50).

---

## Key Metrics

| Metric | Formula |
|--------|---------|
| `commercial_net` | `commercial_long - commercial_short` |
| `small_spec_net` | `small_spec_long - small_spec_short` |
| `commercial_net_pct` | `commercial_net / open_interest` |
| `small_spec_net_pct` | `small_spec_net / open_interest` |
| `divergence` | `commercial_net_pct - small_spec_net_pct` |
| Percentile | Historical rank (0-100) within each market |

---

## Configuration

Primary configuration lives in `src/config.py` as a `Config` dataclass:

| Field | Default | Purpose |
|-------|---------|---------|
| `percentile_high` | 90.0 | Extreme high threshold |
| `percentile_low` | 10.0 | Extreme low threshold |
| `lookback_years` | 1 | Display lookback |
| `historical_years` | 3 | Percentile history window |
| `markets_filter` | [] | Optional post-config market filter |
| `divergence_threshold_bullish` | 0.10 | Defined but unused by active signal logic |
| `divergence_threshold_bearish` | -0.10 | Defined but unused by active signal logic |
| `commercial_net_threshold` | 0.05 | Defined but unused by active signal logic |
| `small_spec_net_threshold` | -0.03 | Defined but unused by active signal logic |

`Config.__post_init__()` auto-creates `data/`, `output/`, and `output/charts/`.

`--years N` on the CLI sets both the fetch range and the historical percentile
window via `Config(historical_years=args.years)`.

---

## contracts.json

This file actively controls filtering and market renaming. It is not just metadata.

Each entry:

| Field | Description |
|-------|-------------|
| `cftc_name` | Exact name from CFTC data (must match exactly) |
| `display_name` | Friendly name shown in reports and charts |
| `category` | Grouping: metals, energy, indices, fixed_income, currencies, grains, softs, meats |
| `enabled` | `false` excludes from all processing |
| `key_market` | `true` includes in the key markets watchlist |

### Disabling a contract

Set `"enabled": false` on the entry. It will be excluded from parsing, analysis,
signals, reports, and charts.

### Adding a contract

1. Run `python main.py --update` to download the latest data.
2. Find the exact CFTC name in `data/legacy_*.txt`.
3. Add an entry to `contracts.json` with the exact `cftc_name`.

Parser-level filtering means adding an enabled contract is enough to make it
appear everywhere.

---

## Outputs

### Data files

| Path | Description |
|------|-------------|
| `data/legacy_*.txt` | Downloaded Legacy COT reports |
| `data/disaggregated_*.txt` | Downloaded Disaggregated COT reports |

### Analysis outputs

| Path | Description |
|------|-------------|
| `output/positions.csv` | All position data with calculated ratios |
| `output/signals.csv` | Current divergence signals |
| `output/market_summary.csv` | Summary statistics per market |
| `output/charts/dashboard.html` | Interactive analysis dashboard |
| `output/charts/*_interactive.html` | Interactive Plotly charts per market |
| `output/charts/*_positions.png` | Static Matplotlib charts per market |

### Reports

| Path | Description |
|------|-------------|
| `output/trade_setup_report.txt` | Markets with extreme divergences (from `report.py`) |
| `output/position_summary.txt` | Formatted position summary (from `summary_report.py`) |
| `output/position_summary.csv` | Full data export (from `summary_report.py`) |

### Logs

| Path | Description |
|------|-------------|
| `logs/weekly.log` | Weekly automation log |

---

## Weekly Automation

A shell script at `scripts/run_cotpy_weekly.sh` runs the full pipeline:

1. `main.py --update --force` — re-downloads all data
2. Verifies current-year files were refreshed in the last 24 hours
3. `main.py --analyze --signals --export --market-charts`
4. `report.py`
5. `summary_report.py`

It uses a lock directory (`cotpy-weekly.lock`) to prevent concurrent runs and
logs everything to `logs/weekly.log`.

The README mentions a macOS LaunchAgent (`launchd/com.fox.cotpy.weekly.plist`),
but that file is not present in the repo. The shell script is what actually runs.

---

## Report scripts

### report.py

Generates `output/trade_setup_report.txt`. Restricts output to markets whose
latest row is within 14 days of the most recent date in the dataset. Shows:

- Strong / Moderate / Weak bullish and bearish setups
- Key markets watchlist (from `key_market: true` in `contracts.json`)

### summary_report.py

Generates `output/position_summary.txt` and `output/position_summary.csv`.
Groups all enabled contracts by category and labels markets from divergence
percentile bands. Does **not** reuse the two-sided percentile logic from
SignalGenerator — it labels from divergence percentile alone.

---

## Source Layout

```
cotpy/
├── src/
│   ├── __init__.py
│   ├── config.py        # Config dataclass + contracts.json helpers
│   ├── fetcher.py       # Download COT data from CFTC
│   ├── parser.py        # Parse/normalize/filter data
│   ├── analyzer.py      # Divergence + percentile analysis
│   ├── signals.py       # Signal generation rules
│   └── visualizer.py    # Matplotlib static + Plotly interactive charts
├── scripts/
│   └── run_cotpy_weekly.sh
├── data/                # Downloaded COT data files
├── output/              # Generated CSVs, charts, reports
├── logs/                # Automation logs
├── contracts.json       # Market configuration
├── main.py              # CLI entry point
├── report.py            # Trade setup report
├── summary_report.py    # Position summary report
├── requirements.txt
├── README.md
├── CLAUDE.md
├── PLAN.md
└── TODO.md
```

---

## Data Sources

- **Legacy COT**: Weekly positions by trader type (commercial, non-commercial,
  non-reportable). Available back to 1986.
  - URL: `https://www.cftc.gov/files/dea/history/deacot{year}.zip`
- **Disaggregated COT**: Detailed breakdown (producers, swap dealers, managed
  money, etc.). Available from 2006.
  - URL: `https://www.cftc.gov/files/dea/history/fut_disagg_txt_{year}.zip`

Data is released every Friday and reflects positions as of the prior Tuesday.

---

## Working Notes

- If a market "disappears," check `contracts.json` enablement and name mapping
  first — parser filtering is the most common cause.
- Network access is required for `--update`. Most other validation can run
  against cached files in `data/`.
- There is no test suite. Verify changes with the smallest relevant command:
  `python main.py --signals`, `python summary_report.py`, etc.
- Chart output filenames only sanitize `/`, so market names with other
  punctuation keep that punctuation in the filename.

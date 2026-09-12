# CLAUDE.md

This file provides repo-specific guidance for agents working in `cotpy`.

## Project Summary

`cotpy` is a Python CLI for analyzing CFTC Commitments of Traders data. The main workflow uses Legacy COT reports to compare commercial hedgers against non-reportable traders ("small specs") and generate contrarian-style signals.

The codebase is small and script-oriented. Publishing and weekly recovery tests run with `.venv/bin/python -m unittest discover -s tests -v`. Analysis validation is usually done by running the CLI or report scripts against cached data in `data/`.

When documentation and code disagree, trust the Python entry points in `main.py`, `report.py`, and `summary_report.py`. `PLAN.md` is historical scaffolding, not the authoritative design.

## Setup And Common Commands

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Primary CLI:

```bash
python main.py --update
python main.py --analyze
python main.py --signals
python main.py --signals --strong-only
python main.py --chart "GOLD"
python main.py --chart "GOLD" --interactive
python main.py --dashboard
python main.py --key-charts
python main.py --market-charts
python main.py --export
python main.py --list-markets
python main.py --all
python main.py --years 5
```

Supporting reports:

```bash
python report.py
python summary_report.py
```

Useful low-cost validation commands when editing:

```bash
python main.py --help
python main.py --list-markets
python main.py --signals --strong-only
python summary_report.py
```

## Actual Pipeline

The main code path is:

```text
COTFetcher -> COTParser -> COTAnalyzer -> SignalGenerator -> COTVisualizer
```

Detailed flow for `main.py` commands:

1. `COTFetcher.get_cached_files()` discovers `data/legacy_*.txt` and `data/disaggregated_*.txt`.
2. `COTParser.parse_all_legacy()` reads and combines Legacy files.
3. `COTParser.calculate_derived_fields(..., report_type="legacy")` computes net positions and percent-of-open-interest fields.
4. `COTAnalyzer.run_full_analysis()` adds divergence and percentile columns.
5. `SignalGenerator.generate_signals()` converts latest readings into bullish/bearish signal objects.
6. `COTVisualizer` or the report scripts format results for charts, console output, CSV, or text files.

## Important Implementation Notes

- The fetcher downloads both Legacy and Disaggregated COT datasets.
- The current analysis, signal generation, dashboard, and both report scripts use Legacy data only.
- `contracts.json` is not just metadata. It actively controls filtering and market renaming through `src/config.py` helpers and `src/parser.py`.
- Only enabled contracts from `contracts.json` survive parsing when the config helper returns names.
- `Config.__post_init__()` creates `data/`, `output/`, and `output/charts/` automatically.
- `main.py --years N` affects both the fetch range and the historical percentile window because it sets `Config(historical_years=args.years)`.
- `main.py --all` runs `--update`, `--analyze`, `--signals`, `--export`, and all enabled-market chart generation, but it does not run `report.py` or `summary_report.py`.
- Supplying multiple CLI flags causes each command handler to reload and reanalyze data independently; there is no shared in-memory pipeline across handlers.
- `main.py --chart ...` expects the normalized display name used after `contracts.json` mapping, not necessarily the raw CFTC market string.
- `main.py --chart ...` output filenames only sanitize `/`, so chart names with other punctuation keep that punctuation in the file name.
- `summary_report.py` labels markets from divergence percentile bands only; it does not reuse the stronger two-sided percentile logic from `SignalGenerator`.
- `report.py` restricts output to markets whose latest row is within 14 days of the most recent date in the dataset.
- `divergence_threshold_bullish`, `divergence_threshold_bearish`, `commercial_net_threshold`, and `small_spec_net_threshold` exist in `Config` but are not currently used by the active signal logic.

## Source Layout

- `main.py`: CLI entry point and command orchestration.
- `report.py`: Generates `output/trade_setup_report.txt`.
- `summary_report.py`: Generates `output/position_summary.txt` and `output/position_summary.csv`.
- `scripts/publish_to_csfox.sh`: Publishes generated `output/` reports to `kryztoph/csfox-reports` under `cotpy/` using `gh api`.
- `scripts/run_cotpy_weekly.py`: Weekly stage orchestration, timeouts, retries, process locking, and status reporting (invoked by the scheduled shell wrapper).
- `src/config.py`: Config dataclass plus helpers for reading `contracts.json`.
- `src/fetcher.py`: Downloads yearly zip files from the CFTC and extracts `.txt` payloads into `data/`.
- `src/parser.py`: Selects CFTC columns, parses dates, normalizes market names, filters to enabled contracts, and computes derived fields.
- `src/analyzer.py`: Adds divergence, percentile, and extreme-reading columns; builds latest-per-market summaries.
- `src/signals.py`: Encodes signal evaluation rules and report-friendly signal objects.
- `src/visualizer.py`: Matplotlib static charts and Plotly HTML outputs.
- `contracts.json`: Canonical market configuration.

## Signal Rules

Signal generation is percentile-based:

- Strong bullish: commercial percentile `>= 90` and small spec percentile `<= 10`
- Moderate bullish: commercial percentile `>= 75` and small spec percentile `<= 25`
- Strong bearish: commercial percentile `<= 10` and small spec percentile `>= 90`
- Moderate bearish: commercial percentile `<= 25` and small spec percentile `>= 75`
- Weak signals fall back to divergence percentile alone

Key formulas:

```python
commercial_net = commercial_long - commercial_short
small_spec_net = small_spec_long - small_spec_short
commercial_net_pct = commercial_net / open_interest
small_spec_net_pct = small_spec_net / open_interest
divergence = commercial_net_pct - small_spec_net_pct
```

Percentiles are computed per market with `rank(pct=True) * 100`.

Weak signals are based on divergence percentile alone:

- Weak bullish: divergence percentile `>= 90`
- Weak bearish: divergence percentile `<= 10`

## Configuration And Data

Primary configuration lives in `src/config.py`:

- `historical_years`: controls download range and percentile history window
- `lookback_years`: currently available for date calculations, but the parser primarily filters by `historical_start_date`
- `percentile_high` / `percentile_low`: extreme thresholds, default `90` / `10`
- `markets_filter`: optional post-config market filtering

`contracts.json` controls:

- exact CFTC name to display-name mapping
- enabled/disabled markets
- category grouping for the summary report
- key-market watchlist membership

The parser-level filtering means adding a contract to `contracts.json` is usually enough to make it appear everywhere, while disabling one removes it from analysis, reports, and charts without touching code.

## Outputs

Common outputs:

- `output/positions.csv`
- `output/signals.csv`
- `output/market_summary.csv`
- `output/charts/dashboard.html`
- `output/charts/*_interactive.html`
- `output/charts/*_positions.png`
- `output/charts/divergence_heatmap.png`
- `output/charts/signal_summary.png`
- `output/charts/market_comparison.html`
- `output/trade_setup_report.txt`
- `output/position_summary.txt`
- `output/position_summary.csv`

Publishing:

- `scripts/run_cotpy_weekly.sh` generates static and interactive charts for all enabled markets, then publishes to `kryztoph/csfox-reports` by default.
- Set `COTPY_PUBLISH_REPORTS=0` to skip publishing, or run `scripts/publish_to_csfox.sh` manually.
- The publisher explicitly triggers a GitHub Pages rebuild after updating the reports branch.
- Published paths live under `cotpy/` in the `csfox-reports` repo.
- The installed schedule runs Saturday at 7 a.m. and noon. It invokes the shell wrapper directly, so changes to the runner take effect without reloading launchd.
- Download, report generation, and publishing each get three attempts, with 60-second and 300-second retry delays. Publishing retries do not repeat the completed generation stage within a run.
- Download attempts allow 40 minutes; each generation command and each publishing attempt allow 60 minutes. Timed-out commands and their child processes are terminated before retrying.
- `logs/weekly-status.json` records the latest stage, attempt, and error; `logs/weekly.log` contains the complete run output. `logs/weekly.lock` uses an OS lock released automatically when the runner exits or crashes.
- Every GitHub API call has a 120-second timeout and up to five attempts for transient errors. Unchanged files are identified by Git blob hashes and skipped.
- Publishing requires a successful Pages build for the target commit and matching live dashboard bytes, allowing 15 minutes for deployment. A no-change rerun still checks/repairs deployment. `COTPY_PUBLISH_TRIGGER_PAGES=0` explicitly disables deployment verification.
- `--market-charts` fails if any required chart could not be generated, preventing the weekly job from publishing a partially regenerated chart set.

Cached downloads:

- `data/legacy_*.txt`
- `data/disaggregated_*.txt`

## Working Safely In This Repo

- Prefer changing `contracts.json` or `src/config.py` for threshold and market-scope changes before altering analysis logic.
- If a market "disappears," check contract enablement and name mapping first; parser filtering is often the cause.
- Network access is required for `--update`; most other validation can run against cached files.
- Prefer verifying changes with the smallest relevant command, for example `python main.py --signals` or `python summary_report.py`; use the recovery tests for weekly/publishing changes.
- If you are only editing docs, do not restage or rewrite unrelated `.context/` files; they are workspace metadata, not part of the product.

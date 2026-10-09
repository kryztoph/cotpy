# COT Data Analysis Tool

Analyze CFTC Commitments of Traders (COT) data to identify divergences between commercials and small speculators for trading signals.

## Installation

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Quick Start

```bash
# Download data and run full analysis
python main.py --all

# Generate trade setup report
python report.py
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `--update, -u` | Download latest COT data from CFTC |
| `--analyze, -a` | Run analysis and show market summary |
| `--signals, -s` | Display current trading signals |
| `--strong-only` | Filter to show only strong signals |
| `--chart MARKET, -c` | Generate charts for a specific market |
| `--interactive, -i` | Generate interactive Plotly chart (with --chart) |
| `--export, -e` | Export analysis results to CSV |
| `--dashboard, -d` | Generate interactive dashboard and all linked market charts |
| `--key-charts` | Generate static and interactive charts for all key markets |
| `--market-charts` | Generate static and interactive charts for all enabled markets |
| `--list-markets, -l` | List all available markets |
| `--all` | Run complete pipeline |
| `--force, -f` | Force re-download of data files |
| `--years N` | Number of years of historical data (default: 3) |

## Examples

```bash
# Download latest COT data
python main.py --update

# Analyze data and show signals
python main.py --analyze --signals

# Show only strong signals
python main.py --signals --strong-only

# Generate interactive chart for Gold
python main.py --chart "GOLD" --interactive

# Generate static chart for S&P 500
python main.py --chart "E-MINI S&P 500 STOCK INDEX"

# Export all data to CSV
python main.py --export

# Generate interactive dashboard
python main.py --dashboard

# Generate the complete key-market chart set
python main.py --key-charts

# Generate charts for every enabled market
python main.py --market-charts

# List all available markets
python main.py --list-markets
```

## Output Files

| File | Description |
|------|-------------|
| `output/positions.csv` | All position data with calculated ratios |
| `output/signals.csv` | Current divergence signals |
| `output/market_summary.csv` | Summary statistics per market |
| `output/charts/dashboard.html` | Interactive analysis dashboard |
| `output/charts/*.html` | Interactive Plotly charts |
| `output/charts/*.png` | Static Matplotlib charts |

## Viewing Charts

Open interactive charts in your browser:

```bash
# Open the main dashboard (overview of all markets)
open output/charts/dashboard.html

# Open a specific market chart
open output/charts/GOLD_interactive.html
```

Generate charts for specific markets:

```bash
# Interactive HTML charts (recommended)
python main.py --chart "GOLD" --interactive
python main.py --chart "CRUDE OIL, LIGHT SWEET" --interactive
python main.py --chart "E-MINI S&P 500 STOCK INDEX" --interactive
python main.py --chart "CORN" --interactive
python main.py --chart "EURO FX" --interactive

# Static PNG charts
python main.py --chart "GOLD"
python main.py --chart "SILVER"
```

Use `--list-markets` to see all available market names.

## Trade Setup Report

Generate a focused report of markets showing extreme divergences:

```bash
python report.py
```

Output includes:
- **Strong Bullish Setups**: Commercials heavily long, small specs heavily short
- **Strong Bearish Setups**: Commercials heavily short, small specs heavily long
- **Key Markets Watchlist**: Major commodities, currencies, and indices with current readings

Report saved to `output/trade_setup_report.txt`

## Weekly Automation

This repo includes a macOS LaunchAgent that refreshes CFTC data and regenerates
all outputs every Saturday at 7:00 AM and noon local time:

```bash
cp launchd/com.fox.cotpy.weekly.plist ~/Library/LaunchAgents/
launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/com.fox.cotpy.weekly.plist
```

The scheduled job runs:

```bash
scripts/run_cotpy_weekly.sh
```

The runner uses `main.py --update`, which refreshes current-week reports and
the current-year archives while reusing historical archives. Failed current-week
downloads return failure instead of silently continuing with cached data.
The runner verifies that both current-week files were refreshed and contain
report dates no older than 10 days, then regenerates analysis, signals, CSV exports, the
dashboard, all static and interactive enabled-market charts, the trade setup report,
and position summary. By default it then
publishes the refreshed reports to the `kryztoph/csfox-reports` GitHub Pages
repo under `cotpy/`. Logs are written to `logs/weekly.log`.

The 10-day freshness limit is an operational guard against publishing last
week's data, rather than an official release-calendar calculation. For a known
CFTC release delay, set `COTPY_MAX_REPORT_AGE_DAYS` to a larger positive number.
Freshness uses weekly report dates, so a late-December report remains valid in
early January even before the new annual archive is available.

On macOS the wrapper holds a `caffeinate -i` assertion while the job runs.
This prevents idle sleep from stretching downloads, timeouts, and publishing
retries across days. It does not wake a sleeping Mac or prevent lid-close sleep;
the scheduled job still needs the computer available to run.

Download, report generation, and publishing each receive three attempts with
60-second and 300-second delays. Download commands have a 40-minute timeout;
each generation command and publish attempt have a 60-minute timeout. The runner
kills timed-out process groups before retrying. Publishing retries reuse completed
reports. An OS lock prevents overlapping runs and releases automatically after a
crash. The latest stage, attempt, and error are recorded in `logs/weekly-status.json`.

GitHub API calls have a 120-second timeout and up to five attempts for transient
failures. Unchanged report blobs are skipped. Publishing succeeds only after a
Pages build for the target commit and matching live dashboard bytes are verified;
unchanged reruns also check deployment. Chart generation fails if any required
artifact is missing, so partial results cannot be published by the weekly runner.

If replacing an already loaded LaunchAgent, reload it to install the fallback:

```bash
launchctl bootout "gui/$(id -u)/com.fox.cotpy.weekly"
cp launchd/com.fox.cotpy.weekly.plist ~/Library/LaunchAgents/
launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/com.fox.cotpy.weekly.plist
```

See [the weekly failure investigation](docs/weekly-refresh-investigation.md) for
observed failures and recovery limits.

Publish reports manually:

```bash
scripts/publish_to_csfox.sh
```

Set `COTPY_PUBLISH_REPORTS=0` to skip publishing from the weekly runner. The
publisher uses `gh api`; `gh` must be installed and authenticated. Override the
target with `COTPY_PUBLISH_REPO`, `COTPY_PUBLISH_BRANCH`, or
`COTPY_PUBLISH_PREFIX`. GitHub Pages rebuild triggering can be disabled with
`COTPY_PUBLISH_TRIGGER_PAGES=0`.

Check status:

```bash
launchctl print "gui/$(id -u)/com.fox.cotpy.weekly"
```

## Signal Logic

**Bullish Signal**: Commercials heavily net long + Small speculators heavily net short
- Commercials (hedgers) are typically "smart money"
- Small specs are often wrong at extremes (contrarian indicator)

**Bearish Signal**: Commercials heavily net short + Small speculators heavily net long

**Signal Strength**:
- **Strong**: Both groups at extreme percentiles (90th/10th)
- **Moderate**: Both groups at elevated percentiles (75th/25th)
- **Weak**: Divergence at extreme percentile

## Key Metrics

- **Commercial Net %**: (Commercial Long - Commercial Short) / Open Interest
- **Small Spec Net %**: (Small Spec Long - Small Spec Short) / Open Interest
- **Divergence**: Commercial Net % - Small Spec Net %
- **Percentile**: Historical ranking of current reading (0-100)

## Contract Configuration

The `contracts.json` file controls which markets are tracked and analyzed. Each contract has:

| Field | Description |
|-------|-------------|
| `cftc_name` | Exact name from CFTC data (must match exactly) |
| `display_name` | Friendly name shown in reports |
| `category` | Grouping (metals, energy, indices, fixed_income, currencies, grains, softs, meats) |
| `enabled` | Set to `false` to exclude from all processing |
| `key_market` | Set to `true` to include in key markets watchlist |

### Disabling a Contract

To stop tracking a contract, edit `contracts.json` and set `"enabled": false`:

```json
{
  "cftc_name": "COCOA - ICE FUTURES U.S.",
  "display_name": "COCOA",
  "category": "softs",
  "enabled": false,
  "key_market": false
}
```

The disabled contract will be excluded from:
- Data parsing and analysis
- Signal generation
- All reports and charts

### Adding a New Contract

1. Run `python main.py --update` to download latest data
2. Check available CFTC names in the data files (`data/legacy_*.txt`)
3. Add entry to `contracts.json` with exact `cftc_name` match

## Position Summary Report

Generate a comprehensive summary of all positions:

```bash
python summary_report.py
```

Output:
- `output/position_summary.txt` - Formatted text report
- `output/position_summary.csv` - Full data export

The report shows:
- All enabled contracts grouped by category
- Open interest, net positions, and percentages
- Divergence percentile and signal strength
- Strong bullish/bearish actionable signals

## Configuration

Edit `src/config.py` to customize:

```python
# Percentile thresholds for extreme readings
percentile_high: float = 90.0  # Above = extremely bullish
percentile_low: float = 10.0   # Below = extremely bearish

# Lookback periods
lookback_years: int = 1        # For analysis display
historical_years: int = 3      # For percentile calculations

# Filter specific markets (empty = all)
markets_filter: list[str] = []
```

## Data Sources

- **Legacy COT**: Weekly positions by trader type (commercial, non-commercial, non-reportable)
- **Disaggregated COT**: Detailed breakdown (producers, swap dealers, managed money, etc.)

Data is released every Friday by the CFTC (as of Tuesday's positions).

## Project Structure

```
cotpy/
├── src/
│   ├── config.py      # Configuration settings & contract loader
│   ├── fetcher.py     # Download COT data from CFTC
│   ├── parser.py      # Parse CSV files into DataFrames
│   ├── analyzer.py    # Calculate ratios & divergences
│   ├── signals.py     # Generate trading signals
│   └── visualizer.py  # Matplotlib & Plotly charts
├── data/              # Downloaded COT data files
├── output/            # Generated CSVs and charts
├── contracts.json     # Contract configuration (enable/disable markets)
├── main.py            # CLI entry point
├── report.py          # Trade setup report generator
├── summary_report.py  # Position summary report generator
└── requirements.txt
```

Dashboard navigation checks:

```bash
python -m unittest discover -s tests -v
NODE_PATH=/tmp/cotpy-links-browser/node_modules node tests/check_dashboard_links.cjs
```

Browser checks require Playwright and Chromium; set `CHROMIUM_PATH` to use an existing browser.
The all-markets table stays at the top, with the existing sorting controls and branded layout.

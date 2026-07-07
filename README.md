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
| `--dashboard, -d` | Generate interactive dashboard |
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
all outputs every Saturday at 7:00 AM local time:

```bash
cp launchd/com.fox.cotpy.weekly.plist ~/Library/LaunchAgents/
launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/com.fox.cotpy.weekly.plist
```

The scheduled job runs:

```bash
scripts/run_cotpy_weekly.sh
```

The runner uses `main.py --update --force`, verifies the current-year COT files
were actually refreshed, then regenerates analysis, signals, CSV exports,
dashboard, trade setup report, and position summary. By default it then
publishes the refreshed reports to the `kryztoph/csfox` GitHub repo under
`reports/cotpy/`. Logs are written to `logs/weekly.log`.

Publish reports manually:

```bash
scripts/publish_to_csfox.sh
```

Set `COTPY_PUBLISH_REPORTS=0` to skip publishing from the weekly runner. The
publisher uses `gh api`; `gh` must be installed and authenticated. Override the
target with `COTPY_PUBLISH_REPO`, `COTPY_PUBLISH_BRANCH`, or
`COTPY_PUBLISH_PREFIX`.

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

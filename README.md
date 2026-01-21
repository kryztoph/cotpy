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
│   ├── config.py      # Configuration settings
│   ├── fetcher.py     # Download COT data from CFTC
│   ├── parser.py      # Parse CSV files into DataFrames
│   ├── analyzer.py    # Calculate ratios & divergences
│   ├── signals.py     # Generate trading signals
│   └── visualizer.py  # Matplotlib & Plotly charts
├── data/              # Downloaded COT data files
├── output/            # Generated CSVs and charts
├── main.py            # CLI entry point
└── requirements.txt
```

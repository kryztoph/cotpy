# COT Data Analysis Tool - Implementation Plan

## Overview
Build a Python tool to analyze CFTC Commitments of Traders (COT) data, identifying divergences between commercials and small speculators for trading signals.

## Project Structure
```
cotpy/
├── .venv/                    # Virtual environment (exists)
├── src/
│   ├── __init__.py
│   ├── fetcher.py           # Download COT data from CFTC
│   ├── parser.py            # Parse CSV/text files into DataFrames
│   ├── analyzer.py          # Calculate net position ratios & divergences
│   ├── signals.py           # Generate trading signals/alerts
│   ├── visualizer.py        # Matplotlib & Plotly charts
│   └── config.py            # Configurable thresholds & settings
├── data/                    # Downloaded COT data files
├── output/                  # Generated CSVs, charts, reports
├── main.py                  # CLI entry point
├── requirements.txt
└── README.md
```

## Dependencies
- `pandas` - Data manipulation
- `requests` - HTTP downloads
- `matplotlib` / `seaborn` - Static charts
- `plotly` - Interactive charts
- `numpy` - Numerical calculations

## Implementation Steps

### 1. Config Module (`src/config.py`)
- Configurable divergence thresholds (default: 60% net long/short)
- Historical percentile thresholds (default: 90th/10th)
- Date range settings (1 year lookback)
- Output paths
- List of markets to track (default: all)

### 2. Data Fetcher (`src/fetcher.py`)
- Download Legacy COT reports (futures-only and combined)
- Download Disaggregated COT reports
- CFTC data URLs:
  - Legacy: `https://www.cftc.gov/files/dea/history/deacot{year}.zip`
  - Disaggregated: `https://www.cftc.gov/files/dea/history/fut_disagg_txt_{year}.zip`
- Handle zip extraction and caching
- Filter to last 1 year of data

### 3. Data Parser (`src/parser.py`)
- Parse Legacy report columns:
  - Commercial Long/Short positions
  - Non-Commercial Long/Short (large speculators)
  - Non-Reportable Long/Short (small speculators)
  - Open Interest
- Parse Disaggregated report columns:
  - Producer/Merchant (commercials)
  - Swap Dealers
  - Managed Money
  - Other Reportables
- Normalize market names across reports
- Calculate derived fields (net positions, % of OI)

### 4. Analyzer (`src/analyzer.py`)
- Calculate net position ratios:
  ```
  commercial_net_ratio = (commercial_long - commercial_short) / open_interest
  small_spec_net_ratio = (small_spec_long - small_spec_short) / open_interest
  ```
- Calculate divergence score:
  ```
  divergence = commercial_net_ratio - small_spec_net_ratio
  ```
- Compute historical percentiles for each market
- Flag extreme readings based on configurable thresholds

### 5. Signal Generator (`src/signals.py`)
- **Bullish signal**: Commercials heavily net long + Small specs heavily net short
- **Bearish signal**: Commercials heavily net short + Small specs heavily net long
- Output signal strength (based on divergence magnitude)
- Generate alerts DataFrame with:
  - Market name
  - Signal type (bullish/bearish)
  - Commercial net %
  - Small spec net %
  - Divergence score
  - Historical percentile
  - Date

### 6. Visualizer (`src/visualizer.py`)
**Matplotlib/Seaborn (static):**
- Time series of net positions by trader type
- Divergence heatmap across markets
- Signal summary bar chart

**Plotly (interactive):**
- Interactive time series with hover details
- Market comparison scatter plot
- Divergence dashboard

### 7. Main CLI (`main.py`)
```bash
python main.py --update          # Fetch latest data
python main.py --analyze         # Run analysis
python main.py --signals         # Show current signals
python main.py --chart MARKET    # Generate charts for specific market
python main.py --export          # Export all to CSV
```

## Key Outputs
1. `output/signals.csv` - Current divergence signals
2. `output/positions.csv` - All position data with ratios
3. `output/charts/` - PNG and HTML visualizations
4. Console alerts for extreme divergences

## Verification
1. Run `python main.py --update` to download COT data
2. Run `python main.py --analyze` to process data
3. Run `python main.py --signals` to view divergence alerts
4. Verify CSV outputs in `output/` directory
5. Open interactive Plotly charts in browser
6. Cross-check a few data points against CFTC website

## Notes
- COT data released every Friday (as of Tuesday's positions)
- Legacy data available back to 1986, Disaggregated from 2006
- "Commercials" in Legacy = hedgers (typically fade them)
- Small speculators often wrong at extremes (contrarian indicator)

## User Requirements Summary
| Aspect | Choice |
|--------|--------|
| **Reports** | Both Legacy & Disaggregated |
| **Markets** | All available |
| **Divergence** | Net position ratio (configurable thresholds) |
| **History** | 1 year |
| **Updates** | Manual script run |
| **Output** | CSV, alerts, and visualizations |
| **Charts** | Matplotlib + Plotly |

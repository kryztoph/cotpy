#!/usr/bin/env python3
"""
COT Position Summary Report

Generate a comprehensive summary report of all positions for contracts
defined in contracts.json.
"""

from datetime import datetime

import pandas as pd

from src.config import Config, get_enabled_contracts, get_key_markets
from src.fetcher import COTFetcher
from src.parser import COTParser
from src.analyzer import COTAnalyzer
from src.signals import SignalGenerator, SignalType, SignalStrength


def get_signal_label(div_pct: float) -> str:
    """Get signal label based on divergence percentile."""
    if div_pct >= 90:
        return "STRONG BULL"
    elif div_pct >= 75:
        return "Lean Bull"
    elif div_pct <= 10:
        return "STRONG BEAR"
    elif div_pct <= 25:
        return "Lean Bear"
    else:
        return "Neutral"


def generate_summary_report():
    """Generate comprehensive position summary for all configured contracts."""

    config = Config()
    fetcher = COTFetcher(config)
    parser = COTParser(config)
    analyzer = COTAnalyzer(config)
    signal_gen = SignalGenerator(config)

    # Load contracts config
    contracts = get_enabled_contracts()
    key_markets = get_key_markets()

    # Load and analyze data
    files = fetcher.get_cached_files()
    if not files["legacy"]:
        print("No data found. Run: python main.py --update")
        return

    df = parser.parse_all_legacy(files["legacy"])
    df = parser.calculate_derived_fields(df, "legacy")
    df = analyzer.run_full_analysis(df)

    # Get latest readings
    latest = analyzer.get_latest_readings(df)
    most_recent_date = latest["date"].max()

    # Group contracts by category
    categories = {}
    for contract in contracts:
        cat = contract.get("category", "other")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(contract)

    # Category display order
    category_order = ["metals", "energy", "indices", "fixed_income", "currencies", "grains", "softs", "meats", "other"]
    category_names = {
        "metals": "METALS",
        "energy": "ENERGY",
        "indices": "STOCK INDICES",
        "fixed_income": "FIXED INCOME",
        "currencies": "CURRENCIES",
        "grains": "GRAINS",
        "softs": "SOFTS",
        "meats": "MEATS",
        "other": "OTHER"
    }

    # Build report
    lines = []
    lines.append("=" * 100)
    lines.append("COT POSITION SUMMARY REPORT")
    lines.append("=" * 100)
    lines.append(f"Data as of: {most_recent_date.strftime('%Y-%m-%d')}")
    lines.append(f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"Contracts tracked: {len(contracts)}")
    lines.append(f"Key markets: {len(key_markets)}")
    lines.append("")

    # Summary stats
    bullish_count = 0
    bearish_count = 0
    neutral_count = 0

    for contract in contracts:
        display_name = contract["display_name"]
        market_data = latest[latest["market"] == display_name]
        if not market_data.empty:
            div_pct = market_data.iloc[0].get("divergence_percentile", 50)
            if div_pct >= 75:
                bullish_count += 1
            elif div_pct <= 25:
                bearish_count += 1
            else:
                neutral_count += 1

    lines.append("MARKET SENTIMENT SUMMARY")
    lines.append("-" * 100)
    lines.append(f"  Bullish (>75th %ile): {bullish_count:3}")
    lines.append(f"  Bearish (<25th %ile): {bearish_count:3}")
    lines.append(f"  Neutral:              {neutral_count:3}")
    lines.append("")

    # Column headers
    header = f"{'Market':<25} {'OI':>12} {'Comm Net':>10} {'Comm %':>8} {'Spec Net':>10} {'Spec %':>8} {'Div %ile':>9} {'Signal':>12}"
    separator = "-" * 100

    # Print by category
    for cat in category_order:
        if cat not in categories:
            continue

        cat_contracts = categories[cat]
        cat_name = category_names.get(cat, cat.upper())

        lines.append("")
        lines.append("=" * 100)
        lines.append(f"{cat_name}")
        lines.append("=" * 100)
        lines.append(header)
        lines.append(separator)

        for contract in cat_contracts:
            display_name = contract["display_name"]
            is_key = contract.get("key_market", False)

            market_data = latest[latest["market"] == display_name]

            if market_data.empty:
                lines.append(f"{display_name:<25} {'NO DATA':>12}")
                continue

            row = market_data.iloc[0]

            oi = row.get("open_interest", 0)
            comm_net = row.get("commercial_net", 0)
            comm_pct = row.get("commercial_net_pct", 0)
            spec_net = row.get("small_spec_net", 0)
            spec_pct = row.get("small_spec_net_pct", 0)
            div_pct = row.get("divergence_percentile", 50)

            signal = get_signal_label(div_pct)
            key_marker = "*" if is_key else " "

            lines.append(
                f"{display_name:<24}{key_marker} "
                f"{oi:>12,.0f} "
                f"{comm_net:>+10,.0f} "
                f"{comm_pct:>+7.1%} "
                f"{spec_net:>+10,.0f} "
                f"{spec_pct:>+7.1%} "
                f"{div_pct:>8.0f} "
                f"{signal:>12}"
            )

    # Strong signals section
    lines.append("")
    lines.append("=" * 100)
    lines.append("ACTIONABLE SIGNALS (Extreme Readings)")
    lines.append("=" * 100)

    strong_bullish = []
    strong_bearish = []

    for contract in contracts:
        display_name = contract["display_name"]
        market_data = latest[latest["market"] == display_name]
        if market_data.empty:
            continue

        row = market_data.iloc[0]
        div_pct = row.get("divergence_percentile", 50)
        comm_pct = row.get("commercial_net_pct", 0)
        spec_pct = row.get("small_spec_net_pct", 0)

        if div_pct >= 90:
            strong_bullish.append((display_name, div_pct, comm_pct, spec_pct))
        elif div_pct <= 10:
            strong_bearish.append((display_name, div_pct, comm_pct, spec_pct))

    lines.append("")
    lines.append("STRONG BULLISH (Commercials accumulating, Retail selling)")
    lines.append("-" * 100)
    if strong_bullish:
        for market, div, comm, spec in sorted(strong_bullish, key=lambda x: -x[1]):
            lines.append(f"  {market:<25} Div: {div:>3.0f}  Comm: {comm:>+6.1%}  Spec: {spec:>+6.1%}")
    else:
        lines.append("  None")

    lines.append("")
    lines.append("STRONG BEARISH (Commercials distributing, Retail buying)")
    lines.append("-" * 100)
    if strong_bearish:
        for market, div, comm, spec in sorted(strong_bearish, key=lambda x: x[1]):
            lines.append(f"  {market:<25} Div: {div:>3.0f}  Comm: {comm:>+6.1%}  Spec: {spec:>+6.1%}")
    else:
        lines.append("  None")

    # Notes
    lines.append("")
    lines.append("=" * 100)
    lines.append("LEGEND")
    lines.append("=" * 100)
    lines.append("  * = Key market (in watchlist)")
    lines.append("  OI = Open Interest")
    lines.append("  Comm Net = Commercial net position (long - short)")
    lines.append("  Comm % = Commercial net as % of open interest")
    lines.append("  Spec Net = Small speculator net position")
    lines.append("  Spec % = Small speculator net as % of open interest")
    lines.append("  Div %ile = Divergence percentile (100=most bullish historically)")
    lines.append("")
    lines.append("  STRONG BULL = Divergence >= 90th percentile")
    lines.append("  Lean Bull   = Divergence >= 75th percentile")
    lines.append("  Neutral     = Divergence 25th-75th percentile")
    lines.append("  Lean Bear   = Divergence <= 25th percentile")
    lines.append("  STRONG BEAR = Divergence <= 10th percentile")
    lines.append("=" * 100)

    # Print report
    report = "\n".join(lines)
    print(report)

    # Save to file
    report_path = config.output_dir / "position_summary.txt"
    with open(report_path, "w") as f:
        f.write(report)
    print(f"\nReport saved to: {report_path}")

    # Also save as CSV for easy analysis
    csv_data = []
    for contract in contracts:
        display_name = contract["display_name"]
        market_data = latest[latest["market"] == display_name]

        if market_data.empty:
            continue

        row = market_data.iloc[0]
        csv_data.append({
            "market": display_name,
            "category": contract.get("category", "other"),
            "key_market": contract.get("key_market", False),
            "date": row.get("date"),
            "open_interest": row.get("open_interest", 0),
            "commercial_long": row.get("commercial_long", 0),
            "commercial_short": row.get("commercial_short", 0),
            "commercial_net": row.get("commercial_net", 0),
            "commercial_net_pct": row.get("commercial_net_pct", 0),
            "commercial_percentile": row.get("commercial_net_pct_percentile", 0),
            "small_spec_long": row.get("small_spec_long", 0),
            "small_spec_short": row.get("small_spec_short", 0),
            "small_spec_net": row.get("small_spec_net", 0),
            "small_spec_net_pct": row.get("small_spec_net_pct", 0),
            "small_spec_percentile": row.get("small_spec_net_pct_percentile", 0),
            "large_spec_net": row.get("large_spec_net", 0),
            "large_spec_net_pct": row.get("large_spec_net_pct", 0),
            "divergence": row.get("divergence", 0),
            "divergence_percentile": row.get("divergence_percentile", 50),
            "signal": get_signal_label(row.get("divergence_percentile", 50)),
        })

    csv_df = pd.DataFrame(csv_data)
    csv_path = config.output_dir / "position_summary.csv"
    csv_df.to_csv(csv_path, index=False)
    print(f"CSV saved to: {csv_path}")


if __name__ == "__main__":
    generate_summary_report()

#!/usr/bin/env python3
"""
COT Trade Setup Report

Generate a report of markets showing extreme divergences that may be
set up for trades based on commercial vs small speculator positioning.
"""

from datetime import datetime, timedelta

import pandas as pd

from src.config import Config, get_key_markets
from src.fetcher import COTFetcher
from src.parser import COTParser
from src.analyzer import COTAnalyzer
from src.signals import SignalGenerator, SignalType, SignalStrength


def generate_report():
    """Generate trade setup report from most recent COT data."""

    config = Config()
    fetcher = COTFetcher(config)
    parser = COTParser(config)
    analyzer = COTAnalyzer(config)
    signal_gen = SignalGenerator(config)

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
    most_recent = latest["date"].max()

    # Filter to recent data only (within 2 weeks)
    recent_cutoff = most_recent - timedelta(days=14)
    recent = latest[latest["date"] >= recent_cutoff].copy()

    # Generate signals
    signals = signal_gen.generate_signals(recent)

    # Separate bullish and bearish
    bullish = [s for s in signals if s.signal_type == SignalType.BULLISH]
    bearish = [s for s in signals if s.signal_type == SignalType.BEARISH]

    # Sort by strength and divergence
    strength_order = {SignalStrength.STRONG: 0, SignalStrength.MODERATE: 1, SignalStrength.WEAK: 2}
    bullish.sort(key=lambda s: (strength_order[s.strength], -s.divergence_percentile))
    bearish.sort(key=lambda s: (strength_order[s.strength], s.divergence_percentile))

    # Print report
    print("=" * 70)
    print("COT TRADE SETUP REPORT")
    print("=" * 70)
    print(f"Data as of: {most_recent.strftime('%Y-%m-%d')}")
    print(f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Markets analyzed: {len(recent)}")
    print()

    # Summary
    strong_bull = sum(1 for s in bullish if s.strength == SignalStrength.STRONG)
    strong_bear = sum(1 for s in bearish if s.strength == SignalStrength.STRONG)
    mod_bull = sum(1 for s in bullish if s.strength == SignalStrength.MODERATE)
    mod_bear = sum(1 for s in bearish if s.strength == SignalStrength.MODERATE)

    print("SUMMARY")
    print("-" * 70)
    print(f"  Strong Bullish Setups:   {strong_bull:3}")
    print(f"  Moderate Bullish Setups: {mod_bull:3}")
    print(f"  Strong Bearish Setups:   {strong_bear:3}")
    print(f"  Moderate Bearish Setups: {mod_bear:3}")
    print()

    strong_bullish = []
    mod_bullish = []
    strong_bearish = []
    mod_bearish = []

    # Bullish setups
    print("=" * 70)
    print("BULLISH SETUPS (Commercials Long / Small Specs Short)")
    print("=" * 70)
    print("Commercials are accumulating while retail is selling - potential buy")
    print()

    if not bullish:
        print("  No bullish setups found.")
    else:
        # Strong signals
        strong_bullish = [s for s in bullish if s.strength == SignalStrength.STRONG]
        if strong_bullish:
            print("STRONG SIGNALS:")
            print("-" * 70)
            for s in strong_bullish:
                print(f"  {s.market}")
                print(f"    Commercial Net: {s.commercial_net_pct:+.1%} | Small Spec Net: {s.small_spec_net_pct:+.1%}")
                print(f"    Divergence Percentile: {s.divergence_percentile:.0f}/100")
                print()

        # Moderate signals
        mod_bullish = [s for s in bullish if s.strength == SignalStrength.MODERATE]
        if mod_bullish:
            print("MODERATE SIGNALS:")
            print("-" * 70)
            for s in mod_bullish[:10]:  # Top 10
                print(f"  {s.market}")
                print(f"    Commercial Net: {s.commercial_net_pct:+.1%} | Small Spec Net: {s.small_spec_net_pct:+.1%}")
                print(f"    Divergence Percentile: {s.divergence_percentile:.0f}/100")
                print()

    # Bearish setups
    print()
    print("=" * 70)
    print("BEARISH SETUPS (Commercials Short / Small Specs Long)")
    print("=" * 70)
    print("Commercials are distributing while retail is buying - potential sell")
    print()

    if not bearish:
        print("  No bearish setups found.")
    else:
        # Strong signals
        strong_bearish = [s for s in bearish if s.strength == SignalStrength.STRONG]
        if strong_bearish:
            print("STRONG SIGNALS:")
            print("-" * 70)
            for s in strong_bearish:
                print(f"  {s.market}")
                print(f"    Commercial Net: {s.commercial_net_pct:+.1%} | Small Spec Net: {s.small_spec_net_pct:+.1%}")
                print(f"    Divergence Percentile: {s.divergence_percentile:.0f}/100")
                print()

        # Moderate signals
        mod_bearish = [s for s in bearish if s.strength == SignalStrength.MODERATE]
        if mod_bearish:
            print("MODERATE SIGNALS:")
            print("-" * 70)
            for s in mod_bearish[:10]:  # Top 10
                print(f"  {s.market}")
                print(f"    Commercial Net: {s.commercial_net_pct:+.1%} | Small Spec Net: {s.small_spec_net_pct:+.1%}")
                print(f"    Divergence Percentile: {s.divergence_percentile:.0f}/100")
                print()

    # Key markets watchlist
    print()
    print("=" * 70)
    print("KEY MARKETS WATCHLIST")
    print("=" * 70)

    # Load key markets from contracts.json (markets with key_market: true)
    key_markets = get_key_markets()

    print(f"{'Market':<35} {'Comm Net':>10} {'Spec Net':>10} {'Div %ile':>10} {'Signal':>12}")
    print("-" * 70)

    for market in key_markets:
        market_data = recent[recent["market"] == market]
        if market_data.empty:
            continue

        row = market_data.iloc[0]
        comm_net = row.get("commercial_net_pct", 0)
        spec_net = row.get("small_spec_net_pct", 0)
        div_pct = row.get("divergence_percentile", 50)

        # Determine signal
        if div_pct >= 90:
            signal = "BULLISH"
        elif div_pct <= 10:
            signal = "BEARISH"
        elif div_pct >= 75:
            signal = "Lean Bull"
        elif div_pct <= 25:
            signal = "Lean Bear"
        else:
            signal = "Neutral"

        print(f"{market:<35} {comm_net:>+9.1%} {spec_net:>+9.1%} {div_pct:>9.0f} {signal:>12}")

    print()
    print("=" * 70)
    print("NOTES")
    print("=" * 70)
    print("- Divergence Percentile: 100 = most bullish historically, 0 = most bearish")
    print("- Strong signals: Both groups at extreme percentiles (90th/10th)")
    print("- Commercials = hedgers/producers (typically 'smart money')")
    print("- Small speculators often wrong at extremes (contrarian indicator)")
    print("- COT data is lagged (Tuesday positions, released Friday)")
    print("- Use with price action and other analysis for timing")
    print("=" * 70)

    # Save to file
    report_path = config.output_dir / "trade_setup_report.txt"
    with open(report_path, "w") as f:
        import sys
        from io import StringIO

        # Capture output
        old_stdout = sys.stdout
        sys.stdout = StringIO()

        # Re-run print statements (simplified version for file)
        print(f"COT TRADE SETUP REPORT")
        print(f"Data as of: {most_recent.strftime('%Y-%m-%d')}")
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print()
        print(f"Strong Bullish: {strong_bull} | Moderate Bullish: {mod_bull}")
        print(f"Strong Bearish: {strong_bear} | Moderate Bearish: {mod_bear}")
        print()

        if strong_bullish:
            print("STRONG BULLISH:")
            for s in strong_bullish:
                print(f"  {s.market} (Div: {s.divergence_percentile:.0f})")

        if strong_bearish:
            print("\nSTRONG BEARISH:")
            for s in strong_bearish:
                print(f"  {s.market} (Div: {s.divergence_percentile:.0f})")

        output = sys.stdout.getvalue()
        sys.stdout = old_stdout
        f.write(output)

    print(f"\nReport saved to: {report_path}")


if __name__ == "__main__":
    generate_report()

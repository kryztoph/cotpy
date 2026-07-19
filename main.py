#!/usr/bin/env python3
"""
COT Data Analysis Tool

Analyze CFTC Commitments of Traders data to identify divergences
between commercials and small speculators for trading signals.

Usage:
    python main.py --update          # Fetch latest data
    python main.py --analyze         # Run analysis
    python main.py --signals         # Show current signals
    python main.py --chart MARKET    # Generate charts for specific market
    python main.py --export          # Export all to CSV
    python main.py --dashboard       # Generate interactive dashboard
    python main.py --key-charts      # Generate charts for all key markets
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

from src.config import Config, get_enabled_display_names, get_key_markets
from src.fetcher import COTFetcher
from src.parser import COTParser
from src.analyzer import COTAnalyzer
from src.signals import SignalGenerator, SignalStrength
from src.visualizer import COTVisualizer


def setup_argparser() -> argparse.ArgumentParser:
    """Set up command line argument parser."""
    parser = argparse.ArgumentParser(
        description="COT Data Analysis Tool - Identify trading signals from CFTC data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --update                    # Download latest COT data
  python main.py --analyze --signals         # Analyze and show signals
  python main.py --chart "GOLD"              # Generate charts for Gold
  python main.py --chart "S&P 500" --interactive  # Interactive chart
  python main.py --export                    # Export analysis to CSV
  python main.py --key-charts                # Generate charts for all key markets
  python main.py --market-charts              # Generate charts for all enabled markets
  python main.py --all                       # Run complete pipeline
        """,
    )

    parser.add_argument(
        "--update", "-u",
        action="store_true",
        help="Download latest COT data from CFTC",
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force re-download of data files",
    )
    parser.add_argument(
        "--analyze", "-a",
        action="store_true",
        help="Run analysis on downloaded data",
    )
    parser.add_argument(
        "--signals", "-s",
        action="store_true",
        help="Display current trading signals",
    )
    parser.add_argument(
        "--strong-only",
        action="store_true",
        help="Show only strong signals",
    )
    parser.add_argument(
        "--chart", "-c",
        type=str,
        metavar="MARKET",
        help="Generate charts for a specific market",
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Generate interactive Plotly chart (with --chart)",
    )
    parser.add_argument(
        "--export", "-e",
        action="store_true",
        help="Export analysis results to CSV",
    )
    parser.add_argument(
        "--dashboard", "-d",
        action="store_true",
        help="Generate interactive dashboard",
    )
    parser.add_argument(
        "--key-charts",
        action="store_true",
        help="Generate static and interactive charts for all enabled key markets",
    )
    parser.add_argument(
        "--market-charts",
        action="store_true",
        help="Generate static and interactive charts for all enabled markets",
    )
    parser.add_argument(
        "--list-markets", "-l",
        action="store_true",
        help="List all available markets",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run complete pipeline (update, analyze, signals, export, market charts)",
    )
    parser.add_argument(
        "--years",
        type=int,
        default=3,
        help="Number of years of historical data (default: 3)",
    )

    return parser


def load_and_analyze_data(config: Config) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Load cached data and run analysis.

    Returns:
        Tuple of (analyzed DataFrame, signals DataFrame)
    """
    fetcher = COTFetcher(config)
    parser = COTParser(config)
    analyzer = COTAnalyzer(config)
    signal_gen = SignalGenerator(config)

    # Get cached files
    files = fetcher.get_cached_files()

    if not files["legacy"]:
        print("No data files found. Run with --update first.")
        sys.exit(1)

    print(f"Loading {len(files['legacy'])} Legacy COT files...")

    # Parse data
    df = parser.parse_all_legacy(files["legacy"])
    print(f"Loaded {len(df)} records across {df['market'].nunique()} markets")

    # Calculate derived fields
    df = parser.calculate_derived_fields(df, report_type="legacy")

    # Run analysis
    print("Running analysis...")
    df = analyzer.run_full_analysis(df)

    # Get latest readings and generate signals
    latest = analyzer.get_latest_readings(df)
    signals = signal_gen.generate_signals(latest)
    signals_df = signal_gen.signals_to_dataframe(signals)

    return df, signals_df


def cmd_update(config: Config, force: bool = False):
    """Download latest COT data."""
    print("=" * 60)
    print("Downloading COT Data from CFTC")
    print("=" * 60)

    fetcher = COTFetcher(config)
    files = fetcher.fetch_all_data(force=force)

    print(f"\nDownloaded {len(files['legacy'])} Legacy files")
    print(f"Downloaded {len(files['disaggregated'])} Disaggregated files")
    print("Done!")


def cmd_analyze(config: Config):
    """Run analysis and print summary."""
    print("=" * 60)
    print("COT Data Analysis")
    print("=" * 60)

    df, signals_df = load_and_analyze_data(config)

    analyzer = COTAnalyzer(config)
    summary = analyzer.get_market_summary(df)

    print("\nMarket Summary (sorted by divergence):")
    print("-" * 60)

    # Display top 20 markets
    display_cols = [
        "market",
        "commercial_net_pct",
        "small_spec_net_pct",
        "divergence_percentile",
    ]
    display_df = summary[display_cols].head(20).copy()
    display_df["commercial_net_pct"] = display_df["commercial_net_pct"].apply(
        lambda x: f"{x:.1%}"
    )
    display_df["small_spec_net_pct"] = display_df["small_spec_net_pct"].apply(
        lambda x: f"{x:.1%}"
    )
    display_df["divergence_percentile"] = display_df["divergence_percentile"].apply(
        lambda x: f"{x:.0f}"
    )

    print(display_df.to_string(index=False))
    print(f"\nTotal markets analyzed: {len(summary)}")


def cmd_signals(config: Config, strong_only: bool = False):
    """Display trading signals."""
    print("=" * 60)
    print("COT Trading Signals")
    print("=" * 60)

    df, signals_df = load_and_analyze_data(config)

    signal_gen = SignalGenerator(config)

    # Get latest and generate signals
    analyzer = COTAnalyzer(config)
    latest = analyzer.get_latest_readings(df)
    signals = signal_gen.generate_signals(latest)

    if strong_only:
        signals = signal_gen.filter_signals(
            signals, min_strength=SignalStrength.STRONG
        )

    report = signal_gen.format_signals_report(signals)
    print(report)


def cmd_chart(config: Config, market: str, interactive: bool = False):
    """Generate charts for a market."""
    print(f"Generating charts for {market}...")

    df, signals_df = load_and_analyze_data(config)
    visualizer = COTVisualizer(config)

    if interactive:
        chart_path = config.charts_dir / visualizer._interactive_chart_filename(market)
        visualizer.plot_interactive_positions(df, market, save_path=chart_path)
        print(f"Open {chart_path} in your browser")
    else:
        import matplotlib.pyplot as plt
        chart_path = config.charts_dir / f"{market.replace('/', '_')}_positions.png"
        visualizer.plot_net_positions(df, market, save_path=chart_path)
        plt.close()


def cmd_export(config: Config):
    """Export analysis to CSV."""
    print("Exporting analysis to CSV...")

    df, signals_df = load_and_analyze_data(config)
    analyzer = COTAnalyzer(config)

    # Export full positions data
    positions_path = config.output_dir / "positions.csv"
    df.to_csv(positions_path, index=False)
    print(f"Saved positions to {positions_path}")

    # Export signals
    signals_path = config.output_dir / "signals.csv"
    signals_df.to_csv(signals_path, index=False)
    print(f"Saved signals to {signals_path}")

    # Export market summary
    summary = analyzer.get_market_summary(df)
    summary_path = config.output_dir / "market_summary.csv"
    summary.to_csv(summary_path, index=False)
    print(f"Saved market summary to {summary_path}")


def cmd_dashboard(config: Config):
    """Generate interactive dashboard."""
    print("Generating interactive dashboard...")

    df, signals_df = load_and_analyze_data(config)
    visualizer = COTVisualizer(config)

    dashboard_path = config.charts_dir / "dashboard.html"
    visualizer.create_dashboard(df, signals_df, save_path=dashboard_path)
    print(f"\nOpen {dashboard_path} in your browser")


def cmd_key_charts(config: Config):
    """Generate the complete chart set for enabled key markets."""
    key_markets = get_key_markets()
    print(f"Generating charts for {len(key_markets)} key markets...")

    df, signals_df = load_and_analyze_data(config)
    visualizer = COTVisualizer(config)
    saved = visualizer.save_all_charts(
        df,
        signals_df,
        markets=key_markets,
    )

    print(f"Saved {len(saved)} chart artifacts to {config.charts_dir}")


def cmd_market_charts(config: Config):
    """Generate the complete chart set for all enabled markets."""
    markets = get_enabled_display_names()
    print(f"Generating charts for {len(markets)} enabled markets...")

    df, signals_df = load_and_analyze_data(config)
    visualizer = COTVisualizer(config)
    saved = visualizer.save_all_charts(
        df,
        signals_df,
        markets=markets,
    )

    print(f"Saved {len(saved)} chart artifacts to {config.charts_dir}")


def cmd_list_markets(config: Config):
    """List all available markets."""
    fetcher = COTFetcher(config)
    parser = COTParser(config)

    files = fetcher.get_cached_files()
    if not files["legacy"]:
        print("No data files found. Run with --update first.")
        return

    df = parser.parse_all_legacy(files["legacy"])
    markets = parser.get_available_markets(df)

    print("=" * 60)
    print("Available Markets")
    print("=" * 60)
    for i, market in enumerate(markets, 1):
        print(f"{i:3}. {market}")
    print(f"\nTotal: {len(markets)} markets")


def main():
    """Main entry point."""
    parser = setup_argparser()
    args = parser.parse_args()

    # If no arguments, show help
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    # Create config
    config = Config(historical_years=args.years)

    # Handle --all flag
    if args.all:
        args.update = True
        args.analyze = True
        args.signals = True
        args.export = True
        args.market_charts = True

    # Execute commands
    try:
        if args.update:
            cmd_update(config, force=args.force)
            print()

        if args.list_markets:
            cmd_list_markets(config)
            print()

        if args.analyze:
            cmd_analyze(config)
            print()

        if args.signals:
            cmd_signals(config, strong_only=args.strong_only)
            print()

        if args.chart:
            cmd_chart(config, args.chart, interactive=args.interactive)
            print()

        if args.export:
            cmd_export(config)
            print()

        if args.dashboard:
            cmd_dashboard(config)
            print()

        if args.key_charts:
            cmd_key_charts(config)
            print()

        if args.market_charts:
            cmd_market_charts(config)
            print()

    except KeyboardInterrupt:
        print("\nOperation cancelled.")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

"""Analyze COT data for divergences and trading signals."""

from typing import Optional

import numpy as np
import pandas as pd

from .config import Config, default_config


class COTAnalyzer:
    """Analyze COT data for divergences between trader groups."""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or default_config

    def calculate_divergence(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate divergence between commercials and small speculators.

        The divergence score measures how much commercials and small specs
        disagree on market direction. Higher positive values = commercials
        more bullish than small specs (contrarian bullish signal).

        Args:
            df: DataFrame with calculated net position percentages

        Returns:
            DataFrame with divergence columns added
        """
        df = df.copy()

        # Main divergence: commercial net % minus small spec net %
        # Positive = commercials more bullish than small specs
        # Negative = commercials more bearish than small specs
        df["divergence"] = df["commercial_net_pct"] - df["small_spec_net_pct"]

        # Also track large spec divergence
        df["large_spec_divergence"] = df["commercial_net_pct"] - df["large_spec_net_pct"]

        return df

    def calculate_percentiles(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate historical percentiles for each market's readings.

        Args:
            df: DataFrame with COT data

        Returns:
            DataFrame with percentile columns added
        """
        df = df.copy()

        # Calculate percentiles for each market
        percentile_cols = [
            "commercial_net_pct",
            "small_spec_net_pct",
            "large_spec_net_pct",
            "divergence",
        ]

        for col in percentile_cols:
            if col not in df.columns:
                continue

            percentile_col = f"{col}_percentile"
            df[percentile_col] = df.groupby("market")[col].transform(
                lambda x: x.rank(pct=True) * 100
            )

        return df

    def identify_extreme_readings(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Flag rows with extreme readings based on percentile thresholds.

        Args:
            df: DataFrame with percentile columns

        Returns:
            DataFrame with extreme reading flags
        """
        df = df.copy()

        high = self.config.percentile_high
        low = self.config.percentile_low

        # Flag extreme commercial positioning
        df["commercial_extreme_long"] = df["commercial_net_pct_percentile"] >= high
        df["commercial_extreme_short"] = df["commercial_net_pct_percentile"] <= low

        # Flag extreme small spec positioning
        df["small_spec_extreme_long"] = df["small_spec_net_pct_percentile"] >= high
        df["small_spec_extreme_short"] = df["small_spec_net_pct_percentile"] <= low

        # Flag extreme divergence
        df["divergence_extreme_bullish"] = df["divergence_percentile"] >= high
        df["divergence_extreme_bearish"] = df["divergence_percentile"] <= low

        return df

    def get_latest_readings(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Get the most recent reading for each market.

        Args:
            df: DataFrame with COT data

        Returns:
            DataFrame with one row per market (most recent date)
        """
        # Get the most recent date for each market
        latest_idx = df.groupby("market")["date"].idxmax()
        return df.loc[latest_idx].reset_index(drop=True)

    def analyze_market(
        self, df: pd.DataFrame, market: str
    ) -> dict:
        """
        Get detailed analysis for a specific market.

        Args:
            df: DataFrame with analyzed COT data
            market: Market name to analyze

        Returns:
            Dictionary with analysis results
        """
        market_df = df[df["market"] == market].copy()

        if market_df.empty:
            return {"error": f"Market '{market}' not found"}

        latest = market_df.iloc[-1]

        return {
            "market": market,
            "date": latest["date"],
            "open_interest": int(latest["open_interest"]),
            "commercial_net": int(latest.get("commercial_net", 0)),
            "commercial_net_pct": float(latest.get("commercial_net_pct", 0)),
            "commercial_percentile": float(latest.get("commercial_net_pct_percentile", 0)),
            "small_spec_net": int(latest.get("small_spec_net", 0)),
            "small_spec_net_pct": float(latest.get("small_spec_net_pct", 0)),
            "small_spec_percentile": float(latest.get("small_spec_net_pct_percentile", 0)),
            "large_spec_net": int(latest.get("large_spec_net", 0)),
            "large_spec_net_pct": float(latest.get("large_spec_net_pct", 0)),
            "divergence": float(latest.get("divergence", 0)),
            "divergence_percentile": float(latest.get("divergence_percentile", 0)),
            "history": market_df[
                ["date", "commercial_net_pct", "small_spec_net_pct", "divergence"]
            ].to_dict("records"),
        }

    def run_full_analysis(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Run complete analysis pipeline on COT data.

        Args:
            df: Raw parsed COT DataFrame with derived fields

        Returns:
            DataFrame with all analysis columns
        """
        # Calculate divergence
        df = self.calculate_divergence(df)

        # Calculate percentiles
        df = self.calculate_percentiles(df)

        # Identify extreme readings
        df = self.identify_extreme_readings(df)

        return df

    def get_market_summary(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate summary statistics for all markets.

        Args:
            df: Analyzed DataFrame

        Returns:
            Summary DataFrame with one row per market
        """
        latest = self.get_latest_readings(df)

        summary_cols = [
            "market",
            "date",
            "open_interest",
            "commercial_net_pct",
            "commercial_net_pct_percentile",
            "small_spec_net_pct",
            "small_spec_net_pct_percentile",
            "divergence",
            "divergence_percentile",
        ]

        # Only select columns that exist
        available_cols = [c for c in summary_cols if c in latest.columns]
        summary = latest[available_cols].copy()

        # Sort by divergence percentile (most extreme first)
        if "divergence_percentile" in summary.columns:
            summary = summary.sort_values(
                "divergence_percentile", ascending=False
            ).reset_index(drop=True)

        return summary

    def calculate_z_scores(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate z-scores for key metrics within each market.

        Args:
            df: DataFrame with COT data

        Returns:
            DataFrame with z-score columns
        """
        df = df.copy()

        z_score_cols = [
            "commercial_net_pct",
            "small_spec_net_pct",
            "divergence",
        ]

        for col in z_score_cols:
            if col not in df.columns:
                continue

            z_col = f"{col}_zscore"
            df[z_col] = df.groupby("market")[col].transform(
                lambda x: (x - x.mean()) / x.std() if x.std() > 0 else 0
            )

        return df

    def get_correlation_matrix(self, df: pd.DataFrame, market: str) -> pd.DataFrame:
        """
        Get correlation matrix of position changes for a market.

        Args:
            df: DataFrame with COT data
            market: Market to analyze

        Returns:
            Correlation matrix DataFrame
        """
        market_df = df[df["market"] == market].copy()

        if market_df.empty:
            return pd.DataFrame()

        # Calculate week-over-week changes
        change_cols = ["commercial_net", "small_spec_net", "large_spec_net"]
        available_cols = [c for c in change_cols if c in market_df.columns]

        for col in available_cols:
            market_df[f"{col}_change"] = market_df[col].diff()

        change_cols_suffixed = [f"{c}_change" for c in available_cols]
        return market_df[change_cols_suffixed].corr()

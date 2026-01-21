"""Parse COT data files into DataFrames."""

from pathlib import Path
from typing import Optional

import pandas as pd

from .config import Config, default_config, get_contract_name_mapping, get_enabled_display_names


class COTParser:
    """Parse COT data files into structured DataFrames."""

    # Legacy report columns of interest (using actual CFTC column names)
    LEGACY_COLUMNS = {
        "Market and Exchange Names": "market",
        "As of Date in Form YYMMDD": "date",
        "Open Interest (All)": "open_interest",
        "Commercial Positions-Long (All)": "commercial_long",
        "Commercial Positions-Short (All)": "commercial_short",
        "Noncommercial Positions-Long (All)": "large_spec_long",
        "Noncommercial Positions-Short (All)": "large_spec_short",
        "Nonreportable Positions-Long (All)": "small_spec_long",
        "Nonreportable Positions-Short (All)": "small_spec_short",
        "Concentration-Gross LT = 4 TDR-Long (All)": "top4_long",
        "Concentration-Gross LT =4 TDR-Short (All)": "top4_short",
        "Concentration-Gross LT =8 TDR-Long (All)": "top8_long",
        "Concentration-Gross LT =8 TDR-Short (All)": "top8_short",
    }

    # Disaggregated report columns of interest (using actual CFTC column names)
    DISAGG_COLUMNS = {
        "Market_and_Exchange_Names": "market",
        "As_of_Date_In_Form_YYMMDD": "date",
        "Open_Interest_All": "open_interest",
        "Prod_Merc_Positions_Long_All": "producer_long",
        "Prod_Merc_Positions_Short_All": "producer_short",
        "Swap_Positions_Long_All": "swap_long",
        "Swap__Positions_Short_All": "swap_short",
        "M_Money_Positions_Long_All": "managed_money_long",
        "M_Money_Positions_Short_All": "managed_money_short",
        "Other_Rept_Positions_Long_All": "other_reportable_long",
        "Other_Rept_Positions_Short_All": "other_reportable_short",
        "NonRept_Positions_Long_All": "nonreportable_long",
        "NonRept_Positions_Short_All": "nonreportable_short",
    }

    def __init__(self, config: Optional[Config] = None):
        self.config = config or default_config

    def parse_legacy_file(self, filepath: Path) -> pd.DataFrame:
        """
        Parse a single Legacy COT report file.

        Args:
            filepath: Path to the Legacy COT text file

        Returns:
            DataFrame with parsed data
        """
        # Read the CSV file
        df = pd.read_csv(filepath, low_memory=False)

        # Select and rename columns
        available_cols = {k: v for k, v in self.LEGACY_COLUMNS.items() if k in df.columns}
        df = df[list(available_cols.keys())].rename(columns=available_cols)

        # Parse date
        df["date"] = pd.to_datetime(df["date"], format="%y%m%d")

        # Clean market names
        df["market"] = df["market"].apply(self._normalize_market_name)

        # Sort by date
        df = df.sort_values("date").reset_index(drop=True)

        return df

    def parse_disaggregated_file(self, filepath: Path) -> pd.DataFrame:
        """
        Parse a single Disaggregated COT report file.

        Args:
            filepath: Path to the Disaggregated COT text file

        Returns:
            DataFrame with parsed data
        """
        # Read the CSV file
        df = pd.read_csv(filepath, low_memory=False)

        # Select and rename columns
        available_cols = {k: v for k, v in self.DISAGG_COLUMNS.items() if k in df.columns}
        df = df[list(available_cols.keys())].rename(columns=available_cols)

        # Parse date
        df["date"] = pd.to_datetime(df["date"], format="%y%m%d")

        # Clean market names
        df["market"] = df["market"].apply(self._normalize_market_name)

        # Sort by date
        df = df.sort_values("date").reset_index(drop=True)

        return df

    def parse_all_legacy(self, filepaths: list[Path]) -> pd.DataFrame:
        """
        Parse and combine multiple Legacy COT files.

        Args:
            filepaths: List of paths to Legacy COT files

        Returns:
            Combined DataFrame
        """
        dfs = []
        for fp in filepaths:
            try:
                df = self.parse_legacy_file(fp)
                dfs.append(df)
            except Exception as e:
                print(f"Error parsing {fp}: {e}")

        if not dfs:
            return pd.DataFrame()

        combined = pd.concat(dfs, ignore_index=True)
        combined = combined.drop_duplicates(subset=["market", "date"])
        combined = combined.sort_values(["market", "date"]).reset_index(drop=True)

        # Filter by date if configured
        start_date = self.config.historical_start_date
        combined = combined[combined["date"] >= start_date]

        # Filter to only enabled contracts from contracts.json
        enabled_names = get_enabled_display_names()
        if enabled_names:
            combined = combined[combined["market"].isin(enabled_names)]

        # Filter by additional markets if configured
        if self.config.markets_filter:
            combined = combined[combined["market"].isin(self.config.markets_filter)]

        return combined

    def parse_all_disaggregated(self, filepaths: list[Path]) -> pd.DataFrame:
        """
        Parse and combine multiple Disaggregated COT files.

        Args:
            filepaths: List of paths to Disaggregated COT files

        Returns:
            Combined DataFrame
        """
        dfs = []
        for fp in filepaths:
            try:
                df = self.parse_disaggregated_file(fp)
                dfs.append(df)
            except Exception as e:
                print(f"Error parsing {fp}: {e}")

        if not dfs:
            return pd.DataFrame()

        combined = pd.concat(dfs, ignore_index=True)
        combined = combined.drop_duplicates(subset=["market", "date"])
        combined = combined.sort_values(["market", "date"]).reset_index(drop=True)

        # Filter by date if configured
        start_date = self.config.historical_start_date
        combined = combined[combined["date"] >= start_date]

        # Filter to only enabled contracts from contracts.json
        enabled_names = get_enabled_display_names()
        if enabled_names:
            combined = combined[combined["market"].isin(enabled_names)]

        # Filter by additional markets if configured
        if self.config.markets_filter:
            combined = combined[combined["market"].isin(self.config.markets_filter)]

        return combined

    def _normalize_market_name(self, name: str) -> str:
        """
        Normalize market names for consistency using contracts.json config.

        Args:
            name: Raw market name from CFTC data

        Returns:
            Normalized market name
        """
        if not isinstance(name, str):
            return str(name)

        # Load name mapping from contracts.json (only enabled contracts)
        replacements = get_contract_name_mapping()

        return replacements.get(name, name)

    def get_available_markets(self, df: pd.DataFrame) -> list[str]:
        """
        Get list of unique markets in the data.

        Args:
            df: DataFrame with parsed COT data

        Returns:
            Sorted list of market names
        """
        return sorted(df["market"].unique().tolist())

    def calculate_derived_fields(self, df: pd.DataFrame, report_type: str = "legacy") -> pd.DataFrame:
        """
        Calculate derived fields like net positions and percentages.

        Args:
            df: DataFrame with parsed COT data
            report_type: 'legacy' or 'disaggregated'

        Returns:
            DataFrame with additional calculated columns
        """
        df = df.copy()

        if report_type == "legacy":
            # Net positions
            df["commercial_net"] = df["commercial_long"] - df["commercial_short"]
            df["large_spec_net"] = df["large_spec_long"] - df["large_spec_short"]
            df["small_spec_net"] = df["small_spec_long"] - df["small_spec_short"]

            # Net position as % of open interest
            df["commercial_net_pct"] = df["commercial_net"] / df["open_interest"]
            df["large_spec_net_pct"] = df["large_spec_net"] / df["open_interest"]
            df["small_spec_net_pct"] = df["small_spec_net"] / df["open_interest"]

            # Long/Short ratios
            df["commercial_ls_ratio"] = df["commercial_long"] / df["commercial_short"].replace(0, 1)
            df["small_spec_ls_ratio"] = df["small_spec_long"] / df["small_spec_short"].replace(0, 1)

        elif report_type == "disaggregated":
            # Net positions
            df["producer_net"] = df["producer_long"] - df["producer_short"]
            df["swap_net"] = df["swap_long"] - df["swap_short"]
            df["managed_money_net"] = df["managed_money_long"] - df["managed_money_short"]
            df["nonreportable_net"] = df["nonreportable_long"] - df["nonreportable_short"]

            # Net position as % of open interest
            df["producer_net_pct"] = df["producer_net"] / df["open_interest"]
            df["swap_net_pct"] = df["swap_net"] / df["open_interest"]
            df["managed_money_net_pct"] = df["managed_money_net"] / df["open_interest"]
            df["nonreportable_net_pct"] = df["nonreportable_net"] / df["open_interest"]

        return df

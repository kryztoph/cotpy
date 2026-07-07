"""Configuration settings for COT data analysis."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional


def load_contracts_config(config_path: Path = None) -> dict:
    """Load contracts configuration from JSON file."""
    if config_path is None:
        config_path = Path(__file__).parent.parent / "contracts.json"

    if not config_path.exists():
        return {"contracts": []}

    with open(config_path) as f:
        return json.load(f)


def get_enabled_contracts(config_path: Path = None) -> list[dict]:
    """Get list of enabled contracts."""
    data = load_contracts_config(config_path)
    return [c for c in data.get("contracts", []) if c.get("enabled", True)]


def get_contract_name_mapping(config_path: Path = None) -> dict[str, str]:
    """Get mapping of CFTC names to display names for enabled contracts."""
    contracts = get_enabled_contracts(config_path)
    return {c["cftc_name"]: c["display_name"] for c in contracts}


def get_enabled_display_names(config_path: Path = None) -> list[str]:
    """Get list of enabled display names for filtering."""
    contracts = get_enabled_contracts(config_path)
    return [c["display_name"] for c in contracts]


def get_key_markets(config_path: Path = None) -> list[str]:
    """Get list of key market display names for watchlist."""
    contracts = get_enabled_contracts(config_path)
    return [c["display_name"] for c in contracts if c.get("key_market", False)]


@dataclass
class Config:
    """Configuration for COT analysis tool."""

    # Paths
    data_dir: Path = field(default_factory=lambda: Path("data"))
    output_dir: Path = field(default_factory=lambda: Path("output"))
    charts_dir: Path = field(default_factory=lambda: Path("output/charts"))

    # Divergence thresholds (as percentage of open interest)
    divergence_threshold_bullish: float = 0.10  # 10% net long commercials
    divergence_threshold_bearish: float = -0.10  # 10% net short commercials

    # Historical percentile thresholds for extreme readings
    percentile_high: float = 90.0  # Above this = extremely bullish
    percentile_low: float = 10.0  # Below this = extremely bearish

    # Lookback period for analysis
    lookback_years: int = 1
    historical_years: int = 3  # Years of data to use for percentile calculations

    # Markets to track (empty = all markets)
    markets_filter: list[str] = field(default_factory=list)

    # CFTC data URLs
    legacy_url_template: str = (
        "https://www.cftc.gov/files/dea/history/deacot{year}.zip"
    )
    disaggregated_url_template: str = (
        "https://www.cftc.gov/files/dea/history/fut_disagg_txt_{year}.zip"
    )
    current_legacy_url: str = "https://www.cftc.gov/dea/newcot/deafut.txt"
    current_disaggregated_url: str = "https://www.cftc.gov/dea/newcot/f_disagg.txt"

    # Signal thresholds
    # Commercials net long + small specs net short = bullish
    commercial_net_threshold: float = 0.05  # 5% of OI
    small_spec_net_threshold: float = -0.03  # -3% of OI (net short)

    def __post_init__(self):
        """Ensure paths exist."""
        self.data_dir = Path(self.data_dir)
        self.output_dir = Path(self.output_dir)
        self.charts_dir = Path(self.charts_dir)

        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.charts_dir.mkdir(parents=True, exist_ok=True)

    @property
    def start_date(self) -> datetime:
        """Calculate start date based on lookback period."""
        return datetime.now() - timedelta(days=365 * self.lookback_years)

    @property
    def historical_start_date(self) -> datetime:
        """Calculate start date for historical percentile calculations."""
        return datetime.now() - timedelta(days=365 * self.historical_years)

    def get_years_to_fetch(self) -> list[int]:
        """Get list of years to fetch data for."""
        current_year = datetime.now().year
        start_year = current_year - self.historical_years
        return list(range(start_year, current_year + 1))

    def get_legacy_url(self, year: int) -> str:
        """Get URL for Legacy COT report."""
        return self.legacy_url_template.format(year=year)

    def get_disaggregated_url(self, year: int) -> str:
        """Get URL for Disaggregated COT report."""
        return self.disaggregated_url_template.format(year=year)

    def get_current_legacy_url(self) -> str:
        """Get URL for current-week Legacy futures COT report."""
        return self.current_legacy_url

    def get_current_disaggregated_url(self) -> str:
        """Get URL for current-week Disaggregated futures COT report."""
        return self.current_disaggregated_url


# Default configuration instance
default_config = Config()

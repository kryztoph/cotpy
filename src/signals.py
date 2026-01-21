"""Generate trading signals from COT analysis."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import pandas as pd

from .config import Config, default_config


class SignalType(Enum):
    """Types of trading signals."""

    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class SignalStrength(Enum):
    """Strength of trading signals."""

    STRONG = "STRONG"
    MODERATE = "MODERATE"
    WEAK = "WEAK"


@dataclass
class Signal:
    """A trading signal based on COT analysis."""

    market: str
    date: pd.Timestamp
    signal_type: SignalType
    strength: SignalStrength
    commercial_net_pct: float
    small_spec_net_pct: float
    divergence: float
    divergence_percentile: float
    description: str

    def to_dict(self) -> dict:
        """Convert signal to dictionary."""
        return {
            "market": self.market,
            "date": self.date,
            "signal": self.signal_type.value,
            "strength": self.strength.value,
            "commercial_net_pct": self.commercial_net_pct,
            "small_spec_net_pct": self.small_spec_net_pct,
            "divergence": self.divergence,
            "divergence_percentile": self.divergence_percentile,
            "description": self.description,
        }


class SignalGenerator:
    """Generate trading signals from COT data analysis."""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or default_config

    def generate_signals(self, df: pd.DataFrame) -> list[Signal]:
        """
        Generate trading signals from analyzed COT data.

        Signal logic:
        - BULLISH: Commercials heavily net long + Small specs heavily net short
        - BEARISH: Commercials heavily net short + Small specs heavily net long

        Args:
            df: Analyzed DataFrame with latest readings per market

        Returns:
            List of Signal objects
        """
        signals = []

        for _, row in df.iterrows():
            signal = self._evaluate_row(row)
            if signal.signal_type != SignalType.NEUTRAL:
                signals.append(signal)

        # Sort by divergence percentile (most extreme first)
        signals.sort(key=lambda s: abs(s.divergence_percentile - 50), reverse=True)

        return signals

    def _evaluate_row(self, row: pd.Series) -> Signal:
        """
        Evaluate a single market row for signals.

        Args:
            row: Single row from DataFrame

        Returns:
            Signal object
        """
        market = row["market"]
        date = row["date"]
        commercial_net_pct = row.get("commercial_net_pct", 0)
        small_spec_net_pct = row.get("small_spec_net_pct", 0)
        divergence = row.get("divergence", 0)
        divergence_percentile = row.get("divergence_percentile", 50)

        # Check for extreme readings using percentiles
        comm_percentile = row.get("commercial_net_pct_percentile", 50)
        small_spec_percentile = row.get("small_spec_net_pct_percentile", 50)

        high = self.config.percentile_high
        low = self.config.percentile_low

        signal_type = SignalType.NEUTRAL
        strength = SignalStrength.WEAK
        description = "No significant divergence detected"

        # Bullish: Commercials extremely net long + Small specs extremely net short
        if comm_percentile >= high and small_spec_percentile <= low:
            signal_type = SignalType.BULLISH
            strength = SignalStrength.STRONG
            description = (
                f"Strong bullish: Commercials at {comm_percentile:.0f}th percentile (net long), "
                f"Small specs at {small_spec_percentile:.0f}th percentile (net short)"
            )
        elif comm_percentile >= 75 and small_spec_percentile <= 25:
            signal_type = SignalType.BULLISH
            strength = SignalStrength.MODERATE
            description = (
                f"Moderate bullish: Commercials at {comm_percentile:.0f}th percentile, "
                f"Small specs at {small_spec_percentile:.0f}th percentile"
            )
        # Bearish: Commercials extremely net short + Small specs extremely net long
        elif comm_percentile <= low and small_spec_percentile >= high:
            signal_type = SignalType.BEARISH
            strength = SignalStrength.STRONG
            description = (
                f"Strong bearish: Commercials at {comm_percentile:.0f}th percentile (net short), "
                f"Small specs at {small_spec_percentile:.0f}th percentile (net long)"
            )
        elif comm_percentile <= 25 and small_spec_percentile >= 75:
            signal_type = SignalType.BEARISH
            strength = SignalStrength.MODERATE
            description = (
                f"Moderate bearish: Commercials at {comm_percentile:.0f}th percentile, "
                f"Small specs at {small_spec_percentile:.0f}th percentile"
            )
        # Check divergence percentile for weaker signals
        elif divergence_percentile >= high:
            signal_type = SignalType.BULLISH
            strength = SignalStrength.WEAK
            description = (
                f"Weak bullish: Divergence at {divergence_percentile:.0f}th percentile"
            )
        elif divergence_percentile <= low:
            signal_type = SignalType.BEARISH
            strength = SignalStrength.WEAK
            description = (
                f"Weak bearish: Divergence at {divergence_percentile:.0f}th percentile"
            )

        return Signal(
            market=market,
            date=date,
            signal_type=signal_type,
            strength=strength,
            commercial_net_pct=commercial_net_pct,
            small_spec_net_pct=small_spec_net_pct,
            divergence=divergence,
            divergence_percentile=divergence_percentile,
            description=description,
        )

    def signals_to_dataframe(self, signals: list[Signal]) -> pd.DataFrame:
        """
        Convert list of signals to DataFrame.

        Args:
            signals: List of Signal objects

        Returns:
            DataFrame with signal data
        """
        if not signals:
            return pd.DataFrame(
                columns=[
                    "market",
                    "date",
                    "signal",
                    "strength",
                    "commercial_net_pct",
                    "small_spec_net_pct",
                    "divergence",
                    "divergence_percentile",
                    "description",
                ]
            )

        return pd.DataFrame([s.to_dict() for s in signals])

    def filter_signals(
        self,
        signals: list[Signal],
        signal_type: Optional[SignalType] = None,
        min_strength: Optional[SignalStrength] = None,
        markets: Optional[list[str]] = None,
    ) -> list[Signal]:
        """
        Filter signals by criteria.

        Args:
            signals: List of signals to filter
            signal_type: Filter by signal type (BULLISH/BEARISH)
            min_strength: Minimum signal strength
            markets: List of markets to include

        Returns:
            Filtered list of signals
        """
        filtered = signals.copy()

        if signal_type:
            filtered = [s for s in filtered if s.signal_type == signal_type]

        if min_strength:
            strength_order = {
                SignalStrength.WEAK: 1,
                SignalStrength.MODERATE: 2,
                SignalStrength.STRONG: 3,
            }
            min_order = strength_order[min_strength]
            filtered = [s for s in filtered if strength_order[s.strength] >= min_order]

        if markets:
            filtered = [s for s in filtered if s.market in markets]

        return filtered

    def get_signal_summary(self, signals: list[Signal]) -> dict:
        """
        Get summary statistics for a list of signals.

        Args:
            signals: List of signals

        Returns:
            Dictionary with summary stats
        """
        if not signals:
            return {
                "total": 0,
                "bullish": 0,
                "bearish": 0,
                "strong": 0,
                "moderate": 0,
                "weak": 0,
            }

        return {
            "total": len(signals),
            "bullish": sum(1 for s in signals if s.signal_type == SignalType.BULLISH),
            "bearish": sum(1 for s in signals if s.signal_type == SignalType.BEARISH),
            "strong": sum(1 for s in signals if s.strength == SignalStrength.STRONG),
            "moderate": sum(1 for s in signals if s.strength == SignalStrength.MODERATE),
            "weak": sum(1 for s in signals if s.strength == SignalStrength.WEAK),
        }

    def format_signals_report(self, signals: list[Signal]) -> str:
        """
        Format signals into a readable text report.

        Args:
            signals: List of signals

        Returns:
            Formatted report string
        """
        if not signals:
            return "No significant signals detected."

        lines = ["=" * 60, "COT DIVERGENCE SIGNALS", "=" * 60, ""]

        summary = self.get_signal_summary(signals)
        lines.append(f"Total signals: {summary['total']}")
        lines.append(f"  Bullish: {summary['bullish']}")
        lines.append(f"  Bearish: {summary['bearish']}")
        lines.append("")
        lines.append("-" * 60)

        for signal in signals:
            emoji = "🟢" if signal.signal_type == SignalType.BULLISH else "🔴"
            lines.append(f"\n{emoji} {signal.market}")
            lines.append(f"   Date: {signal.date.strftime('%Y-%m-%d')}")
            lines.append(f"   Signal: {signal.signal_type.value} ({signal.strength.value})")
            lines.append(f"   Commercial Net: {signal.commercial_net_pct:.1%}")
            lines.append(f"   Small Spec Net: {signal.small_spec_net_pct:.1%}")
            lines.append(f"   Divergence Percentile: {signal.divergence_percentile:.0f}")
            lines.append(f"   {signal.description}")

        lines.append("\n" + "=" * 60)
        return "\n".join(lines)

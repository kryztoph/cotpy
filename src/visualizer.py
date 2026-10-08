"""Visualization tools for COT data analysis."""

from pathlib import Path
from typing import Optional
from html import escape
from urllib.parse import quote

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .config import Config, default_config, get_enabled_contracts, get_key_markets


class COTVisualizer:
    """Create visualizations for COT data analysis."""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or default_config
        self._setup_style()

    def _setup_style(self):
        """Set up matplotlib style."""
        plt.style.use("seaborn-v0_8-darkgrid")
        sns.set_palette("husl")

    # =========================================================================
    # Matplotlib / Seaborn Charts (Static)
    # =========================================================================

    def plot_net_positions(
        self,
        df: pd.DataFrame,
        market: str,
        save_path: Optional[Path] = None,
    ) -> plt.Figure:
        """
        Plot time series of net positions by trader type.

        Args:
            df: DataFrame with COT data
            market: Market to plot
            save_path: Optional path to save the figure

        Returns:
            matplotlib Figure object
        """
        market_df = df[df["market"] == market].copy()

        if market_df.empty:
            raise ValueError(f"No data found for market: {market}")

        fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

        # Top: Net positions as % of OI
        ax1 = axes[0]
        ax1.plot(
            market_df["date"],
            market_df["commercial_net_pct"] * 100,
            label="Commercials",
            linewidth=2,
            color="blue",
        )
        ax1.plot(
            market_df["date"],
            market_df["small_spec_net_pct"] * 100,
            label="Small Speculators",
            linewidth=2,
            color="red",
        )
        ax1.plot(
            market_df["date"],
            market_df["large_spec_net_pct"] * 100,
            label="Large Speculators",
            linewidth=1.5,
            color="green",
            alpha=0.7,
        )
        ax1.axhline(y=0, color="black", linestyle="-", linewidth=0.5)
        ax1.set_ylabel("Net Position (% of OI)")
        ax1.set_title(f"{market} - Net Positions by Trader Type")
        ax1.legend(loc="upper left")
        ax1.grid(True, alpha=0.3)

        # Bottom: Divergence
        ax2 = axes[1]
        divergence = market_df["divergence"] * 100
        colors = ["green" if d > 0 else "red" for d in divergence]
        ax2.bar(market_df["date"], divergence, color=colors, alpha=0.7, width=5)
        ax2.axhline(y=0, color="black", linestyle="-", linewidth=0.5)
        ax2.set_ylabel("Divergence (%)")
        ax2.set_xlabel("Date")
        ax2.set_title("Commercial vs Small Spec Divergence")
        ax2.grid(True, alpha=0.3)

        plt.tight_layout()

        if save_path:
            fig.savefig(save_path, dpi=150, bbox_inches="tight")
            print(f"Saved chart to {save_path}")

        return fig

    def plot_divergence_heatmap(
        self,
        df: pd.DataFrame,
        save_path: Optional[Path] = None,
    ) -> plt.Figure:
        """
        Create heatmap of divergence percentiles across markets.

        Args:
            df: DataFrame with latest readings per market
            save_path: Optional path to save the figure

        Returns:
            matplotlib Figure object
        """
        # Prepare data for heatmap
        heatmap_data = df[["market", "divergence_percentile"]].copy()
        heatmap_data = heatmap_data.sort_values("divergence_percentile", ascending=False)

        # Limit to top 30 markets for readability
        heatmap_data = heatmap_data.head(30)

        fig, ax = plt.subplots(figsize=(10, max(8, len(heatmap_data) * 0.3)))

        # Create color map (red = bearish, green = bullish)
        values = heatmap_data["divergence_percentile"].values.reshape(-1, 1)

        sns.heatmap(
            values,
            ax=ax,
            cmap="RdYlGn",
            vmin=0,
            vmax=100,
            annot=True,
            fmt=".0f",
            yticklabels=heatmap_data["market"].values,
            xticklabels=["Divergence Percentile"],
            cbar_kws={"label": "Percentile (100=Bullish, 0=Bearish)"},
        )

        ax.set_title("COT Divergence Heatmap by Market")
        plt.tight_layout()

        if save_path:
            fig.savefig(save_path, dpi=150, bbox_inches="tight")
            print(f"Saved heatmap to {save_path}")

        return fig

    def plot_signal_summary(
        self,
        signals_df: pd.DataFrame,
        save_path: Optional[Path] = None,
    ) -> plt.Figure:
        """
        Create bar chart summarizing signals.

        Args:
            signals_df: DataFrame with signal data
            save_path: Optional path to save the figure

        Returns:
            matplotlib Figure object
        """
        if signals_df.empty:
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.text(0.5, 0.5, "No signals to display", ha="center", va="center")
            return fig

        fig, ax = plt.subplots(figsize=(12, max(6, len(signals_df) * 0.4)))

        # Color by signal type
        colors = signals_df["signal"].map({"BULLISH": "green", "BEARISH": "red"}).values

        # Plot horizontal bars
        y_pos = range(len(signals_df))
        bars = ax.barh(
            y_pos,
            signals_df["divergence_percentile"],
            color=colors,
            alpha=0.7,
        )

        # Add strength indicators
        for i, (idx, row) in enumerate(signals_df.iterrows()):
            strength_marker = {"STRONG": "***", "MODERATE": "**", "WEAK": "*"}.get(
                row["strength"], ""
            )
            ax.text(
                row["divergence_percentile"] + 2,
                i,
                strength_marker,
                va="center",
                fontweight="bold",
            )

        ax.set_yticks(y_pos)
        ax.set_yticklabels(signals_df["market"])
        ax.set_xlabel("Divergence Percentile")
        ax.set_title("COT Signal Summary (* = weak, ** = moderate, *** = strong)")
        ax.axvline(x=50, color="black", linestyle="--", alpha=0.5)
        ax.set_xlim(0, 105)
        ax.grid(True, alpha=0.3, axis="x")

        plt.tight_layout()

        if save_path:
            fig.savefig(save_path, dpi=150, bbox_inches="tight")
            print(f"Saved signal summary to {save_path}")

        return fig

    # =========================================================================
    # Plotly Charts (Interactive)
    # =========================================================================

    def plot_interactive_positions(
        self,
        df: pd.DataFrame,
        market: str,
        save_path: Optional[Path] = None,
    ) -> go.Figure:
        """
        Create interactive time series with Plotly.

        Args:
            df: DataFrame with COT data
            market: Market to plot
            save_path: Optional path to save HTML

        Returns:
            Plotly Figure object
        """
        market_df = df[df["market"] == market].copy()

        if market_df.empty:
            raise ValueError(f"No data found for market: {market}")

        fig = make_subplots(
            rows=3,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.08,
            subplot_titles=(
                "Net Positions (% of OI)",
                "Divergence",
                "Open Interest",
            ),
            row_heights=[0.45, 0.35, 0.2],
        )

        # Net positions
        fig.add_trace(
            go.Scatter(
                x=market_df["date"],
                y=market_df["commercial_net_pct"] * 100,
                name="Commercials",
                line=dict(color="blue", width=2),
                hovertemplate="%{y:.1f}%<extra>Commercials</extra>",
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=market_df["date"],
                y=market_df["small_spec_net_pct"] * 100,
                name="Small Specs",
                line=dict(color="red", width=2),
                hovertemplate="%{y:.1f}%<extra>Small Specs</extra>",
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=market_df["date"],
                y=market_df["large_spec_net_pct"] * 100,
                name="Large Specs",
                line=dict(color="green", width=1.5, dash="dot"),
                hovertemplate="%{y:.1f}%<extra>Large Specs</extra>",
            ),
            row=1,
            col=1,
        )

        # Divergence
        colors = [
            "green" if d > 0 else "red" for d in market_df["divergence"]
        ]
        fig.add_trace(
            go.Bar(
                x=market_df["date"],
                y=market_df["divergence"] * 100,
                name="Divergence",
                marker_color=colors,
                hovertemplate="%{y:.1f}%<extra>Divergence</extra>",
            ),
            row=2,
            col=1,
        )

        # Open Interest
        fig.add_trace(
            go.Scatter(
                x=market_df["date"],
                y=market_df["open_interest"],
                name="Open Interest",
                fill="tozeroy",
                line=dict(color="purple", width=1),
                hovertemplate="%{y:,.0f}<extra>Open Interest</extra>",
            ),
            row=3,
            col=1,
        )

        fig.update_layout(
            title=f"{market} - COT Analysis",
            height=800,
            showlegend=True,
            legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
            hovermode="x unified",
        )

        fig.update_yaxes(title_text="% of OI", row=1, col=1)
        fig.update_yaxes(title_text="Divergence %", row=2, col=1)
        fig.update_yaxes(title_text="Contracts", row=3, col=1)

        # Add zero line
        fig.add_hline(y=0, line_dash="dash", line_color="gray", row=1, col=1)
        fig.add_hline(y=0, line_dash="dash", line_color="gray", row=2, col=1)

        if save_path:
            fig.write_html(save_path)
            print(f"Saved interactive chart to {save_path}")

        return fig

    def plot_market_comparison(
        self,
        df: pd.DataFrame,
        save_path: Optional[Path] = None,
    ) -> go.Figure:
        """
        Create interactive scatter plot comparing markets.

        Args:
            df: DataFrame with latest readings per market
            save_path: Optional path to save HTML

        Returns:
            Plotly Figure object
        """
        fig = go.Figure()

        # Color by divergence percentile
        fig.add_trace(
            go.Scatter(
                x=df["commercial_net_pct"] * 100,
                y=df["small_spec_net_pct"] * 100,
                mode="markers+text",
                text=df["market"],
                textposition="top center",
                marker=dict(
                    size=12,
                    color=df["divergence_percentile"],
                    colorscale="RdYlGn",
                    colorbar=dict(title="Divergence<br>Percentile"),
                    line=dict(width=1, color="black"),
                ),
                hovertemplate=(
                    "<b>%{text}</b><br>"
                    "Commercial Net: %{x:.1f}%<br>"
                    "Small Spec Net: %{y:.1f}%<br>"
                    "<extra></extra>"
                ),
            )
        )

        # Add quadrant lines
        fig.add_hline(y=0, line_dash="dash", line_color="gray")
        fig.add_vline(x=0, line_dash="dash", line_color="gray")

        # Add quadrant labels
        fig.add_annotation(
            x=max(df["commercial_net_pct"]) * 50,
            y=min(df["small_spec_net_pct"]) * 50,
            text="BULLISH<br>(Comm Long, Specs Short)",
            showarrow=False,
            font=dict(size=12, color="green"),
        )
        fig.add_annotation(
            x=min(df["commercial_net_pct"]) * 50,
            y=max(df["small_spec_net_pct"]) * 50,
            text="BEARISH<br>(Comm Short, Specs Long)",
            showarrow=False,
            font=dict(size=12, color="red"),
        )

        fig.update_layout(
            title="Market Positioning Comparison",
            xaxis_title="Commercial Net Position (% of OI)",
            yaxis_title="Small Spec Net Position (% of OI)",
            height=700,
            showlegend=False,
        )

        if save_path:
            fig.write_html(save_path)
            print(f"Saved comparison chart to {save_path}")

        return fig

    def _interactive_chart_filename(self, market: str) -> str:
        """Return the standard interactive chart filename for a market."""
        safe_name = market.replace("/", "_").replace(" ", "_")
        return f"{safe_name}_interactive.html"

    def _signal_label(self, divergence_percentile: float) -> str:
        """Translate divergence percentile into a dashboard-friendly label."""
        if divergence_percentile >= 90:
            return "Strong Bullish"
        if divergence_percentile >= 75:
            return "Lean Bullish"
        if divergence_percentile <= 10:
            return "Strong Bearish"
        if divergence_percentile <= 25:
            return "Lean Bearish"
        return "Neutral"

    def _signal_color(self, divergence_percentile: float) -> str:
        """Return a cell color for the signal label."""
        if divergence_percentile >= 90:
            return "rgba(30, 132, 73, 0.22)"
        if divergence_percentile >= 75:
            return "rgba(88, 214, 141, 0.18)"
        if divergence_percentile <= 10:
            return "rgba(192, 57, 43, 0.22)"
        if divergence_percentile <= 25:
            return "rgba(236, 112, 99, 0.18)"
        return "rgba(215, 219, 221, 0.22)"

    def _latest_with_drilldown_fields(self, df: pd.DataFrame) -> pd.DataFrame:
        """Build latest market rows with category, key-market, and change fields."""
        sorted_df = df.sort_values(["market", "date"]).copy()
        latest = sorted_df.groupby("market", as_index=False).tail(1).reset_index(drop=True)

        contracts = get_enabled_contracts()
        category_by_market = {
            contract["display_name"]: contract.get("category", "other")
            for contract in contracts
        }
        key_markets = set(get_key_markets())

        changes = {}
        for market, market_df in sorted_df.groupby("market"):
            current = market_df.iloc[-1]
            cutoff = current["date"] - pd.Timedelta(days=28)
            previous = market_df[market_df["date"] <= cutoff]
            if previous.empty:
                changes[market] = np.nan
            else:
                changes[market] = (
                    current.get("divergence_percentile", np.nan)
                    - previous.iloc[-1].get("divergence_percentile", np.nan)
                )

        latest["category"] = latest["market"].map(category_by_market).fillna("other")
        latest["category_label"] = latest["category"].str.replace("_", " ").str.title()
        latest["is_key_market"] = latest["market"].isin(key_markets)
        latest["signal_label"] = latest["divergence_percentile"].apply(self._signal_label)
        latest["signal_color"] = latest["divergence_percentile"].apply(self._signal_color)
        latest["divergence_change_4w"] = latest["market"].map(changes)
        latest["intent_score"] = latest["divergence_percentile"] - 50
        latest["chart_link"] = latest["market"].apply(
            lambda market: (
                f'<a href="{escape(quote(self._interactive_chart_filename(market), safe=""))}">'
                f'{escape(market)}</a>'
            )
        )

        return latest

    def create_dashboard(
        self,
        df: pd.DataFrame,
        signals_df: pd.DataFrame,
        save_path: Optional[Path] = None,
    ) -> go.Figure:
        """
        Create comprehensive dashboard with multiple views.

        Args:
            df: Analyzed DataFrame with all data
            signals_df: DataFrame with signals
            save_path: Optional path to save HTML

        Returns:
            Plotly Figure object
        """
        latest = self._latest_with_drilldown_fields(df)
        most_recent = latest["date"].max()

        strong_bull = len(
            signals_df[
                (signals_df["signal"] == "BULLISH")
                & (signals_df["strength"] == "STRONG")
            ]
        ) if not signals_df.empty else 0
        strong_bear = len(
            signals_df[
                (signals_df["signal"] == "BEARISH")
                & (signals_df["strength"] == "STRONG")
            ]
        ) if not signals_df.empty else 0
        moderate_bull = len(
            signals_df[
                (signals_df["signal"] == "BULLISH")
                & (signals_df["strength"] == "MODERATE")
            ]
        ) if not signals_df.empty else 0
        moderate_bear = len(
            signals_df[
                (signals_df["signal"] == "BEARISH")
                & (signals_df["strength"] == "MODERATE")
            ]
        ) if not signals_df.empty else 0

        key_table = latest[latest["is_key_market"]].copy()
        key_table = key_table.sort_values("divergence_percentile", ascending=False)

        bullish_extremes = latest.sort_values("divergence_percentile", ascending=False).head(10)
        bearish_extremes = latest.sort_values("divergence_percentile", ascending=True).head(10)
        extremes = pd.concat([bullish_extremes, bearish_extremes])
        extremes = extremes.drop_duplicates("market")
        extremes = extremes.sort_values("intent_score")
        extremes_markets = extremes["market"].tolist()

        drilldown = latest.sort_values(
            ["category", "divergence_percentile"],
            ascending=[True, False],
        ).copy()

        fig = make_subplots(
            rows=4,
            cols=4,
            specs=[
                [
                    {"type": "domain"},
                    {"type": "domain"},
                    {"type": "domain"},
                    {"type": "domain"},
                ],
                [
                    {"type": "scatter", "colspan": 2},
                    None,
                    {"type": "table", "colspan": 2},
                    None,
                ],
                [{"type": "bar", "colspan": 4}, None, None, None],
                [{"type": "table", "colspan": 4}, None, None, None],
            ],
            subplot_titles=(
                "Strong Bullish",
                "Strong Bearish",
                "Moderate Bullish",
                "Moderate Bearish",
                "Positioning Map",
                "Key Markets",
                "Bullish and Bearish Extremes",
                "Category Drill Down",
            ),
            vertical_spacing=0.08,
            horizontal_spacing=0.06,
            row_heights=[0.13, 0.32, 0.23, 0.32],
        )

        for col, value, color in [
            (1, strong_bull, "#1e8449"),
            (2, strong_bear, "#c0392b"),
            (3, moderate_bull, "#58d68d"),
            (4, moderate_bear, "#ec7063"),
        ]:
            fig.add_trace(
                go.Indicator(
                    mode="number",
                    value=value,
                    number=dict(font=dict(size=34, color=color)),
                ),
                row=1,
                col=col,
            )

        fig.add_trace(
            go.Scatter(
                x=latest["commercial_net_pct"] * 100,
                y=latest["small_spec_net_pct"] * 100,
                mode="markers",
                marker=dict(
                    size=10,
                    color=latest["divergence_percentile"],
                    colorscale="RdYlGn",
                    showscale=True,
                    line=dict(
                        width=np.where(latest["is_key_market"], 2, 0.5),
                        color=np.where(latest["is_key_market"], "#111111", "#777777"),
                    ),
                    colorbar=dict(
                        title="Div %ile",
                        x=0.47,
                        thickness=15,
                        len=0.26,
                        y=0.66,
                    ),
                ),
                text=latest["market"],
                customdata=np.stack(
                    [
                        latest["category_label"],
                        latest["signal_label"],
                        latest["divergence_percentile"],
                        latest["divergence_change_4w"].fillna(0),
                    ],
                    axis=-1,
                ),
                hovertemplate=(
                    "<b>%{text}</b><br>"
                    "Category: %{customdata[0]}<br>"
                    "Signal: %{customdata[1]}<br>"
                    "Comm Net: %{x:.1f}%<br>"
                    "Small Spec Net: %{y:.1f}%<br>"
                    "Div %ile: %{customdata[2]:.0f}<br>"
                    "4w Change: %{customdata[3]:+.0f}<extra></extra>"
                ),
            ),
            row=2,
            col=1,
        )
        fig.add_shape(
            type="line",
            x0=(latest["commercial_net_pct"] * 100).min(),
            x1=(latest["commercial_net_pct"] * 100).max(),
            y0=0,
            y1=0,
            xref="x",
            yref="y",
            line=dict(color="gray", dash="dash"),
        )
        fig.add_shape(
            type="line",
            x0=0,
            x1=0,
            y0=(latest["small_spec_net_pct"] * 100).min(),
            y1=(latest["small_spec_net_pct"] * 100).max(),
            xref="x",
            yref="y",
            line=dict(color="gray", dash="dash"),
        )

        key_colors = [key_table["signal_color"].tolist()] * 6
        fig.add_trace(
            go.Table(
                columnwidth=[2.2, 1.2, 1.0, 1.0, 1.0, 0.9],
                header=dict(
                    values=[
                        "Market",
                        "Signal",
                        "Div %ile",
                        "4w Chg",
                        "Comm %",
                        "Spec %",
                    ],
                    fill_color="#e5e7eb",
                    align="left",
                    font=dict(size=12),
                ),
                cells=dict(
                    values=[
                        key_table["chart_link"],
                        key_table["signal_label"],
                        key_table["divergence_percentile"].apply(lambda x: f"{x:.0f}"),
                        key_table["divergence_change_4w"].apply(
                            lambda x: "n/a" if pd.isna(x) else f"{x:+.0f}"
                        ),
                        key_table["commercial_net_pct"].apply(lambda x: f"{x:+.1%}"),
                        key_table["small_spec_net_pct"].apply(lambda x: f"{x:+.1%}"),
                    ],
                    fill_color=key_colors,
                    align="left",
                    height=24,
                    font=dict(size=11),
                ),
            ),
            row=2,
            col=3,
        )

        bar_colors = np.where(extremes["intent_score"] >= 0, "#1e8449", "#c0392b")
        fig.add_trace(
            go.Bar(
                y=extremes["market"],
                x=extremes["intent_score"],
                orientation="h",
                marker_color=bar_colors,
                text=extremes["divergence_percentile"].apply(lambda x: f"{x:.0f}"),
                textposition="outside",
                customdata=np.stack(
                    [
                        extremes["signal_label"],
                        extremes["divergence_percentile"],
                        extremes["divergence_change_4w"].fillna(0),
                    ],
                    axis=-1,
                ),
                hovertemplate=(
                    "<b>%{y}</b><br>"
                    "%{customdata[0]}<br>"
                    "Div %ile: %{customdata[1]:.0f}<br>"
                    "4w Change: %{customdata[2]:+.0f}<extra></extra>"
                ),
            ),
            row=3,
            col=1,
        )
        fig.add_shape(
            type="line",
            x0=0,
            x1=0,
            y0=-0.5,
            y1=len(extremes) - 0.5,
            xref="x2",
            yref="y2",
            line=dict(color="gray", dash="dash"),
        )

        def drilldown_table_values(table_df: pd.DataFrame) -> list[pd.Series]:
            return [
                table_df["category_label"],
                table_df["chart_link"],
                table_df["signal_label"],
                table_df["divergence_percentile"].apply(lambda x: f"{x:.0f}"),
                table_df["divergence_change_4w"].apply(
                    lambda x: "n/a" if pd.isna(x) else f"{x:+.0f}"
                ),
                table_df["commercial_net_pct"].apply(lambda x: f"{x:+.1%}"),
                table_df["small_spec_net_pct"].apply(lambda x: f"{x:+.1%}"),
                table_df["open_interest"].apply(lambda x: f"{x:,.0f}"),
                table_df["is_key_market"].apply(lambda x: "Yes" if x else ""),
            ]

        def drilldown_fill_colors(table_df: pd.DataFrame) -> list[list[str]]:
            return [table_df["signal_color"].tolist()] * 9

        drilldown_trace_index = len(fig.data)
        drill_colors = drilldown_fill_colors(drilldown)
        fig.add_trace(
            go.Table(
                columnwidth=[1.0, 1.8, 1.2, 0.8, 0.8, 0.9, 0.9, 0.8, 0.6],
                header=dict(
                    values=[
                        "Category",
                        "Market",
                        "Signal",
                        "Div %ile",
                        "4w Chg",
                        "Comm %",
                        "Spec %",
                        "OI",
                        "Key",
                    ],
                    fill_color="#e5e7eb",
                    align="left",
                    font=dict(size=12),
                ),
                cells=dict(
                    values=drilldown_table_values(drilldown),
                    fill_color=drill_colors,
                    align="left",
                    height=23,
                    font=dict(size=11),
                ),
            ),
            row=4,
            col=1,
        )

        drilldown_sort_options = [
            ("Category", ["category", "divergence_percentile"], [True, False]),
            ("Market A-Z", ["market"], [True]),
            ("Div High-Low", ["divergence_percentile"], [False]),
            ("Div Low-High", ["divergence_percentile"], [True]),
            ("4w Chg Up", ["divergence_change_4w"], [False]),
            ("4w Chg Down", ["divergence_change_4w"], [True]),
            ("Commercial %", ["commercial_net_pct"], [False]),
            ("Small Spec %", ["small_spec_net_pct"], [False]),
            ("Open Interest", ["open_interest"], [False]),
            ("Key First", ["is_key_market", "category", "market"], [False, True, True]),
        ]
        drilldown_buttons = []
        for label, sort_columns, ascending in drilldown_sort_options:
            sorted_drilldown = drilldown.sort_values(
                sort_columns,
                ascending=ascending,
                na_position="last",
            )
            drilldown_buttons.append(
                dict(
                    label=label,
                    method="restyle",
                    args=[
                        {
                            "cells.values": [drilldown_table_values(sorted_drilldown)],
                            "cells.fill.color": [drilldown_fill_colors(sorted_drilldown)],
                        },
                        [drilldown_trace_index],
                    ],
                )
            )

        fig.update_layout(
            title=(
                "COT Analysis Dashboard"
                f"<br><sup>Data as of {most_recent:%Y-%m-%d}; "
                f"{len(latest)} markets analyzed. Click market names in tables "
                "to open individual interactive charts when generated.</sup>"
            ),
            height=1550,
            showlegend=False,
            margin=dict(l=40, r=40, t=110, b=40),
            updatemenus=[
                dict(
                    buttons=drilldown_buttons,
                    direction="down",
                    showactive=True,
                    x=0,
                    xanchor="left",
                    y=0.285,
                    yanchor="top",
                )
            ],
        )
        fig.add_annotation(
            text="Sort drill down:",
            x=0,
            xanchor="left",
            y=0.306,
            yanchor="top",
            xref="paper",
            yref="paper",
            showarrow=False,
            font=dict(size=12),
        )

        fig.update_xaxes(title_text="Commercial Net %", row=2, col=1)
        fig.update_yaxes(title_text="Small Spec Net %", row=2, col=1)
        fig.update_xaxes(title_text="Intent Score: Bearish < 0 < Bullish", row=3, col=1)
        fig.update_yaxes(
            automargin=True,
            categoryorder="array",
            categoryarray=extremes_markets,
            tickmode="array",
            tickvals=extremes_markets,
            ticktext=extremes_markets,
            row=3,
            col=1,
        )

        if save_path:
            link_script = Path(__file__).with_name("dashboard_links.js").read_text()
            fig.write_html(save_path, post_script=link_script)
            print(f"Saved dashboard to {save_path}")

        return fig

    def save_all_charts(
        self,
        df: pd.DataFrame,
        signals_df: pd.DataFrame,
        markets: Optional[list[str]] = None,
    ) -> dict[str, Path]:
        """
        Generate and save all charts.

        Args:
            df: Analyzed DataFrame
            signals_df: DataFrame with signals
            markets: Optional list of markets to generate individual charts for

        Returns:
            Dictionary mapping chart names to file paths
        """
        charts_dir = self.config.charts_dir
        saved = {}

        # Get latest readings
        latest = df.groupby("market").last().reset_index()

        # Save heatmap
        try:
            heatmap_path = charts_dir / "divergence_heatmap.png"
            self.plot_divergence_heatmap(latest, save_path=heatmap_path)
            saved["heatmap"] = heatmap_path
            plt.close()
        except Exception as e:
            print(f"Error saving heatmap: {e}")

        # Save signal summary
        try:
            summary_path = charts_dir / "signal_summary.png"
            self.plot_signal_summary(signals_df, save_path=summary_path)
            saved["signal_summary"] = summary_path
            plt.close()
        except Exception as e:
            print(f"Error saving signal summary: {e}")

        # Save market comparison (Plotly)
        try:
            comparison_path = charts_dir / "market_comparison.html"
            self.plot_market_comparison(latest, save_path=comparison_path)
            saved["market_comparison"] = comparison_path
        except Exception as e:
            print(f"Error saving market comparison: {e}")

        # Save dashboard
        try:
            dashboard_path = charts_dir / "dashboard.html"
            self.create_dashboard(df, signals_df, save_path=dashboard_path)
            saved["dashboard"] = dashboard_path
        except Exception as e:
            print(f"Error saving dashboard: {e}")

        # Save individual market charts
        if markets:
            for market in markets:
                try:
                    # Static chart
                    safe_name = market.replace("/", "_").replace(" ", "_")
                    static_path = charts_dir / f"{safe_name}_positions.png"
                    self.plot_net_positions(df, market, save_path=static_path)
                    saved[f"{market}_static"] = static_path
                    plt.close()

                    # Interactive chart
                    interactive_path = charts_dir / self._interactive_chart_filename(market)
                    self.plot_interactive_positions(df, market, save_path=interactive_path)
                    saved[f"{market}_interactive"] = interactive_path
                except Exception as e:
                    print(f"Error saving charts for {market}: {e}")

        return saved

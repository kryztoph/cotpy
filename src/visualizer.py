"""Visualization tools for COT data analysis."""

from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .config import Config, default_config


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
        # Get latest readings
        latest = df.groupby("market").last().reset_index()
        latest = latest.sort_values("divergence_percentile", ascending=False)

        fig = make_subplots(
            rows=2,
            cols=2,
            column_widths=[0.7, 0.3],
            specs=[
                [{"type": "scatter"}, {"type": "bar"}],
                [{"type": "table", "colspan": 2}, None],
            ],
            subplot_titles=(
                "Market Positioning",
                "Top Divergence Signals",
                "Signal Details",
            ),
            vertical_spacing=0.15,
            horizontal_spacing=0.08,
            row_heights=[0.6, 0.4],
        )

        # Scatter plot of positioning
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
                    colorbar=dict(
                        title="Div %ile",
                        x=1.02,
                        thickness=15,
                        len=0.5,
                        y=0.75
                    ),
                ),
                text=latest["market"],
                hovertemplate="<b>%{text}</b><br>Comm: %{x:.1f}%<br>Spec: %{y:.1f}%<extra></extra>",
            ),
            row=1,
            col=1,
        )

        # Bar chart of top signals
        top_signals = latest.head(15)
        colors = ["green" if d >= 50 else "red" for d in top_signals["divergence_percentile"]]
        fig.add_trace(
            go.Bar(
                y=top_signals["market"],
                x=top_signals["divergence_percentile"],
                orientation="h",
                marker_color=colors,
                hovertemplate="%{y}: %{x:.0f}%ile<extra></extra>",
            ),
            row=1,
            col=2,
        )

        # Table of signals
        if not signals_df.empty:
            table_df = signals_df.head(10)
            fig.add_trace(
                go.Table(
                    header=dict(
                        values=["Market", "Signal", "Strength", "Comm Net", "Spec Net", "Div %ile"],
                        fill_color="lightgray",
                        align="left",
                    ),
                    cells=dict(
                        values=[
                            table_df["market"],
                            table_df["signal"],
                            table_df["strength"],
                            table_df["commercial_net_pct"].apply(lambda x: f"{x:.1%}"),
                            table_df["small_spec_net_pct"].apply(lambda x: f"{x:.1%}"),
                            table_df["divergence_percentile"].apply(lambda x: f"{x:.0f}"),
                        ],
                        fill_color=[
                            [
                                "rgba(144, 238, 144, 0.3)" if s == "BULLISH" else "rgba(240, 128, 128, 0.3)"
                                for s in table_df["signal"]
                            ]
                        ]
                        * 6,
                        align="left",
                    ),
                ),
                row=2,
                col=1,
            )

        fig.update_layout(
            title="COT Analysis Dashboard",
            height=1100,
            showlegend=False,
        )

        fig.update_xaxes(title_text="Commercial Net %", row=1, col=1)
        fig.update_yaxes(title_text="Small Spec Net %", row=1, col=1)
        fig.update_xaxes(title_text="Divergence Percentile", row=1, col=2)

        if save_path:
            fig.write_html(save_path)
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
                    interactive_path = charts_dir / f"{safe_name}_interactive.html"
                    self.plot_interactive_positions(df, market, save_path=interactive_path)
                    saved[f"{market}_interactive"] = interactive_path
                except Exception as e:
                    print(f"Error saving charts for {market}: {e}")

        return saved

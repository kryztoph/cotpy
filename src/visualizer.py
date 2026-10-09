"""Visualization tools for COT data analysis."""

from pathlib import Path
from typing import Optional
from html import escape
from urllib.parse import quote
import base64
import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .config import Config, default_config, get_enabled_contracts, get_key_markets
from .prices import MARKET_TICKERS, price_fetcher


class COTVisualizer:
    """Create visualizations for COT data analysis."""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or default_config
        self._setup_style()

    def _setup_style(self):
        """Set up matplotlib style."""
        plt.style.use("seaborn-v0_8-darkgrid")
        sns.set_palette("husl")

    @staticmethod
    def _divergence_bar_colors(divergence: pd.Series) -> list[str]:
        """Color the largest positive and negative divergences gold.

        Positive and negative divergences retain their directional colors. The
        largest positive and largest negative bars are each highlighted; ties
        resolve to the earliest occurrence for each direction.
        """
        values = pd.to_numeric(divergence, errors="coerce")
        colors = ["green" if value > 0 else "red" for value in values]
        positive_values = values[values > 0]
        negative_values = values[values < 0]
        for directional_values in (positive_values, negative_values):
            if directional_values.empty:
                continue
            extreme_index = directional_values.idxmax()
            colors[values.index.get_loc(extreme_index)] = "#D4AF37"
        return colors

    def _write_branded_html(
        self,
        fig: go.Figure,
        save_path: Path,
        global_tracker: bool = False,
        point_links: bool = False,
        dashboard_sort_payload: Optional[dict] = None,
        table_links: bool = False,
    ) -> None:
        """Write a self-contained Plotly page with CSFox branding."""
        logo_path = Path("/Users/fox/Private/Projects/csfox/assets/logo.png")
        logo_html = ""
        if logo_path.is_file():
            encoded = base64.b64encode(logo_path.read_bytes()).decode("ascii")
            logo_html = (
                '<img class="csfox-logo" '
                f'src="data:image/png;base64,{encoded}" alt="CSFox">'
            )

        link_script = Path(__file__).with_name("dashboard_links.js").read_text() if table_links else None
        html = fig.to_html(full_html=True, config={"responsive": True}, post_script=link_script)
        branding = f"""
<style>
  html, body {{ margin: 0; max-width: 100%; overflow-x: hidden; font-family: Arial, sans-serif; }}
  *, *::before, *::after {{ box-sizing: border-box; }}
  .plotly-graph-div {{ width: 100% !important; max-width: 100%; }}
  .csfox-header {{ display: flex; align-items: center; gap: 12px; padding: 10px 18px 0; }}
  .csfox-logo {{ width: 72px; height: 38px; object-fit: contain; }}
  .csfox-title {{ font-size: 18px; font-weight: 600; color: #172554; }}
  .dashboard-sort-controls {{ display: flex; flex-wrap: wrap; align-items: center; gap: 6px; padding: 8px 18px 2px; }}
  .dashboard-sort-controls span {{ color: #475569; font-size: 12px; font-weight: 600; margin-right: 2px; }}
  .dashboard-sort-controls button {{ appearance: none; border: 1px solid #cbd5e1; border-radius: 4px; background: #fff; color: #1e3a5f; cursor: pointer; font-size: 12px; padding: 4px 7px; }}
  .dashboard-sort-controls button:hover, .dashboard-sort-controls button[aria-pressed="true"] {{ background: #e0f2fe; border-color: #0ea5e9; }}
  .csfox-footer {{ padding: 8px 18px 14px; color: #6b7280; font-size: 11px; text-align: center; }}
</style>
<header class="csfox-header">{logo_html}<span class="csfox-title">CSFox Reports</span></header>
"""
        footer = '<footer class="csfox-footer">© 2026 csfox.com. All rights reserved.</footer>'
        tracker = ""
        if global_tracker:
            tracker = """
<script>
  document.addEventListener("DOMContentLoaded", function () {
    const graph = document.querySelector(".plotly-graph-div");
    if (!graph) return;
    const trackerName = "global-hover-tracker";

    graph.on("plotly_hover", function (event) {
      if (!event.points || !event.points.length) return;
      const x = event.points[0].x;
      const shapes = (graph.layout.shapes || []).filter((shape) => shape.name !== trackerName);
      shapes.push({
        name: trackerName,
        type: "line",
        xref: "x",
        yref: "paper",
        x0: x,
        x1: x,
        y0: 0,
        y1: 1,
        line: { color: "#111827", width: 1.5, dash: "dot" }
      });
      Plotly.relayout(graph, { shapes: shapes });
    });
    graph.on("plotly_unhover", function () {
      const shapes = (graph.layout.shapes || []).filter((shape) => shape.name !== trackerName);
      Plotly.relayout(graph, { shapes: shapes });
    });
  });
</script>
"""
        point_linker = ""
        if point_links:
            point_linker = """
<script>
  document.addEventListener("DOMContentLoaded", function () {
    const graph = document.querySelector(".plotly-graph-div");
    if (!graph) return;

    function chartHref(point) {
      const values = point && point.customdata;
      if (!Array.isArray(values)) return null;
      const href = values[4];
      return typeof href === "string" && /^[^:/?#]+_interactive\\.html$/.test(href)
        ? href
        : null;
    }

    graph.on("plotly_hover", function (event) {
      const point = event.points && event.points[0];
      graph.style.cursor = chartHref(point) ? "pointer" : "default";
    });
    graph.on("plotly_unhover", function () {
      graph.style.cursor = "default";
    });
    graph.on("plotly_click", function (event) {
      const point = event.points && event.points[0];
      const href = chartHref(point);
      if (href) window.location.assign(href);
    });
  });
</script>
"""
        sort_controls = ""
        if dashboard_sort_payload:
            buttons = "".join(
                (
                    '<button type="button" data-sort-key="'
                    f'{escape(key, quote=True)}" data-sort-label="{escape(option["label"], quote=True)}">'
                    f'{escape(option["label"])} ↕</button>'
                )
                for key, option in dashboard_sort_payload.items()
            )
            payload = json.dumps(dashboard_sort_payload).replace("<", "\\u003c")
            sort_controls = f"""
<section class="dashboard-sort-controls" aria-label="Category drill-down sorting">
  <span>Sort category drill-down:</span>{buttons}
</section>
<script>
  document.addEventListener("DOMContentLoaded", function () {{
    const graph = document.querySelector(".plotly-graph-div");
    const options = {payload};
    let activeKey = "category";
    let activeDirection = "asc";

    function renderButtons() {{
      document.querySelectorAll("[data-sort-key]").forEach(function (button) {{
        const active = button.dataset.sortKey === activeKey;
        button.setAttribute("aria-pressed", String(active));
        button.textContent = button.dataset.sortLabel + (active ? (activeDirection === "asc" ? " ▲" : " ▼") : " ↕");
      }});
    }}

    document.querySelectorAll("[data-sort-key]").forEach(function (button) {{
      button.addEventListener("click", function () {{
        const key = button.dataset.sortKey;
        const option = options[key];
        if (!graph || !option) return;
        const direction = key === activeKey && activeDirection === "asc"
          ? "desc"
          : (key === activeKey ? "asc" : option.default_direction);
        const values = option.directions[direction];
        Plotly.restyle(graph, {{
          "cells.values": [values.cells_values],
          "cells.fill.color": [values.cells_fill_color]
        }}, [option.trace_index]);
        activeKey = key;
        activeDirection = direction;
        renderButtons();
      }});
    }});
    renderButtons();
  }});
</script>
"""
        html = html.replace(
            '<meta charset="utf-8" />',
            '<meta charset="utf-8" />\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1" />',
            1,
        )
        html = html.replace("<body>", f"<body>{branding}", 1)
        if sort_controls:
            html = html.replace("</header>", f"</header>{sort_controls}", 1)
        html = html.replace(
            "</body>",
            f"{tracker}{point_linker}{footer}</body>",
            1,
        )
        save_path.write_text(html, encoding="utf-8")

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
        colors = self._divergence_bar_colors(divergence)
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
            specs=[[{"secondary_y": True}], [{}], [{}]],
            vertical_spacing=0.05,
            subplot_titles=(
                "Net Positions (% of OI)",
                "Divergence",
                "Open Interest",
            ),
            row_heights=[0.58, 0.25, 0.17],
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

        # Prices are kept on a secondary axis because the position series are
        # percentages while prices use contract-specific units.
        prices = price_fetcher.get_prices(
            market,
            market_df["date"].min(),
            market_df["date"].max(),
        )
        if not prices.empty:
            price_ticker = MARKET_TICKERS.get(market, "n/a")
            # Candlestick overlay retained for possible future reuse:
            # fig.add_trace(
            #     go.Candlestick(
            #         x=prices["date"],
            #         open=prices["open"],
            #         high=prices["high"],
            #         low=prices["low"],
            #         close=prices["close"],
            #         name=f"Price ({price_ticker})",
            #         increasing_line_color="#16803c",
            #         decreasing_line_color="#c0392b",
            #     ),
            #     row=1,
            #     col=1,
            #     secondary_y=True,
            # )
            fig.add_trace(
                go.Scatter(
                    x=prices["date"],
                    y=prices["close"],
                    name=f"Price ({price_ticker})",
                    line=dict(color="black", width=1.5),
                    hovertemplate=f"%{{y:,.4g}}<extra>Price ({price_ticker})</extra>",
                ),
                row=1,
                col=1,
                secondary_y=True,
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
        colors = self._divergence_bar_colors(market_df["divergence"])
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
            go.Bar(
                x=market_df["date"],
                y=market_df["open_interest"],
                name="Open Interest",
                marker_color="rgba(128, 0, 128, 0.65)",
                hovertemplate="%{y:,.0f}<extra>Open Interest</extra>",
            ),
            row=3,
            col=1,
        )

        fig.update_layout(
            title=f"{market} - COT Analysis",
            height=1000,
            showlegend=True,
            legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
            # Show every series at the same date and draw a shared vertical
            # tracker across all three panels.
            hovermode="x unified",
            spikedistance=-1,
            hoverdistance=-1,
        )

        fig.update_yaxes(title_text="% of OI", row=1, col=1)
        price_ticker = MARKET_TICKERS.get(market, "n/a")
        fig.update_yaxes(title_text=f"Price ({price_ticker})", secondary_y=True, row=1, col=1)
        fig.update_yaxes(title_text="Divergence", row=2, col=1)
        fig.update_yaxes(title_text="Contracts", row=3, col=1)

        for axis in ("xaxis", "xaxis2", "xaxis3"):
            fig.update_layout(
                **{
                    axis: dict(
                        showspikes=True,
                        spikemode="across",
                        spikesnap="cursor",
                        spikethickness=1,
                        spikecolor="#374151",
                        spikedash="dot",
                    )
                }
            )

        # Add zero line
        fig.add_hline(y=0, line_dash="dash", line_color="gray", row=1, col=1)
        fig.add_hline(y=0, line_dash="dash", line_color="gray", row=2, col=1)

        if save_path:
            self._write_branded_html(fig, save_path, global_tracker=True)
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
            self._write_branded_html(fig, save_path)
            print(f"Saved comparison chart to {save_path}")

        return fig

    def _interactive_chart_filename(self, market: str) -> str:
        """Return the standard interactive chart filename for a market."""
        safe_name = market.replace("/", "_").replace(" ", "_")
        return f"{safe_name}_interactive.html"

    @staticmethod
    def _signal_label(signal: str, strength: str) -> str:
        """Return the same human-readable classification used by signal counts."""
        if signal not in {"BULLISH", "BEARISH"}:
            return "Neutral"
        return f"{strength.title()} {signal.title()}"

    @staticmethod
    def _signal_color(signal: str, strength: str) -> str:
        """Return a cell color for an evaluated signal."""
        colors = {
            ("BULLISH", "STRONG"): "rgba(30, 132, 73, 0.22)",
            ("BULLISH", "MODERATE"): "rgba(88, 214, 141, 0.18)",
            ("BULLISH", "WEAK"): "rgba(88, 214, 141, 0.10)",
            ("BEARISH", "STRONG"): "rgba(192, 57, 43, 0.22)",
            ("BEARISH", "MODERATE"): "rgba(236, 112, 99, 0.18)",
            ("BEARISH", "WEAK"): "rgba(236, 112, 99, 0.10)",
        }
        return colors.get((signal, strength), "rgba(215, 219, 221, 0.22)")

    def _latest_with_drilldown_fields(
        self,
        df: pd.DataFrame,
        signals_df: pd.DataFrame,
    ) -> pd.DataFrame:
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

        signal_rows = signals_df.drop_duplicates("market", keep="last")
        signal_by_market = signal_rows.set_index("market")["signal"]
        strength_by_market = signal_rows.set_index("market")["strength"]
        latest["signal"] = latest["market"].map(signal_by_market).fillna("NEUTRAL")
        latest["strength"] = latest["market"].map(strength_by_market).fillna("")
        latest["signal_label"] = [
            self._signal_label(signal, strength)
            for signal, strength in zip(latest["signal"], latest["strength"])
        ]
        latest["signal_color"] = [
            self._signal_color(signal, strength)
            for signal, strength in zip(latest["signal"], latest["strength"])
        ]
        latest["divergence_change_4w"] = latest["market"].map(changes)
        latest["intent_score"] = latest["divergence_percentile"] - 50
        latest["chart_link"] = latest["market"].apply(
            lambda market: (
                f'<a href="{escape(quote(self._interactive_chart_filename(market), safe=""))}" target="_self">'
                f'{escape(market)}</a>'
            )
        )
        latest["chart_url"] = latest["market"].apply(
            lambda market: quote(self._interactive_chart_filename(market), safe="")
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
        latest = self._latest_with_drilldown_fields(df, signals_df)
        most_recent = latest["date"].max()

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
            cols=2,
            specs=[
                [{"type": "table", "colspan": 2}, None],
                [{"type": "scatter", "colspan": 2}, None],
                [{"type": "table", "colspan": 2}, None],
                [{"type": "bar", "colspan": 2}, None],
            ],
            subplot_titles=(
                "Category Drill Down",
                "Positioning Map",
                "Key Markets",
                "Bullish and Bearish Extremes",
            ),
            vertical_spacing=0.025,
            horizontal_spacing=0.08,
            row_heights=[0.38, 0.20, 0.22, 0.20],
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
                        title="Div<br>%ile",
                        x=0.92,
                        thickness=15,
                        len=0.14,
                        y=0.53,
                    ),
                ),
                text=latest["market"],
                customdata=np.stack(
                    [
                        latest["category_label"],
                        latest["signal_label"],
                        latest["divergence_percentile"],
                        latest["divergence_change_4w"].fillna(0),
                        latest["chart_url"],
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
                    "4w Change: %{customdata[3]:+.0f}<br>"
                    "<b>Click to open chart</b><extra></extra>"
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

        key_colors = [key_table["signal_color"].tolist()] * 3
        fig.add_trace(
            go.Table(
                columnwidth=[2.3, 1.4, 0.8],
                header=dict(
                    values=[
                        "Market",
                        "Signal",
                        "Div %ile",
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
                    ],
                    fill_color=key_colors,
                    align="left",
                    height=24,
                    font=dict(size=11),
                ),
            ),
            row=3,
            col=1,
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
            row=4,
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

        def drilldown_table_values(table_df: pd.DataFrame) -> list[list[str]]:
            return [
                table_df["category_label"].tolist(),
                table_df["chart_link"].tolist(),
                table_df["signal_label"].tolist(),
                table_df["divergence_percentile"].apply(lambda x: f"{x:.0f}").tolist(),
                table_df["divergence_change_4w"].apply(
                    lambda x: "n/a" if pd.isna(x) else f"{x:+.0f}"
                ).tolist(),
                table_df["commercial_net_pct"].apply(lambda x: f"{x:+.1%}").tolist(),
                table_df["small_spec_net_pct"].apply(lambda x: f"{x:+.1%}").tolist(),
                table_df["open_interest"].apply(lambda x: f"{x:,.0f}").tolist(),
                table_df["is_key_market"].apply(lambda x: "Yes" if x else "").tolist(),
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
            row=1,
            col=1,
        )

        drilldown_sort_specs = [
            ("category", "Category", ["category", "divergence_percentile"], [False], "asc"),
            ("market", "Market", ["market"], [], "asc"),
            ("signal", "Signal", ["signal_label", "market"], [True], "asc"),
            ("divergence", "Div %ile", ["divergence_percentile"], [], "desc"),
            ("change", "4w Chg", ["divergence_change_4w"], [], "desc"),
            ("commercial", "Comm %", ["commercial_net_pct"], [], "desc"),
            ("small_spec", "Spec %", ["small_spec_net_pct"], [], "desc"),
            ("open_interest", "OI", ["open_interest"], [], "desc"),
            ("key", "Key", ["is_key_market", "category", "market"], [True, True], "desc"),
        ]
        dashboard_sort_payload = {}
        for key, label, sort_columns, secondary_ascending, default_direction in drilldown_sort_specs:
            directions = {}
            for direction in ("asc", "desc"):
                sorted_drilldown = drilldown.sort_values(
                    sort_columns,
                    ascending=[direction == "asc", *secondary_ascending],
                    na_position="last",
                )
                directions[direction] = {
                    "cells_values": drilldown_table_values(sorted_drilldown),
                    "cells_fill_color": drilldown_fill_colors(sorted_drilldown),
                }
            dashboard_sort_payload[key] = {
                "label": label,
                "default_direction": default_direction,
                "directions": directions,
                "trace_index": drilldown_trace_index,
            }

        fig.update_layout(
            title=(
                "COT Analysis Dashboard"
                f"<br><sup>Data as of {most_recent:%Y-%m-%d}; "
                f"{len(latest)} markets analyzed.<br>Market names link to "
                "interactive charts.</sup>"
            ),
            height=3000,
            autosize=True,
            showlegend=False,
            margin=dict(l=28, r=28, t=110, b=40),
        )

        fig.update_xaxes(
            title_text="Commercial Net %",
            domain=[0, 0.88],
            row=2,
            col=1,
        )
        fig.update_yaxes(title_text="Small Spec Net %", row=2, col=1)
        fig.update_xaxes(title_text="Intent Score: Bearish < 0 < Bullish", row=4, col=1)
        fig.update_yaxes(
            automargin=True,
            categoryorder="array",
            categoryarray=extremes_markets,
            tickmode="array",
            tickvals=extremes_markets,
            ticktext=extremes_markets,
            row=4,
            col=1,
        )

        if save_path:
            self._write_branded_html(
                fig,
                save_path,
                point_links=True,
                dashboard_sort_payload=dashboard_sort_payload,
                table_links=True,
            )
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

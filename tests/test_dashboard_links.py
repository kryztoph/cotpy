"""Regression checks for dashboard navigation and chart destinations."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import pandas as pd

from main import cmd_dashboard
from src.config import Config
from src.visualizer import COTVisualizer


class DashboardLinkTests(unittest.TestCase):
    def test_market_links_encode_filename_and_escape_label(self):
        # A fixture name exercises URL punctuation as well as HTML escaping.
        market = 'S&P / Test #1?'
        df = pd.DataFrame([{
            'market': market, 'date': pd.Timestamp('2026-01-02'),
            'divergence_percentile': 50,
        }])
        with tempfile.TemporaryDirectory() as tmp:
            config = Config(data_dir=Path(tmp) / 'data',
                            output_dir=Path(tmp), charts_dir=Path(tmp) / 'charts')
            visualizer = COTVisualizer(config)
            link = visualizer._latest_with_drilldown_fields(df, pd.DataFrame(columns=["market", "signal", "strength"])).iloc[0]['chart_link']
        self.assertEqual(
            link,
            '<a href="S%26P___Test_%231%3F_interactive.html" target="_self">S&amp;P / Test #1?</a>',
        )

    def test_dashboard_command_generates_every_link_target_first(self):
        config = Mock(charts_dir=Path('charts'))
        df = pd.DataFrame({'market': ['GOLD', 'S&P 500', 'GOLD']})
        signals = pd.DataFrame()
        with patch('main.load_and_analyze_data', return_value=(df, signals)), \
                patch('main.COTVisualizer') as factory:
            visualizer = factory.return_value
            visualizer._interactive_chart_filename.side_effect = (
                lambda market: COTVisualizer._interactive_chart_filename(None, market)
            )
            cmd_dashboard(config)
        calls = visualizer.plot_interactive_positions.call_args_list
        self.assertEqual([call.args[1] for call in calls], ['GOLD', 'S&P 500'])
        self.assertEqual([call.kwargs['save_path'] for call in calls], [
            Path('charts/GOLD_interactive.html'), Path('charts/S&P_500_interactive.html'),
        ])
        visualizer.create_dashboard.assert_called_once_with(
            df, signals, save_path=Path('charts/dashboard.html'),
        )
        self.assertEqual(visualizer.method_calls[-1][0], 'create_dashboard')

    def test_dashboard_preserves_all_markets_at_top_and_branded_sorting(self):
        markets = ['GOLD', 'SILVER', 'CORN']
        df = pd.DataFrame([{
            'market': market, 'date': pd.Timestamp('2026-09-29'),
            'divergence_percentile': 50 + index * 10,
            'commercial_net_pct': .1, 'small_spec_net_pct': -.1,
            'open_interest': 1000,
        } for index, market in enumerate(markets)])
        signals = pd.DataFrame(columns=['market', 'signal', 'strength'])
        with tempfile.TemporaryDirectory() as tmp:
            config = Config(data_dir=Path(tmp) / 'data', output_dir=Path(tmp),
                            charts_dir=Path(tmp) / 'charts')
            path = config.charts_dir / 'dashboard.html'
            fig = COTVisualizer(config).create_dashboard(df, signals, save_path=path)
            tables = [trace for trace in fig.data if trace.type == 'table']
            full_table = next(trace for trace in tables if 'Category' in trace.header.values)
            self.assertGreater(full_table.domain.y[0], .6)
            self.assertEqual(len(full_table.cells.values[0]), len(markets))
            self.assertTrue(all(any(market in link for link in full_table.cells.values[1])
                                for market in markets))
            self.assertEqual(fig.layout.height, 3000)
            self.assertEqual(fig.layout.annotations[0].text, 'Category Drill Down')
            html = path.read_text()
            self.assertIn('csfox-header', html)
            self.assertIn('data-sort-key="market"', html)
            self.assertIn('MutationObserver(restoreLinks)', html)
            self.assertIn('plotly_click', html)


if __name__ == '__main__':
    unittest.main()

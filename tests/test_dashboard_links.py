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
            link = visualizer._latest_with_drilldown_fields(df).iloc[0]['chart_link']
        self.assertEqual(
            link,
            '<a href="S%26P___Test_%231%3F_interactive.html">S&amp;P / Test #1?</a>',
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


if __name__ == '__main__':
    unittest.main()

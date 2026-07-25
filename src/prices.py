"""Fetch market prices for chart overlays."""

from __future__ import annotations

import time

import pandas as pd
import requests


# Yahoo Finance continuous futures symbols provide a useful price proxy for
# the corresponding CFTC contract. Currency contracts are quoted in the
# futures quote convention used by Yahoo (for example, EUR/USD and USD/JPY).
MARKET_TICKERS = {
    "GOLD": "GC=F",
    "SILVER": "SI=F",
    "COPPER": "HG=F",
    "PLATINUM": "PL=F",
    "PALLADIUM": "PA=F",
    "CRUDE OIL": "CL=F",
    "NATURAL GAS": "NG=F",
    "GASOLINE": "RB=F",
    "HEATING OIL": "HO=F",
    "S&P 500": "ES=F",
    "NASDAQ 100": "NQ=F",
    "DOW JONES": "YM=F",
    "RUSSELL 2000": "RTY=F",
    "VIX": "^VIX",
    "T-BONDS": "ZB=F",
    "10Y NOTES": "ZN=F",
    "2Y NOTES": "ZT=F",
    "5Y NOTES": "ZF=F",
    # Spot symbols preserve the display direction used by contracts.json.
    "EUR/USD": "EURUSD=X",
    "USD/JPY": "JPY=X",
    "GBP/USD": "GBPUSD=X",
    "USD/CHF": "CHF=X",
    "USD/CAD": "CAD=X",
    "AUD/USD": "AUDUSD=X",
    "NZD/USD": "NZDUSD=X",
    "USD/MXN": "MXN=X",
    "CORN": "ZC=F",
    "SOYBEANS": "ZS=F",
    "WHEAT": "ZW=F",
    "SOYBEAN OIL": "ZL=F",
    "SOYBEAN MEAL": "ZM=F",
    "COFFEE": "KC=F",
    "SUGAR": "SB=F",
    "COCOA": "CC=F",
    "COTTON": "CT=F",
    "LIVE CATTLE": "LE=F",
    "LEAN HOGS": "HE=F",
    "FEEDER CATTLE": "GF=F",
}


class PriceFetcher:
    """Fetch and cache daily prices for COT markets."""

    def __init__(self):
        self._cache: dict[tuple[str, str, str], pd.DataFrame] = {}
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "cotpy/1.0"})

    def get_prices(self, market: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        """Return daily OHLC prices with ``date`` and candle columns."""
        ticker = MARKET_TICKERS.get(market)
        if not ticker:
            return pd.DataFrame(columns=["date", "open", "high", "low", "close"])

        start_key = pd.Timestamp(start).date().isoformat()
        end_key = pd.Timestamp(end).date().isoformat()
        cache_key = (ticker, start_key, end_key)
        if cache_key in self._cache:
            return self._cache[cache_key]

        period1 = int(pd.Timestamp(start).tz_localize("UTC").timestamp())
        period2 = int((pd.Timestamp(end) + pd.Timedelta(days=2)).tz_localize("UTC").timestamp())
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        try:
            response = self._session.get(
                url,
                params={"period1": period1, "period2": period2, "interval": "1d", "events": "history"},
                timeout=20,
            )
            response.raise_for_status()
            result = response.json()["chart"]["result"]
            if not result:
                raise ValueError("empty Yahoo Finance response")
            chart = result[0]
            quote = chart["indicators"]["quote"][0]
            prices = pd.DataFrame(
                {
                    "date": pd.to_datetime(chart.get("timestamp", []), unit="s", utc=True).tz_convert(None),
                    "open": quote["open"],
                    "high": quote["high"],
                    "low": quote["low"],
                    "close": quote["close"],
                }
            ).dropna(subset=["open", "high", "low", "close"])
        except (requests.RequestException, KeyError, TypeError, ValueError, IndexError) as exc:
            print(f"Warning: could not fetch price history for {market} ({ticker}): {exc}")
            prices = pd.DataFrame(columns=["date", "open", "high", "low", "close"])

        self._cache[cache_key] = prices
        # Avoid hammering the public endpoint when generating all markets.
        time.sleep(0.05)
        return prices


price_fetcher = PriceFetcher()

"""Price data fetching service from Binance API."""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)


class PriceFetcher:
    """Price data fetching from Binance API."""

    def __init__(self, base_url: str = "https://api.binance.com/api/v3"):
        """Initialize price fetcher."""
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "SqueezeBot/1.0"})

    def get_klines(
        self, symbol: str, interval: str = "1h", limit: int = 100
    ) -> Optional[pd.DataFrame]:
        """
        Get kline/candlestick data from Binance.

        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            interval: Timeframe ('1h', '4h', '1d')
            limit: Number of records (max 1000)

        Returns:
            DataFrame with OHLCV data or None if error
        """
        try:
            url = f"{self.base_url}/klines"
            params = {
                "symbol": symbol.upper(),
                "interval": interval,
                "limit": min(limit, 1000),  # Binance max limit
            }

            logger.debug(f"Fetching {symbol} data for {interval}")
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            if not data:
                logger.warning(f"No data received for {symbol}")
                return None

            # Convert to DataFrame
            df = pd.DataFrame(
                data,
                columns=[
                    "timestamp",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "close_time",
                    "quote_asset_volume",
                    "number_of_trades",
                    "taker_buy_base_asset_volume",
                    "taker_buy_quote_asset_volume",
                    "ignore",
                ],
            )

            # Convert data types
            df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")
            numeric_columns = ["open", "high", "low", "close", "volume"]

            for col in numeric_columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

            # Select and reorder relevant columns
            result_df = df[
                ["datetime", "open", "high", "low", "close", "volume"]
            ].copy()
            result_df = result_df.sort_values("datetime").reset_index(drop=True)

            logger.info(
                f"Successfully fetched {len(result_df)} records for {symbol} {interval}"
            )
            return result_df

        except requests.exceptions.Timeout:
            logger.error(f"Timeout fetching data for {symbol}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error fetching {symbol}: {e}")
            return None
        except ValueError as e:
            logger.error(f"Data parsing error for {symbol}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching {symbol}: {e}")
            return None

    def get_current_price(self, symbol: str) -> Optional[float]:
        """
        Get current price for a symbol.

        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')

        Returns:
            Current price as float or None if error
        """
        try:
            url = f"{self.base_url}/ticker/price"
            params = {"symbol": symbol.upper()}

            response = self.session.get(url, params=params, timeout=5)
            response.raise_for_status()

            data = response.json()
            price = float(data["price"])

            logger.debug(f"Current price for {symbol}: {price}")
            return price

        except Exception as e:
            logger.error(f"Error fetching current price for {symbol}: {e}")
            return None

    def get_multiple_symbols(
        self, symbols: List[str], interval: str = "1h", limit: int = 100
    ) -> Dict[str, pd.DataFrame]:
        """
        Get price data for multiple symbols.

        Args:
            symbols: List of trading pairs
            interval: Timeframe
            limit: Number of records per symbol

        Returns:
            Dict mapping symbol to DataFrame
        """
        results = {}
        failed_symbols = []

        for symbol in symbols:
            logger.info(f"Fetching data for {symbol}")

            df = self.get_klines(symbol, interval, limit)
            if df is not None:
                results[symbol] = df
            else:
                failed_symbols.append(symbol)

            # Rate limiting - avoid hitting Binance limits
            time.sleep(0.1)

        if failed_symbols:
            logger.warning(f"Failed to fetch data for symbols: {failed_symbols}")

        logger.info(
            f"Successfully fetched data for {len(results)}/{len(symbols)} symbols"
        )
        return results

    def validate_data(self, df: pd.DataFrame, min_records: int = 50) -> bool:
        """
        Validate that DataFrame has sufficient data for analysis.

        Args:
            df: DataFrame to validate
            min_records: Minimum number of records required

        Returns:
            bool: True if valid, False otherwise
        """
        if df is None or df.empty:
            logger.error("DataFrame is None or empty")
            return False

        # Check required columns
        required_columns = ["datetime", "open", "high", "low", "close", "volume"]
        if not all(col in df.columns for col in required_columns):
            logger.error("Missing required columns in price data")
            return False

        # Check for sufficient data
        if len(df) < min_records:
            logger.warning(f"Insufficient data: {len(df)} < {min_records} records")
            return False

        # Check for NaN values in price columns
        price_columns = ["open", "high", "low", "close"]
        if df[price_columns].isnull().any().any():
            logger.error("Found NaN values in price data")
            return False

        # Check for logical price relationships
        invalid_candles = (
            (df["high"] < df["low"])
            | (df["high"] < df["open"])
            | (df["high"] < df["close"])
            | (df["low"] > df["open"])
            | (df["low"] > df["close"])
        )

        if invalid_candles.any():
            logger.error("Found invalid price relationships in data")
            return False

        logger.debug(f"Data validation passed: {len(df)} records")
        return True

    def get_market_info(self, symbol: str) -> Optional[Dict]:
        """
        Get market information for a symbol.

        Args:
            symbol: Trading pair

        Returns:
            Dict with market info or None if error
        """
        try:
            url = f"{self.base_url}/ticker/24hr"
            params = {"symbol": symbol.upper()}

            response = self.session.get(url, params=params, timeout=5)
            response.raise_for_status()

            data = response.json()

            # Extract relevant information
            market_info = {
                "symbol": data["symbol"],
                "price_change": float(data["priceChange"]),
                "price_change_percent": float(data["priceChangePercent"]),
                "high_price": float(data["highPrice"]),
                "low_price": float(data["lowPrice"]),
                "volume": float(data["volume"]),
                "quote_volume": float(data["quoteVolume"]),
                "last_price": float(data["lastPrice"]),
            }

            return market_info

        except Exception as e:
            logger.error(f"Error fetching market info for {symbol}: {e}")
            return None

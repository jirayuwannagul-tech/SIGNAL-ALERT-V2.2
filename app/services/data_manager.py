import logging

import requests

import time

from typing import Dict, List, Optional, Tuple

from datetime import datetime, timedelta

import pandas as pd

from requests.adapters import HTTPAdapter

from urllib3.util import Retry


from ..utils.core_utils import JSONManager, ErrorHandler

from ..utils.data_types import DataConverter

from .config_manager import ConfigManager


class DataManager:
    """Centralized data management - รวม DataUpdater + PriceFetcher"""

    def __init__(self):

        self.logger = logging.getLogger(__name__)

        self.config = ConfigManager()

        self.json_manager = JSONManager()

        self.data_converter = DataConverter()

        # Cache management

        self.cache = {}

        self.price_cache = {}

        self.last_requests = {}

        # Rate limiting

        self.min_request_interval = 0.2  # 200ms between requests

        self.price_cache_timeout = 30  # 30 seconds for price cache

        # Setup requests session with connection pooling

        self._setup_session()

        self.logger.info("✅ DataManager initialized")

    def _setup_session(self):
        """Setup requests session with connection pooling"""

        self.session = requests.Session()

        # Retry strategy

        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )

        adapter = HTTPAdapter(
            pool_connections=10, pool_maxsize=20, max_retries=retry_strategy
        )

        self.session.mount("http://", adapter)

        self.session.mount("https://", adapter)

    @ErrorHandler.api_error_handler
    def get_current_prices(self, symbols: List[str]) -> Dict[str, float]:
        """Get current prices for multiple symbols"""

        try:

            binance_config = self.config.get_binance_config()

            symbols_param = '["' + '","'.join(symbols) + '"]'

            url = f"{binance_config['base_url']}/ticker/price"

            response = self.session.get(
                url,
                params={"symbols": symbols_param},
                timeout=binance_config["timeout"],
            )

            response.raise_for_status()

            prices = {}

            for item in response.json():

                price = float(item["price"])

                if self.data_converter.validate_price_data(price):

                    prices[item["symbol"]] = price

            # Update cache

            now = time.time()

            for symbol, price in prices.items():

                self.price_cache[f"price_{symbol}"] = {"price": price, "timestamp": now}

            self.logger.info(f"Fetched {len(prices)} current prices")

            return prices

        except Exception as e:

            self.logger.error(f"Error fetching current prices: {e}")

            return {}

    def get_current_prices_cached(self, symbols: List[str]) -> Dict[str, float]:
        """Get current prices with intelligent caching"""

        now = time.time()

        fresh_prices = {}

        symbols_to_fetch = []

        # Check cache first

        for symbol in symbols:

            cache_key = f"price_{symbol}"

            if cache_key in self.price_cache:

                cached_data = self.price_cache[cache_key]

                if now - cached_data["timestamp"] < self.price_cache_timeout:

                    fresh_prices[symbol] = cached_data["price"]

                else:

                    symbols_to_fetch.append(symbol)

            else:

                symbols_to_fetch.append(symbol)

        # Fetch missing prices

        if symbols_to_fetch:

            fetched_prices = self.get_current_prices(symbols_to_fetch)

            fresh_prices.update(fetched_prices)

        return fresh_prices

    def get_single_price(self, symbol: str) -> Optional[float]:
        """Get single symbol price with rate limiting"""

        now = time.time()
        last_request = self.last_requests.get(symbol, 0)

        if now - last_request < self.min_request_interval:
            time.sleep(self.min_request_interval - (now - last_request))

        try:
            binance_config = self.config.get_binance_config()
            url = f"{binance_config['base_url']}/ticker/price"

            response = self.session.get(
                url, params={"symbol": symbol}, timeout=binance_config["timeout"]
            )
            response.raise_for_status()

            self.last_requests[symbol] = time.time()

            price = float(response.json()["price"])
            if self.data_converter.validate_price_data(price):
                self.price_cache[f"price_{symbol}"] = {
                    "price": price,
                    "timestamp": time.time(),
                }
                return price

            return None

        except Exception as e:
            self.logger.error(f"Error fetching price for {symbol}: {e}")
            return None

    def get_klines(
        self, symbol: str, interval: str, limit: int = 500
    ) -> Optional[pd.DataFrame]:
        """Get klines data with caching"""

        cache_key = f"{symbol}_{interval}"

        # Check cache first

        if cache_key in self.cache:

            cached_data = self.cache[cache_key]

            if self._is_cache_valid(cached_data, interval):

                return cached_data["df"]

        try:

            binance_config = self.config.get_binance_config()

            url = f"{binance_config['base_url']}/klines"

            params = {"symbol": symbol, "interval": interval, "limit": limit}

            response = self.session.get(
                url, params=params, timeout=binance_config["timeout"]
            )

            response.raise_for_status()

            data = response.json()

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

            numeric_columns = ["open", "high", "low", "close", "volume"]

            for col in numeric_columns:

                df[col] = pd.to_numeric(df[col], errors="coerce")

            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")

            df = df[["timestamp", "open", "high", "low", "close", "volume"]].copy()

            # Validate DataFrame

            if not self.data_converter.validate_dataframe(df):

                self.logger.warning(f"Invalid DataFrame for {symbol} {interval}")

                return None

            # Update cache

            self.cache[cache_key] = {"df": df, "timestamp": datetime.now()}

            # Save to file for persistence

            self._save_to_file(symbol, interval, df)

            self.logger.debug(f"Loaded {len(df)} candles for {symbol} {interval}")

            return df

        except Exception as e:

            self.logger.error(f"Error fetching klines for {symbol}: {e}")

            return self._load_from_file(symbol, interval)

    def _is_cache_valid(self, cached_data: Dict, interval: str) -> bool:
        """Check if cached data is still valid"""

        now = datetime.now()

        cache_time = cached_data["timestamp"]

        # Cache validity periods

        validity_periods = {"1d": timedelta(hours=6)}

    def _save_to_file(self, symbol: str, interval: str, df: pd.DataFrame):
        """Save data to JSON file"""

        try:

            month_str = datetime.now().strftime("%Y-%m")

            filename = f"data/candles/{symbol}_{interval}_{month_str}.json"

            data = {
                "symbol": symbol,
                "interval": interval,
                "timestamp": datetime.now().isoformat(),
                "data": df.to_dict("records"),
            }

            # Convert numpy types before saving

            data = self.data_converter.convert_numpy_types(data)

            self.json_manager.save_json(data, filename)

        except Exception as e:

            self.logger.error(f"Error saving data to file: {e}")

    def _load_from_file(self, symbol: str, interval: str) -> Optional[pd.DataFrame]:
        """Load data from JSON file as fallback"""

        try:

            month_str = datetime.now().strftime("%Y-%m")

            filename = f"data/candles/{symbol}_{interval}_{month_str}.json"

            data = self.json_manager.load_json(filename)

            if not data or "data" not in data:

                return None

            df = pd.DataFrame(data["data"])

            if df.empty:

                return None

            # Convert timestamp column

            df["timestamp"] = pd.to_datetime(df["timestamp"])

            # Validate loaded data

            if self.data_converter.validate_dataframe(df):

                self.logger.info(f"Loaded fallback data for {symbol} {interval}")

                return df

            return None

        except Exception as e:

            self.logger.error(f"Error loading data from file: {e}")

            return None

    def clear_cache(self):
        """Clear all caches"""

        self.cache.clear()

        self.price_cache.clear()

        self.logger.info("Cache cleared")

    def process_websocket_kline(self, kline_data: Dict, signal_detector=None):
        """Process real-time kline from WebSocket"""

        try:

            symbol = kline_data["symbol"]

            timeframe = kline_data["timeframe"]

            cache_key = f"{symbol}_{timeframe}_realtime"

            # ✅ log แค่ทุก 1 นาที (ต่อ symbol+timeframe)

            now = datetime.now()

            minute_key = f"{symbol}_{timeframe}"

            last_ts = getattr(self, "_last_minute_log", {}).get(minute_key)

            if last_ts is None or (now - last_ts).total_seconds() >= 60:

                # สร้าง dict ครั้งแรกถ้ายังไม่มี

                if not hasattr(self, "_last_minute_log"):

                    self._last_minute_log = {}

                self._last_minute_log[minute_key] = now

                self.logger.info("🎯 DataManager.process_websocket_kline() called")

                self.logger.info(
                    f"📊 {symbol} {timeframe} | C: {float(kline_data.get('close', 0)):.2f} | Closed: {bool(kline_data.get('is_closed'))}"
                )

            # Update real-time cache

            self.cache[cache_key] = {
                "data": kline_data,
                "timestamp": now,
            }

            # When candle closes

            if kline_data.get("is_closed"):

                self.logger.info(
                    f"📊 Candle closed: {symbol} {timeframe} "
                    f"C: {float(kline_data.get('close', 0)):.2f}"
                )

                # Forward to SignalDetector for analysis (only on close)

                if signal_detector is not None:

                    try:

                        signal_detector.analyze_realtime(kline_data)

                    except Exception as e:

                        self.logger.error(f"Error forwarding to SignalDetector: {e}")

        except Exception as e:

            self.logger.error(f"Error processing WebSocket kline: {e}")

    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""

        return {
            "klines_cache_size": len(self.cache),
            "price_cache_size": len(self.price_cache),
            "last_requests_count": len(self.last_requests),
        }

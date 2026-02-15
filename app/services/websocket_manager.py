"""

WebSocket Manager v2.2 - Real-time Binance Data Stream

"""

import logging

import json

import time

import threading

from typing import Callable, Optional, Dict

import websocket


logger = logging.getLogger(__name__)


class WebSocketManager:

    def __init__(self, symbol: str = "btcusdt", timeframe: str = "1d"):

        self.symbol = symbol.lower()

        self.timeframe = timeframe.lower()

        self.base_url = "wss://stream.binance.com:9443/ws"

        self.stream_name = f"{self.symbol}@kline_{self.timeframe}"

        self.ws = None

        self.ws_thread = None

        self.is_running = False

        self.reconnect_attempts = 0

        self.max_reconnect_attempts = 10

        self.reconnect_delay = 5

        self.on_kline_callback: Optional[Callable] = None

        logger.info(f"WebSocketManager initialized: {self.stream_name}")

    def connect(self):

        if self.is_running:

            logger.warning("WebSocket already running")

            return

        self.is_running = True

        self.reconnect_attempts = 0

        ws_url = f"{self.base_url}/{self.stream_name}"

        logger.info(f"Connecting to: {ws_url}")

        self.ws = websocket.WebSocketApp(
            ws_url,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
            on_open=self._on_open,
        )

        self.ws_thread = threading.Thread(target=self._run_websocket, daemon=True)

        self.ws_thread.start()

        logger.info("WebSocket thread started")

    def _run_websocket(self):

        try:

            self.ws.run_forever(ping_interval=20, ping_timeout=10)

        except Exception as e:

            logger.error(f"WebSocket run error: {e}")

            self._attempt_reconnect()

    def disconnect(self):

        logger.info("Disconnecting WebSocket...")

        self.is_running = False

        if self.ws:

            self.ws.close()

        logger.info("WebSocket disconnected")

    def _on_message(self, ws, message):

        # logger.info("🔔 Message received")

        try:

            data = json.loads(message)

            if data.get("e") != "kline":

                return

            kline = data.get("k", {})

            kline_data = {
                "symbol": data.get("s"),
                "timeframe": self.timeframe,
                "open_time": kline.get("t"),
                "close_time": kline.get("T"),
                "open": float(kline.get("o", 0)),
                "high": float(kline.get("h", 0)),
                "low": float(kline.get("l", 0)),
                "close": float(kline.get("c", 0)),
                "volume": float(kline.get("v", 0)),
                "is_closed": kline.get("x", False),
            }

            if self.on_kline_callback:

                self.on_kline_callback(kline_data)

            if kline_data["is_closed"]:

                logger.info(
                    f"🕯️ Kline closed: {kline_data['symbol']} {self.timeframe} C: {kline_data['close']:.2f}"
                )

        except Exception as e:

            logger.error(f"Error processing message: {e}")

    def _on_open(self, ws):

        logger.info(f"✅ WebSocket connected: {self.stream_name}")

        self.reconnect_attempts = 0

    def _on_error(self, ws, error):

        logger.error(f"❌ WebSocket error: {error}")

    def _on_close(self, ws, close_status_code, close_msg):

        logger.warning(f"🔌 WebSocket closed: {close_status_code} - {close_msg}")

        logger.warning(
            f"🔍 Debug: is_running={self.is_running}, reconnect_attempts={self.reconnect_attempts}"
        )

        if self.is_running:

            logger.info("🔄 Initiating reconnect...")

            self._attempt_reconnect()

        else:

            logger.warning("⚠️ Not reconnecting (is_running=False)")

    def _attempt_reconnect(self):

        if self.reconnect_attempts >= self.max_reconnect_attempts:

            logger.error(
                f"Max reconnect attempts ({self.max_reconnect_attempts}) reached. Giving up."
            )

            self.is_running = False

            return

        self.reconnect_attempts += 1

        wait_time = self.reconnect_delay * self.reconnect_attempts

        logger.info(
            f"🔄 Reconnect attempt {self.reconnect_attempts}/{self.max_reconnect_attempts} in {wait_time}s..."
        )

        time.sleep(wait_time)

        if self.is_running:

            self.ws = None

            ws_url = f"{self.base_url}/{self.stream_name}"

            logger.info(f"Reconnecting to: {ws_url}")

            self.ws = websocket.WebSocketApp(
                ws_url,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
                on_open=self._on_open,
            )

            self.ws_thread = threading.Thread(target=self._run_websocket, daemon=True)

            self.ws_thread.start()

    def set_kline_callback(self, callback: Callable):

        self.on_kline_callback = callback

        logger.info("Kline callback registered")

    def get_status(self) -> Dict:

        return {
            "is_running": self.is_running,
            "stream": self.stream_name,
            "reconnect_attempts": self.reconnect_attempts,
            "thread_alive": self.ws_thread.is_alive() if self.ws_thread else False,
        }

    def change_stream(self, symbol: str, timeframe: str):

        logger.info(f"Changing stream to {symbol}@kline_{timeframe}")

        self.disconnect()

        time.sleep(2)

        self.symbol = symbol.lower()

        self.timeframe = timeframe.lower()

        self.stream_name = f"{self.symbol}@kline_{self.timeframe}"

        self.connect()

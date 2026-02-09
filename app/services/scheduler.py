import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from config.settings import Config
from app.services.telegram_notifier import TelegramNotifier

logger = logging.getLogger(__name__)

class SignalScheduler:
    def __init__(self, config: Dict):
        self.config = config
        self.scheduler = BackgroundScheduler()
        self.running = False
        self.signal_detector = None
        self.position_manager = None
        self.line_notifier = None
        self.telegram_notifier = None
        self.sheets_logger = None
        self.last_signals = {}  
        self.cooldown_minutes = Config.SIGNAL_COOLDOWN_MINUTES
        self.signal_history_file = "data/signal_history.json"
        self._load_signal_history()
        logger.info(f"SignalScheduler v2.0 initialized with {self.cooldown_minutes}min cooldown")

    def _load_signal_history(self):
        try:
            if os.path.exists(self.signal_history_file):
                with open(self.signal_history_file, 'r') as f:
                    data = json.load(f)
                for key, timestamp_str in data.items():
                    self.last_signals[key] = datetime.fromisoformat(timestamp_str)
                logger.info(f"Loaded {len(self.last_signals)} signal history records")
        except Exception as e:
            logger.error(f"Error loading signal history: {e}")

    def _save_signal_history(self):
        try:
            os.makedirs(os.path.dirname(self.signal_history_file), exist_ok=True)
            data = {k: v.isoformat() for k, v in self.last_signals.items()}
            with open(self.signal_history_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving signal history: {e}")

    def _is_duplicate_signal(self, symbol: str, timeframe: str, direction: str) -> bool:
        signal_key = f"{symbol}_{timeframe}_{direction}"
        current_time = datetime.now()
        if signal_key in self.last_signals:
            last_time = self.last_signals[signal_key]
            time_diff = current_time - last_time
            if time_diff.total_seconds() < (self.cooldown_minutes * 60):
                return True
        return False

    def _record_signal(self, symbol: str, timeframe: str, direction: str):
        self.last_signals[f"{symbol}_{timeframe}_{direction}"] = datetime.now()
        self._save_signal_history()

    def set_services(self, signal_detector, position_manager, line_notifier, sheets_logger):
        self.signal_detector = signal_detector
        self.position_manager = position_manager
        self.line_notifier = line_notifier
        self.sheets_logger = sheets_logger
        self.telegram_notifier = TelegramNotifier(
            token=self.config.get("telegram_token"),
            chat_id=self.config.get("telegram_chat_id")
        )

    def start_scheduler(self):
        if self.running: return
        self.scheduler.add_job(
            func=self._scan_4h_signals, trigger="cron", hour="*", minute="*/15",
            id="scan_4h_signals", replace_existing=True
        )
        self.scheduler.add_job(
            func=self._scan_1d_signals, trigger="cron", hour="0,4,8,12,16,20", minute=0,
            id="scan_1d_signals", replace_existing=True
        )
        self.scheduler.add_job(
            func=self._update_positions_refactored, trigger=IntervalTrigger(minutes=2),
            id="update_positions", replace_existing=True
        )
        self.scheduler.add_job(
            func=self._send_daily_summary, trigger="cron", hour=0, minute=0,
            id="daily_summary", replace_existing=True
        )
        self.scheduler.start()
        self.running = True
        logger.info("SignalScheduler v2.0 Dual-Channel started")

    def _scan_4h_signals(self):
        try:
            symbols = getattr(Config, 'DEFAULT_SYMBOLS', ["BTCUSDT", "ETHUSDT"])
            active_signals = self.signal_detector.get_active_signals(symbols, ["4h"])
            for signal in active_signals:
                self._process_signal_refactored(signal, "4h")
        except Exception as e:
            logger.error(f"Error in 4h scan: {e}")

    def _scan_1d_signals(self):
        try:
            symbols = getattr(Config, 'DEFAULT_SYMBOLS', ["BTCUSDT", "ETHUSDT"])
            active_signals = self.signal_detector.get_active_signals(symbols, ["1d"])
            for signal in active_signals:
                self._process_signal_refactored(signal, "1d")
        except Exception as e:
            logger.error(f"Error in 1d scan: {e}")

    def _process_signal_refactored(self, signal: Dict, timeframe: str) -> bool:
        try:
            symbol = signal.get("symbol")
            signals = signal.get("signals", {})
            direction = "LONG" if signals.get("buy") else "SHORT" if signals.get("short") else None
            if not symbol or not direction or signal.get("signal_strength", 0) < 75:
                return False
            if self._is_duplicate_signal(symbol, timeframe, direction):
                return False
            if not signal.get("position_created", False):
                self._record_signal(symbol, timeframe, direction)
                return False
            
            if self.line_notifier: self.line_notifier.send_signal_alert(signal)
            if self.telegram_notifier: self.telegram_notifier.send_signal_alert(signal)
            if self.sheets_logger: self.sheets_logger.log_trading_journal(signal)
            
            self._record_signal(symbol, timeframe, direction)
            return True
        except Exception as e:
            logger.error(f"Process error: {e}")
            return False

    def _update_positions_refactored(self):
        try:
            if not self.position_manager: return
            updates = self.position_manager.update_positions()
            for pid, upinfo in updates.items():
                if upinfo.get('position_closed') or upinfo.get('sl_hit',{}).get('hit'):
                    if self.line_notifier: self.line_notifier.send_position_update({"updates": upinfo})
                    if self.telegram_notifier: self.telegram_notifier.send_signal_alert({"symbol": pid, "status": "CLOSED"})
        except Exception as e:
            logger.error(f"Update error: {e}")

    def _send_daily_summary(self):
        try:
            summary = {"date": datetime.now().strftime("%Y-%m-%d"), "status": "Active"}
            if self.line_notifier: self.line_notifier.send_daily_summary(summary)
            if self.telegram_notifier: self.telegram_notifier.send_signal_alert({"summary": "Daily Report Sent"})
        except Exception as e:
            logger.error(f"Summary error: {e}")

    def stop_scheduler(self):
        if self.running:
            self._save_signal_history()
            self.scheduler.shutdown(wait=False)
            self.running = False
            logger.info("SignalScheduler stopped")

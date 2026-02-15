"""Signal History Manager - Persistent storage for signals (1D + intraday with cooldown)"""

import os

import json

import logging

from pathlib import Path

from datetime import datetime, timezone

from typing import Dict, Optional


logger = logging.getLogger(__name__)


class SignalHistoryManager:

    def __init__(self, data_dir: str = None):

        # =========================

        # L1) Config Layer

        # =========================

        if data_dir is None:

            data_dir = os.getenv("DATA_DIR", "data")

        # =========================

        # L2) Storage Layer

        # =========================

        self.data_dir = Path(data_dir)

        self.data_dir.mkdir(parents=True, exist_ok=True)

        # ไฟล์เดิม (คงชื่อเดิมเพื่อไม่กระทบระบบอื่น)

        self.history_file = self.data_dir / "signal_history_1d.json"

        # =========================

        # L3) Load Layer

        # =========================

        self.signal_history = self._load_history()

        for k, v in self.signal_history.items():

            logger.info(f"📌 {k} => {v}")

        logger.info(f"✅ SignalHistoryManager initialized (File: {self.history_file})")

    def _load_history(self) -> Dict:

        # =========================

        # L1) Read Layer

        # =========================

        try:

            if self.history_file.exists():

                with open(self.history_file, "r") as f:

                    data = json.load(f)

                    logger.info(f"📂 Loaded {len(data)} signal histories")

                    return data

            logger.info("📂 No existing history file, starting fresh")

            return {}

        except Exception as e:

            logger.error(f"Error loading history: {e}")

            return {}

    def _save_history(self):

        # =========================

        # L1) Write Layer

        # =========================

        try:

            with open(self.history_file, "w") as f:

                json.dump(self.signal_history, f, indent=2)

            logger.debug(
                f"💾 Saved signal history ({len(self.signal_history)} entries)"
            )

        except Exception as e:

            logger.error(f"Error saving history: {e}")

    def _get_cooldown_minutes(self, timeframe: str) -> int:
        """

        Cooldown policy

        - 15m: 60 นาที (1 ชั่วโมง)

        - 1d: 1440 นาที (1 วัน)

        """

        return {
            "15m": 60,
            "1d": 1440,
        }.get(timeframe, 60)

    def _parse_iso_datetime(self, iso_str: str) -> Optional[datetime]:
        """

        รองรับ date เดิมที่อาจไม่มี timezone และของใหม่ที่มี timezone

        """

        if not iso_str:

            return None

        try:

            dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))

            if dt.tzinfo is None:

                dt = dt.replace(tzinfo=timezone.utc)

            return dt.astimezone(timezone.utc)

        except Exception:

            return None

    def should_notify(
        self, symbol: str, timeframe: str, signal_type: str, current_price: float
    ) -> bool:
        """

        Check if should notify for this signal (with cooldown)



        Key design: ใช้ key = symbol_timeframe_signal_type (เหมือนเดิม)

        Behavior:

        - ถ้าไม่เคยมี key นี้ -> แจ้ง

        - ถ้าเคยมี -> แจ้งได้อีกเมื่อ cooldown ผ่าน

        """

        # =========================

        # L1) Key Layer

        # =========================

        key = f"{symbol}_{timeframe}_{signal_type}"

        # =========================

        # L2) New Signal Layer

        # =========================

        if key not in self.signal_history:

            return True

        last_signal = self.signal_history.get(key, {})

        # =========================

        # L3) Cooldown Layer

        # =========================

        cooldown_minutes = self._get_cooldown_minutes(timeframe)

        last_dt = self._parse_iso_datetime(last_signal.get("date"))

        if last_dt is None:

            return True  # parse ไม่ได้ ให้แจ้ง (กันพลาด)

        now_dt = datetime.now(timezone.utc)

        minutes = (now_dt - last_dt).total_seconds() / 60.0

        if minutes >= cooldown_minutes:

            return True

        logger.debug(f"⏭️ Skip: {key} cooldown not passed ({cooldown_minutes}m)")

        return False

    def record_signal(
        self, symbol: str, timeframe: str, signal_type: str, current_price: float
    ):
        """

        Record that signal was notified

        - บันทึกแบบ timezone-safe เพื่อใช้คำนวณ cooldown ได้ชัวร์

        """

        # =========================

        # L1) Key Layer

        # =========================

        key = f"{symbol}_{timeframe}_{signal_type}"

        # =========================

        # L2) Record Layer

        # =========================

        self.signal_history[key] = {
            "symbol": symbol,
            "timeframe": timeframe,
            "signal_type": signal_type,
            "price": current_price,
            "date": datetime.now(timezone.utc).isoformat(),
            "notified": True,
        }

        # =========================

        # L3) Persist Layer

        # =========================

        self._save_history()

        logger.info(f"📝 Recorded: {key} @ {current_price}")

    def clear_opposite_signal(self, symbol: str, timeframe: str, signal_type: str):
        """

        Clear opposite signal when trend changes (เหมือนเดิม)

        """

        # =========================

        # L1) Opposite Key Layer

        # =========================

        opposite = "SHORT" if signal_type == "LONG" else "LONG"

        key = f"{symbol}_{timeframe}_{opposite}"

        # =========================

        # L2) Delete Layer

        # =========================

        if key in self.signal_history:

            del self.signal_history[key]

            self._save_history()

            logger.info(f"🗑️ Cleared opposite signal: {key}")

    def get_history(self, symbol: Optional[str] = None) -> Dict:

        # =========================

        # L1) Filter Layer

        # =========================

        if symbol:

            return {
                k: v
                for k, v in self.signal_history.items()
                if v.get("symbol") == symbol
            }

        return self.signal_history

    def clear_history(self):

        # =========================

        # L1) Clear Layer

        # =========================

        self.signal_history = {}

        self._save_history()

        logger.info("🗑️ Cleared all signal history")

    def get_stats(self) -> Dict:

        # =========================

        # L1) Stats Layer

        # =========================

        total = len(self.signal_history)

        long_count = sum(
            1 for v in self.signal_history.values() if v.get("signal_type") == "LONG"
        )

        short_count = sum(
            1 for v in self.signal_history.values() if v.get("signal_type") == "SHORT"
        )

        return {
            "total_signals": total,
            "long_signals": long_count,
            "short_signals": short_count,
            "file_path": str(self.history_file),
            "file_exists": self.history_file.exists(),
        }

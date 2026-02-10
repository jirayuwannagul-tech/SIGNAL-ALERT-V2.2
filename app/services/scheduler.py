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
    """
    Auto Scheduler v2.2 - ระบบจัดการสัญญาณเทรดและสมาชิก VIP
    แบ่ง Layer ชัดเจนเพื่อให้ง่ายต่อการแก้ไข
    """

    def __init__(self, config: Dict):
        # ================================================================
        # 🌐 LAYER 0: Initialization (ตั้งค่าระบบพื้นฐาน)
        # ================================================================
        self.config = config
        self.scheduler = BackgroundScheduler()
        self.running = False
        
        # Services Placeholder
        self.signal_detector = None
        self.position_manager = None
        self.member_manager = None  # 🎯 เพิ่มระบบจัดการสมาชิก
        self.line_notifier = None
        self.telegram_notifier = None
        self.sheets_logger = None
        
        # Signal Deduplication
        self.last_signals = {}  
        self.cooldown_minutes = Config.SIGNAL_COOLDOWN_MINUTES
        self.signal_history_file = "data/signal_history.json"
        
        self._load_signal_history()
        logger.info(f"SignalScheduler v2.2 initialized with {self.cooldown_minutes}min cooldown")

    # ================================================================
    # 🛰️ LAYER 1: Core Scheduling Control (ควบคุมการเริ่ม/หยุดงาน)
    # ================================================================

    def start_scheduler(self):
        """เริ่มการทำงานของ Job ทั้งหมด"""
        if self.running: return

        # Job: ตรวจสอบสัญญาณเทรด 4H (ทุก 15 นาที)
        self.scheduler.add_job(
            func=self._scan_4h_signals, trigger="cron", hour="*", minute="*/15",
            id="scan_4h_signals", replace_existing=True
        )
        
        # Job: ตรวจสอบสัญญาณเทรด 1D (ทุก 4 ชั่วโมง)
        self.scheduler.add_job(
            func=self._scan_1d_signals, trigger="cron", hour="0,4,8,12,16,20", minute=0,
            id="scan_1d_signals", replace_existing=True
        )
        
        # Job: อัปเดตสถานะ Position (ทุก 2 นาที)
        self.scheduler.add_job(
            func=self._update_positions_refactored, trigger=IntervalTrigger(minutes=2),
            id="update_positions", replace_existing=True
        )

        # Job: ตรวจสอบสมาชิกหมดอายุ (ทุกวัน เวลา 00:05)
        self.scheduler.add_job(
            func=self._check_membership_expiry, trigger="cron", hour=0, minute=5,
            id="check_membership", replace_existing=True
        )
        
        # Job: รายงานสรุปประจำวัน (ทุกเที่ยงคืน)
        self.scheduler.add_job(
            func=self._send_daily_summary, trigger="cron", hour=0, minute=0,
            id="daily_summary", replace_existing=True
        )

        self.scheduler.start()
        self.running = True
        logger.info("✅ SignalScheduler v2.2 (Trading + VIP System) started")

    def stop_scheduler(self):
        """หยุดการทำงานและเซฟประวัติ"""
        if self.running:
            self._save_signal_history()
            self.scheduler.shutdown(wait=False)
            self.running = False
            logger.info("SignalScheduler stopped")

    # ================================================================
    # 📢 LAYER 2: Trading Signal Logic (ตรรกะการวิเคราะห์และพ่นสัญญาณ)
    # ================================================================

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
        """จัดการสัญญาณที่กรองแล้วและส่งเข้าห้อง TG/LINE"""
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
            
            # พ่นซิกเข้า Telegram (แยกห้อง VIP/ธรรมดา ใน TelegramNotifier)
            if self.telegram_notifier: 
                self.telegram_notifier.send_signal_alert(signal)
            
            # ช่องทางสำรองอื่นๆ
            if self.line_notifier: self.line_notifier.send_signal_alert(signal)
            if self.sheets_logger: self.sheets_logger.log_trading_journal(signal)
            
            self._record_signal(symbol, timeframe, direction)
            return True
        except Exception as e:
            logger.error(f"Process error: {e}")
            return False

    # ================================================================
    # 👤 LAYER 3: Membership Management (ระบบตรวจสอบสมาชิกหมดอายุ)
    # ================================================================

    def _check_membership_expiry(self):
        """ตรวจสอบและเตะสมาชิกที่หมดอายุออกจากห้อง VIP"""
        try:
            if self.member_manager:
                logger.info("👤 Checking VIP membership expiry...")
                vip_group_id = self.config.get("telegram_chat_id")
                self.member_manager.check_and_cleanup_expiry(vip_group_id)
        except Exception as e:
            logger.error(f"❌ Membership expiry check error: {e}")

    # ================================================================
    # 📊 LAYER 4: Maintenance & Reports (สรุปผลและอัปเดตราคา)
    # ================================================================

    def _update_positions_refactored(self):
        try:
            if not self.position_manager: return
            updates = self.position_manager.update_positions()
            for pid, upinfo in updates.items():
                if upinfo.get('position_closed'):
                    # แจ้งเตือนปิดออเดอร์/Hit TP/SL
                    if self.telegram_notifier: 
                        msg = f"📊 *Update:* {pid} Closed\nStatus: {upinfo.get('close_reason', 'N/A')}"
                        self.telegram_notifier.send_message(msg)
        except Exception as e:
            logger.error(f"Update error: {e}")

    def _send_daily_summary(self):
        try:
            summary = {"date": datetime.now().strftime("%Y-%m-%d"), "status": "Active"}
            if self.telegram_notifier: 
                self.telegram_notifier.send_message(f"📅 *Daily Report {summary['date']}*\nระบบทำงานปกติ พร้อมดูแลห้อง VIP และห้องธรรมดาครับ")
        except Exception as e:
            logger.error(f"Summary error: {e}")

    # ================================================================
    # 🛠️ LAYER 5: Service Injection & History
    # ================================================================

    def set_services(self, signal_detector, position_manager, line_notifier, sheets_logger, member_manager=None):
        self.signal_detector = signal_detector
        self.position_manager = position_manager
        self.line_notifier = line_notifier
        self.sheets_logger = sheets_logger
        self.member_manager = member_manager
        self.telegram_notifier = TelegramNotifier(
            token=os.getenv("TELEGRAM_BOT_TOKEN"),
            chat_id=os.getenv("TELEGRAM_CHAT_ID")
        )

    def _load_signal_history(self):
        try:
            if os.path.exists(self.signal_history_file):
                with open(self.signal_history_file, 'r') as f:
                    data = json.load(f)
                self.last_signals = {k: datetime.fromisoformat(v) for k, v in data.items()}
        except Exception as e:
            logger.error(f"Load history error: {e}")

    def _save_signal_history(self):
        try:
            os.makedirs(os.path.dirname(self.signal_history_file), exist_ok=True)
            data = {k: v.isoformat() for k, v in self.last_signals.items()}
            with open(self.signal_history_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Save history error: {e}")

    def _is_duplicate_signal(self, symbol: str, timeframe: str, direction: str) -> bool:
        key = f"{symbol}_{timeframe}_{direction}"
        if key in self.last_signals:
            return (datetime.now() - self.last_signals[key]).total_seconds() < (self.cooldown_minutes * 60)
        return False

    def _record_signal(self, symbol: str, timeframe: str, direction: str):
        self.last_signals[f"{symbol}_{timeframe}_{direction}"] = datetime.now()
        self._save_signal_history()
import json
import logging
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
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
        
        # Job: ตรวจสอบสัญญาณเทรด 1D (07:05 ไทย = 00:05 UTC)
        self.scheduler.add_job(
            func=self._scan_1d_signals,
            trigger="cron",
            hour=0,
            minute=5,
            id="scan_1d_signals",
            replace_existing=True
        )

        # Job: อัปเดตสถานะ Position (ทุก 1 นาที)
        self.scheduler.add_job(
            func=self._update_positions_refactored,
            trigger=IntervalTrigger(minutes=1),
            id="update_positions",
            replace_existing=True
        )

        # Job: ตรวจสอบสมาชิกหมดอายุ (ทุกวัน เวลา 00:05)
        self.scheduler.add_job(
            func=self._check_membership_expiry,
            trigger="cron",
            hour=10,   # 17:00 ไทย
            minute=0,
            id="check_membership",
            replace_existing=True
        )

        # Job: รายงานสรุปประจำวัน (20:00 ไทย = 13:00 UTC)
        self.scheduler.add_job(
            func=self._send_daily_summary,
            trigger="cron",
            hour=13,
            minute=0,
            id="daily_summary",
            replace_existing=True
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

    def _scan_1d_signals(self):
        try:
            symbols = getattr(Config, 'DEFAULT_SYMBOLS', ["BTCUSDT", "ETHUSDT"])
            results = self.signal_detector.scan_multiple_symbols(symbols, ["1d"])
            
            for r in results:
                symbol = r.get("symbol")
                sig = r.get("signals", {})
                
                # ====== 1) CROSS ALERT (แจ้งเตือนรอ pullback) ======
                if sig.get("cross_up") or sig.get("cross_down"):
                    direction = "CROSS_UP" if sig.get("cross_up") else "CROSS_DOWN"
                    if not self._is_duplicate_signal(symbol, "1d", direction):
                        if self.telegram_notifier:
                            if sig.get("cross_up"):
                                msg = (
                                    f"🟢 ว้าว! EMA ตัดกันแล้วจ้า~\n"
                                    f"━━━━━━━━━━━━━━━\n"
                                    f"🪙 {symbol} (1D)\n"
                                    f"📈 EMA12 วิ่งแซง EMA26 ไปแล้วจ้า!\n"
                                    f"🚀 กระทิงตื่นนอน... เตรียมตัว!\n"
                                    f"⏳ ใจเย็นๆ รอ PULLBACK ก่อนนะ\n"
                                    f"💡 อย่าเพิ่ง FOMO เด้อ~\n"
                                    f"━━━━━━━━━━━━━━━"
                                )
                            else:
                                msg = (
                                    f"🔴 โอ้โห! EMA ตัดลงแล้วว~\n"
                                    f"━━━━━━━━━━━━━━━\n"
                                    f"🪙 {symbol} (1D)\n"
                                    f"📉 EMA12 ดิ่งลงใต้ EMA26 แล้ว!\n"
                                    f"🐻 หมีตื่น... ระวังหัวนะจ๊ะ!\n"
                                    f"⏳ ใจเย็นๆ รอ PULLBACK ก่อน\n"
                                    f"💡 อย่าเพิ่งกระโดดลงเหวนะ~\n"
                                    f"━━━━━━━━━━━━━━━"
                                )
                            self.telegram_notifier.send_message(msg, thread_id=2)
                        self._record_signal(symbol, "1d", direction)
                
                # ====== 2) PULLBACK ENTRY (ส่งสัญญาณเข้าเทรด) ======
                if sig.get("buy") or sig.get("short"):
                    self._process_signal_refactored(r, "1d")
                    
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

            # เดิม: ถ้า position_created=False จะ record แล้ว return False -> ทำให้ไม่ส่ง TG
            # ใหม่: record ไว้ได้ แต่ "ไม่หยุด" ให้ส่งต่อได้เลย
            if not signal.get("position_created", False):
                self._record_signal(symbol, timeframe, direction)

            # ===== Telegram ส่งจาก analyze_symbol() แล้ว ไม่ต้องส่งซ้ำ =====
            logger.info(f"✅ Signal processed: {signal.get('symbol')} {timeframe} {direction}")

            # ช่องทางสำรองอื่นๆ
            if self.line_notifier:
                self.line_notifier.send_signal_alert(signal)
            if self.sheets_logger:
                self.sheets_logger.log_trading_journal(signal)

            # กันพลาด: บันทึกสัญญาณหลังส่งด้วย
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
            if not self.position_manager:
                return

            updates = self.position_manager.update_positions()

            for pid, upinfo in updates.items():

                # ===== แจ้ง TP1 / TP2 / TP3 เฉพาะตอนเพิ่ง HIT =====
                for tp in ["TP1_hit", "TP2_hit", "TP3_hit"]:
                    if upinfo.get(tp):
                        if self.telegram_notifier:
                            msg = (
                                f"🎯 *{tp.replace('_hit','')} HIT*\n"
                                f"ID: {pid}\n"
                                f"Price: {upinfo[tp].get('price')}\n"
                                f"Target: {upinfo[tp].get('target_price')}"
                            )
                            thread_id = int(os.getenv("TOPIC_CHAT_ID", 1))
                            self.telegram_notifier.send_message(msg, thread_id=thread_id)


                # ===== แจ้ง SL =====
                if upinfo.get("sl_hit"):
                    if self.telegram_notifier:
                        msg = (
                            f"🛑 *SL HIT*\n"
                            f"ID: {pid}\n"
                            f"Price: {upinfo['sl_hit'].get('price')}\n"
                            f"Target: {upinfo['sl_hit'].get('target_price')}"
                        )
                        thread_id = int(os.getenv("TOPIC_CHAT_ID", 1))
                        self.telegram_notifier.send_message(msg, thread_id=thread_id)


                # ===== แจ้งปิด position (ส่งเฉพาะตอนปิดจริง) =====
                if upinfo.get("position_closed"):
                    if self.telegram_notifier:
                        thread_id = int(os.getenv("TOPIC_CHAT_ID", 1))
                        msg = f"📊 *Update:* {pid} Closed\nReason: {upinfo.get('close_reason', 'N/A')}"
                        self.telegram_notifier.send_message(msg, thread_id=thread_id)

        except Exception as e:
            logger.error(f"Update error: {e}")

    def _send_daily_summary(self):
        try:
            if not self.telegram_notifier:
                return

            tz = ZoneInfo("Asia/Bangkok")
            today_th = datetime.now(tz).date()

            entries_today = 0
            tp1_today = 0
            tp2_today = 0
            tp3_today = 0
            sl_today = 0

            active_now = 0
            closed_today = 0

            # ✅ reload positions from file to ensure sync
            pm = getattr(self, "position_manager", None)
            if pm and hasattr(pm, "_load_positions"):
                pm.positions = pm._load_positions()
            positions = getattr(pm, "positions", {}) if pm else {}

            def _parse_dt(dt_str: str):
                """Parse ISO datetime string to Bangkok timezone"""
                if not dt_str:
                    return None
                try:
                    dt_str = dt_str.replace("Z", "+00:00")
                    dt = datetime.fromisoformat(dt_str)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=tz)
                    return dt.astimezone(tz)
                except Exception:
                    return None

            for _pid, p in (positions or {}).items():
                try:
                    # active now
                    if p.get("status") == "ACTIVE":
                        active_now += 1

                    # entries today
                    et_dt = _parse_dt(p.get("entry_time"))
                    if et_dt and et_dt.date() == today_th:
                        entries_today += 1

                    # closed today
                    ct_dt = _parse_dt(p.get("close_time"))
                    if ct_dt and ct_dt.date() == today_th:
                        closed_today += 1

                    # TP/SL today (จาก events)
                    ev = p.get("events") or {}
                    for k in ("TP1", "TP2", "TP3", "SL"):
                        e = ev.get(k)
                        if not e or not isinstance(e, dict):
                            continue
                        ts_dt = _parse_dt(e.get("timestamp"))
                        if not ts_dt or ts_dt.date() != today_th:
                            continue

                        if k == "TP1": tp1_today += 1
                        elif k == "TP2": tp2_today += 1
                        elif k == "TP3": tp3_today += 1
                        elif k == "SL": sl_today += 1

                except Exception as ex:
                    logger.warning(f"Summary parse error for {_pid}: {ex}")
                    continue

            msg = (
                f"📅 DAILY SUMMARY {today_th.isoformat()} (TH)\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"📌 เข้าไม้วันนี้: {entries_today}\n"
                f"🎯 TP1: {tp1_today} | TP2: {tp2_today} | TP3: {tp3_today}\n"
                f"🛑 SL: {sl_today}\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"🟢 Active ตอนนี้: {active_now}\n"
                f"🔒 ปิดวันนี้: {closed_today}\n"
            )

            self.telegram_notifier.send_message(msg, thread_id=self.telegram_notifier.topics.get("normal"))
            
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
            self.last_signals = {}
            changed = False

            if os.path.exists(self.signal_history_file):
                with open(self.signal_history_file, "r") as f:
                    data = json.load(f) or {}

                if isinstance(data, dict):
                    for k, v in data.items():
                        try:
                            # ✅ legacy: {key: "timestamp"}
                            if isinstance(v, str):
                                self.last_signals[k] = datetime.fromisoformat(v)
                                changed = True

                            # ✅ new: {key: {"date": "...", "notified": True}}
                            elif isinstance(v, dict):
                                date_str = v.get("date")
                                if date_str:
                                    self.last_signals[k] = datetime.fromisoformat(date_str)

                        except Exception:
                            continue

            # ✅ persist migration once (convert old str -> dict format)
            if changed:
                self._save_signal_history()

        except Exception as e:
            logger.error(f"Load history error: {e}")


    def _save_signal_history(self):
        try:
            os.makedirs(os.path.dirname(self.signal_history_file), exist_ok=True)

            # ✅ always save in new format
            data = {
                k: {"date": dt.isoformat(), "notified": True}
                for k, dt in self.last_signals.items()
            }

            with open(self.signal_history_file, "w") as f:
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

    def get_scheduler_status(self) -> Dict:
        """Used by /api/scheduler/status and tests. Must not raise."""
        try:
            running = bool(self.running)
            return {
                "ok": True,
                "running": running,
                "status": "running" if running else "stopped",
                "jobs": len(self.scheduler.get_jobs()) if self.scheduler else 0,
            }
        except Exception as e:
            return {"ok": False, "running": False, "status": "error", "error": str(e)}

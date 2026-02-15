import os
import logging
from typing import Dict, Any
from ..utils.core_utils import ConfigValidator
class ConfigManager:
    """Centralized configuration management - REFACTORED v2.2 (Telegram Sub)"""
    _instance = None
    _config = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    def __init__(self):
        if self._config is None:
            self._load_config()
    def _load_config(self):
        """Load and validate all configuration layers"""
        # ================================================================
        # 🌐 LAYER 1: Required Environment Variables (ด่านตรวจหลัก)
        # ================================================================
        required_env_vars = [
            "TELEGRAM_BOT_TOKEN",  # Token จาก BotFather
            "TELEGRAM_CHAT_ID",  # ID กลุ่มหลัก (Group ID)
        ]
        try:
            # ใช้ Validator ตรวจสอบตัวแปรที่จำเป็น
            self._config = ConfigValidator.validate_required_env_vars(required_env_vars)
            # ================================================================
            # 📡 LAYER 2: System & Telegram Configuration
            # ================================================================
            self._config.update(
                {
                    # System Basics
                    "DEBUG": os.getenv("DEBUG", "false").lower() == "true",
                    "PORT": int(os.getenv("PORT", "8080")),
                    "VERSION": os.getenv("VERSION", "2.2-telegram-sub"),
                    # Binance Config
                    "BINANCE_BASE_URL": "https://fapi.binance.com/fapi/v1",
                    # Telegram Topic IDs (แยกตามจุดประสงค์การใช้งาน)
                    "TOPIC_NORMAL_ID": os.getenv(
                        "TOPIC_NORMAL_ID"
                    ),  # ห้องสัญญาณธรรมดา (Spot)
                    "TOPIC_VIP_ID": os.getenv("TOPIC_VIP_ID"),  # ห้องสัญญาณ VIP (Futures)
                    "TOPIC_CHAT_ID": os.getenv("TOPIC_CHAT_ID"),  # ห้องพูดคุย Community
                    "TOPIC_MEMBER_ID": os.getenv(
                        "TOPIC_MEMBER_ID"
                    ),  # ห้องสมัครสมาชิก/ชำระเงิน
                    # Membership Settings
                    "VIP_PRICE": 490,
                    "VIP_DURATION_DAYS": 30,
                }
            )
            # ================================================================
            # 🧪 LAYER 3: Legacy & Optional Configs (Disabled or Optional)
            # ================================================================
            self._config.update(
                {
                    "LINE_CHANNEL_ACCESS_TOKEN": os.getenv(
                        "LINE_CHANNEL_ACCESS_TOKEN", ""
                    ),
                    "LINE_CHANNEL_SECRET": os.getenv("LINE_CHANNEL_SECRET", ""),
                    "LINE_USER_ID": os.getenv("LINE_USER_ID", ""),
                    "GOOGLE_SHEETS_ID": os.getenv("GOOGLE_SHEETS_ID", ""),
                    "GOOGLE_APPLICATION_CREDENTIALS": os.getenv(
                        "GOOGLE_APPLICATION_CREDENTIALS",
                        os.getenv("GOOGLE_CREDENTIALS_PATH", "/app/credentials.json"),
),
                }
            )
            self._validate_config()
            logging.info("✅ ConfigManager: Configuration loaded and layers organized")
        except Exception as e:
            logging.error(f"❌ ConfigManager: Configuration error: {e}")
            raise
    # ================================================================
    # 🛠️ LAYER 4: Accessor Methods (ฟังก์ชันดึงข้อมูล)
    # ================================================================
    def get(self, key: str, default: Any = None) -> Any:
        """ดึงค่าคอนฟิกรายตัว"""
        return self._config.get(key, default)
    def get_all(self) -> Dict[str, Any]:
        """ดึงค่าคอนฟิกทั้งหมด"""
        return self._config.copy()
    def get_telegram_config(self) -> Dict[str, Any]:
        """ดึงค่าเฉพาะส่วน Telegram และ Topics"""
        return {
            "token": self._config["TELEGRAM_BOT_TOKEN"],
            "chat_id": self._config["TELEGRAM_CHAT_ID"],
            "topics": {
                "normal": self._config["TOPIC_NORMAL_ID"],
                "vip": self._config["TOPIC_VIP_ID"],
                "chat": self._config["TOPIC_CHAT_ID"],
                "member": self._config["TOPIC_MEMBER_ID"],
            },
        }
    def get_binance_config(self) -> Dict[str, Any]:
        """ดึงค่า Binance API"""
        return {
            "base_url": self._config["BINANCE_BASE_URL"],
            "timeout": 30,
            "rate_limit": 1200,
        }
    def get_line_config(self) -> Dict[str, Any]:
        """ดึงค่า LINE (optional)"""
        return {
            "channel_access_token": self._config.get("LINE_CHANNEL_ACCESS_TOKEN", ""),
            "channel_secret": self._config.get("LINE_CHANNEL_SECRET", ""),
            "user_id": self._config.get("LINE_USER_ID", ""),
        }
    def get_google_config(self) -> Dict[str, Any]:
        """ดึงค่า Google Sheets (optional)"""
        import os
        # _config อาจเก็บเฉพาะ required env → optional อย่าง GOOGLE_SHEETS_ID อาจหาย
        sheets_id = (self._config.get("GOOGLE_SHEETS_ID") or os.getenv("GOOGLE_SHEETS_ID") or "").strip()
        # ใช้ GOOGLE_APPLICATION_CREDENTIALS เป็นหลัก + fallback key ที่คุณมีใน .env
        credentials_path = (
            self._config.get("GOOGLE_APPLICATION_CREDENTIALS")
            or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            or os.getenv("GOOGLE_CREDENTIALS_PATH")
            or os.getenv("GOOGLE_SHEET_SERVICE_ACCOUNT")
            or "/app/credentials.json"
        )
        return {
            "sheets_id": sheets_id,
            "credentials_path": credentials_path,
        }
    # ================================================================
    # 🛡️ LAYER 5: Validation & Helpers
    # ================================================================
    def _validate_config(self):
        """ตรวจสอบความถูกต้องของค่าที่รับมา"""
        # ตรวจสอบ Port
        port = self._config.get("PORT")
        if not (1024 <= port <= 65535):
            self._config["PORT"] = 8080
            logging.warning(f"⚠️ Invalid port: {port}. Defaulting to 8080")
        # ตรวจสอบความยาว Token เบื้องต้น
        if len(self._config["TELEGRAM_BOT_TOKEN"]) < 20:
            logging.error("❌ Invalid Telegram Bot Token")
    def is_debug_mode(self) -> bool:
        return self._config.get("DEBUG", False)

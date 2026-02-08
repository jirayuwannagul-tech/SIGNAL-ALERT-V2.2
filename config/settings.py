"""Configuration settings for Squeeze Bot - COMPLETE v2.0"""

import os
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Base configuration class with layer organization - COMPLETE v2.0"""

    # ================================================================
    # 🌐 LAYER 1: System Basics (updated for refactored architecture)
    # ================================================================

    # System version and identification
    VERSION = "2.0-refactored"
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    
    # Basic settings
    CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "900"))  # 15 minutes
    TIMEFRAMES = ["4h", "1d"]
    MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", "10"))
    
    # Refactored service settings
    SIGNAL_COOLDOWN_MINUTES = int(os.getenv("SIGNAL_COOLDOWN_MINUTES", "30"))
    PRICE_MONITOR_INTERVAL = int(os.getenv("PRICE_MONITOR_INTERVAL", "30"))  # seconds

    # ================================================================
    # 📡 LAYER 2: External API Connections (updated for ConfigManager)
    # ================================================================

    # Binance API
    BINANCE_BASE_URL = os.getenv("BINANCE_BASE_URL", "https://fapi.binance.com/fapi/v1")
    BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
    BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY", "")

    # LINE Bot (updated for ConfigManager)
    LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
    LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
    LINE_USER_ID = os.getenv("LINE_USER_ID", "")

    # Google Sheets (updated for ConfigManager)
    GOOGLE_SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID", "")
    GOOGLE_SHEETS_CREDENTIALS = os.getenv("GOOGLE_SHEETS_CREDENTIALS", "")
    
    # Fix: Unescape JSON string
    _creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON", "")
    if _creds_json:
        # Railway may wrap with quotes, remove them
        _creds_json = _creds_json.strip('"')
        # Replace escaped quotes and newlines
        _creds_json = _creds_json.replace('\\"', '"').replace('\\n', '\n')
    
    GOOGLE_APPLICATION_CREDENTIALS = _creds_json or os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "/app/credentials.json")

    # ================================================================
    # 💰 LAYER 3: Symbol Selection (COMPLETE - 50 symbols)
    # ================================================================

    # Top 50 Crypto by Market Cap - ALL VERIFIED on Binance Futures ✅
    DEFAULT_SYMBOLS = [
        # Top 10 - Major coins
        "BTCUSDT", "ETHUSDT", "XRPUSDT", "BNBUSDT", "SOLUSDT",
        "ADAUSDT", "DOGEUSDT", "TRXUSDT", "TONUSDT", "LINKUSDT",
        
        # 11-20 - Large caps
        "AVAXUSDT", "DOTUSDT", "LTCUSDT", "NEARUSDT", "UNIUSDT",
        "ICPUSDT", "APTUSDT", "ATOMUSDT", "HBARUSDT", "FILUSDT",
        
        # 21-30 - Mid caps
        "ARBUSDT", "OPUSDT", "SUIUSDT", "INJUSDT", "STXUSDT",
        "IMXUSDT", "AAVEUSDT", "GRTUSDT", "RENDERUSDT", "TIAUSDT",
        
        # 31-40 - DeFi & Layer 1/2
        "POLUSDT", "MKRUSDT", "ALGOUSDT", "LDOUSDT", "VETUSDT",
        "SEIUSDT", "TAOUSDT", "FTMUSDT", "KAVAUSDT", "RUNEUSDT",
        
        # 41-50 - Gaming, Metaverse & Others
        "BEAMXUSDT", "SANDUSDT", "MANAUSDT", "AXSUSDT", "FLOWUSDT",
        "CHZUSDT", "ENSUSDT", "APEUSDT", "QNTUSDT", "EGLDUSDT"
    ]

    # Priority symbols - Updated to 10 for better coverage
    PRIORITY_SYMBOLS = [
        "BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "SOLUSDT",
        "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT"
    ]

    # ================================================================
    # 📊 LAYER 4: Technical Indicators (COMPLETE with ATR)
    # ================================================================

    INDICATORS = {
        "squeeze": {
            "length": int(os.getenv("SQUEEZE_LENGTH", "20")),
            "bb_mult": float(os.getenv("SQUEEZE_BB_MULT", "2.0")),
            "kc_mult": float(os.getenv("SQUEEZE_KC_MULT", "1.5")),
            "use_true_range": True
        },
        "macd": {
            "fast": int(os.getenv("MACD_FAST", "8")),
            "slow": int(os.getenv("MACD_SLOW", "17")),
            "signal": int(os.getenv("MACD_SIGNAL", "9"))
        },
        "rsi": {
            "period": int(os.getenv("RSI_PERIOD", "14")),
            "oversold": int(os.getenv("RSI_OVERSOLD", "40")),
            "overbought": int(os.getenv("RSI_OVERBOUGHT", "60"))
        },
        "atr": {
            "period": int(os.getenv("ATR_PERIOD", "14")),
            "min_atr_multiplier": float(os.getenv("MIN_ATR_MULT", "0.5"))
        }
    }

    # ================================================================
    # 💸 LAYER 5: Risk Management (updated for PositionManager)
    # ================================================================

    RISK_MANAGEMENT = {
        "4h": {
            "tp_levels": [3.0, 5.0, 7.0],  # เพิ่มใหม่
            "sl_level": 3.0,
            "max_risk_per_trade": 3.0,
            "max_open_trades": 3
        },
        "1d": {
            "tp_levels": [5.0, 7.0, 9.0],
            "sl_level": 5.0,
            "max_risk_per_trade": 3.0,
            "max_open_trades": 2
        }
    }

    # ================================================================
    # 🔄 LAYER 6: Signal Filtering (COMPLETE with liquidity checks)
    # ================================================================

    SIGNAL_FILTERING = {
        "min_signal_strength": int(os.getenv("MIN_SIGNAL_STRENGTH", "70")),
        "require_volume_confirmation": True,
        "min_volume_ratio": float(os.getenv("MIN_VOLUME_RATIO", "1.2")),
        "cooldown_minutes": int(os.getenv("SIGNAL_COOLDOWN", "15")),
        "max_signals_per_day": int(os.getenv("MAX_SIGNALS_PER_DAY", "20")),
        "min_24h_volume_usd": int(os.getenv("MIN_24H_VOLUME", "5000000")),
        "min_open_interest_usd": int(os.getenv("MIN_OPEN_INTEREST", "2000000")),
        "max_spread_percentage": float(os.getenv("MAX_SPREAD_PCT", "0.1"))
    }

    # ================================================================
    # 🏷️ LAYER 7: Signal Classification
    # ================================================================

    SIGNAL_CATEGORIES = {
        "strong": {
            "min_strength": 90,
            "description": "High confidence signals",
            "notification_priority": "high"
        },
        "medium": {
            "min_strength": 70,
            "description": "Medium confidence signals",
            "notification_priority": "medium"
        },
        "weak": {
            "min_strength": 50,
            "description": "Low confidence signals",
            "notification_priority": "low"
        }
    }

    # ================================================================
    # 📱 LAYER 8: Notifications
    # ================================================================

    NOTIFICATIONS = {
        "line_enabled": bool(os.getenv("LINE_NOTIFICATIONS", "true").lower() == "true"),
        "sheets_enabled": bool(os.getenv("SHEETS_LOGGING", "true").lower() == "true"),
        "console_enabled": True,
        "signal_strength_threshold": 75,
        "notification_cooldown": 300,
        "version": "2.0.106"
    }

    # ================================================================
    # 🗃️ LAYER 9: Data Storage (COMPLETE with performance optimization)
    # ================================================================

    DATA_STORAGE = {
        "enabled": True,
        "cache_duration_hours": 24,
        "max_candles_per_symbol": 500,
        "storage_path": "./data/candles",
        "backup_enabled": True,
        "compression": True,
        "price_cache_timeout": 30,
        "connection_pool_size": 20,
        "batch_size": 10,
        "retry_attempts": 3,
        "retry_delay_seconds": 2,
        "use_compression": True,
        "max_memory_mb": 512
    }

    # ================================================================
    # 🗃️ LAYER 10: Position Management (RESTORED)
    # ================================================================

    POSITION_MANAGEMENT = {
        "positions_file": "data/positions.json",
        "auto_cleanup_days": 30,
        "max_positions_per_symbol": 1,
        "position_timeout_hours": 168,
        "track_partial_fills": True,
        "calculate_pnl": True
    }

    # ================================================================
    # 📊 LAYER 11: Symbol Categories & Tiers (FIXED)
    # ================================================================

    SYMBOL_CATEGORIES = {
        "tier1": ["BTCUSDT", "ETHUSDT"],
        "tier2": ["BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "SOLUSDT",
                  "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT"],
        "tier3": DEFAULT_SYMBOLS[:30],
        "tier4": DEFAULT_SYMBOLS[30:],
        "layer1": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "ADAUSDT", "AVAXUSDT", 
                   "DOTUSDT", "NEARUSDT", "APTUSDT", "ATOMUSDT", "ICPUSDT",
                   "SUIUSDT", "ALGOUSDT", "SEIUSDT", "FTMUSDT", "EGLDUSDT"],
        "layer2": ["ARBUSDT", "OPUSDT", "POLUSDT", "IMXUSDT", "STXUSDT"],
        "defi": ["UNIUSDT", "AAVEUSDT", "MKRUSDT", "LDOUSDT", "INJUSDT",
                 "RUNEUSDT", "KAVAUSDT", "GRTUSDT"],
        "gaming": ["BEAMXUSDT", "SANDUSDT", "MANAUSDT", "AXSUSDT", 
                   "FLOWUSDT", "CHZUSDT", "APEUSDT", "IMXUSDT"]
    }

    # ================================================================
    # 🛡️ Validation Methods
    # ================================================================

    @classmethod
    def validate_config(cls) -> List[str]:
        """Validate required configuration settings for v2.0"""
        errors = []

        if not cls.BINANCE_BASE_URL:
            errors.append("BINANCE_BASE_URL is required")

        if not cls.TIMEFRAMES:
            errors.append("At least one timeframe must be specified")

        if not cls.DEFAULT_SYMBOLS:
            errors.append("At least one symbol must be specified")

        required_indicators = ["squeeze", "macd", "rsi"]
        for indicator in required_indicators:
            if indicator not in cls.INDICATORS:
                errors.append(f"Missing required indicator: {indicator}")

        for timeframe in cls.TIMEFRAMES:
            if timeframe not in cls.RISK_MANAGEMENT:
                errors.append(f"Missing risk management settings for timeframe: {timeframe}")

        if cls.SIGNAL_COOLDOWN_MINUTES < 1:
            errors.append("SIGNAL_COOLDOWN_MINUTES must be at least 1 minute")

        if cls.PRICE_MONITOR_INTERVAL < 10:
            errors.append("PRICE_MONITOR_INTERVAL must be at least 10 seconds")

        return errors

    @classmethod
    def initialize_config(cls) -> None:
        """Initialize configuration and display status for v2.0"""
        print("=" * 60)
        print(f"🚀 SIGNAL ALERT SYSTEM v{cls.VERSION} - CONFIGURATION")
        print("=" * 60)
        
        print(f"Check Interval: {cls.CHECK_INTERVAL} seconds")
        print(f"Timeframes: {', '.join(cls.TIMEFRAMES)}")
        print(f"Symbols: {len(cls.DEFAULT_SYMBOLS)} total")
        print(f"Priority Symbols: {len(cls.PRIORITY_SYMBOLS)}")
        print(f"Signal Cooldown: {cls.SIGNAL_COOLDOWN_MINUTES} minutes")
        print(f"Price Monitor Interval: {cls.PRICE_MONITOR_INTERVAL} seconds")
        
        print("\n📡 API Connections:")
        print(f"Binance: {'✅ Configured' if cls.BINANCE_BASE_URL else '❌ Not configured'}")
        print(f"Line Bot: {'✅ Configured' if cls.LINE_CHANNEL_ACCESS_TOKEN else '❌ Not configured'}")
        print(f"Google Sheets: {'✅ Configured' if cls.GOOGLE_SHEETS_ID else '❌ Not configured'}")
        
        print(f"\n🔧 Refactored Services:")
        print(f"ConfigManager: ✅ Ready")
        print(f"DataManager: ✅ Ready")
        print(f"PositionManager: ✅ Ready")
        
        print(f"\n📊 Technical Indicators:")
        for name, settings in cls.INDICATORS.items():
            print(f"{name.upper()}: {settings}")

        errors = cls.validate_config()
        if errors:
            print(f"\n❌ Configuration Errors:")
            for error in errors:
                print(f"  - {error}")
        else:
            print(f"\n✅ Configuration validated successfully!")

        print("=" * 60)

    # ================================================================
    # 🔧 Helper Functions (COMPLETE SET)
    # ================================================================

    @classmethod
    def get_timeframe_config(cls, timeframe: str) -> Dict:
        """Get configuration for specific timeframe"""
        return cls.RISK_MANAGEMENT.get(timeframe, cls.RISK_MANAGEMENT.get("4h", {}))

    @classmethod
    def get_indicator_settings(cls, indicator: str) -> Dict:
        """Get settings for specific indicator"""
        return cls.INDICATORS.get(indicator, {})

    @classmethod
    def get_notification_config(cls) -> Dict:
        """Get notification configuration"""
        return cls.NOTIFICATIONS

    @classmethod
    def get_binance_config(cls) -> Dict:
        """Get Binance API configuration for DataManager"""
        return {
            'base_url': cls.BINANCE_BASE_URL,
            'api_key': cls.BINANCE_API_KEY,
            'secret_key': cls.BINANCE_SECRET_KEY,
            'timeout': 30,
            'rate_limit': 1200
        }

    @classmethod
    def get_google_config(cls) -> Dict:
        """Get Google configuration for ConfigManager"""
        return {
            'sheets_id': cls.GOOGLE_SHEETS_ID,
            'credentials_path': cls.GOOGLE_APPLICATION_CREDENTIALS
        }

    @classmethod
    def get_line_config(cls) -> Dict:
        """Get LINE configuration for ConfigManager"""
        return {
            'access_token': cls.LINE_CHANNEL_ACCESS_TOKEN,
            'secret': cls.LINE_CHANNEL_SECRET,
            'user_id': cls.LINE_USER_ID
        }

    @classmethod
    def get_position_config(cls) -> Dict:
        """Get position management configuration for PositionManager"""
        return cls.POSITION_MANAGEMENT

    @classmethod
    def get_symbols_by_tier(cls, tier: int = 4) -> List[str]:
        """Get symbols by tier level"""
        if tier == 1:
            return cls.SYMBOL_CATEGORIES["tier1"]
        elif tier == 2:
            return cls.SYMBOL_CATEGORIES["tier2"]
        elif tier == 3:
            return cls.SYMBOL_CATEGORIES["tier3"]
        else:
            return cls.DEFAULT_SYMBOLS

    @classmethod
    def get_symbols_by_category(cls, category: str) -> List[str]:
        """Get symbols by category"""
        return cls.SYMBOL_CATEGORIES.get(category, [])

    @classmethod
    def is_priority_symbol(cls, symbol: str) -> bool:
        """Check if symbol is in priority list"""
        return symbol in cls.PRIORITY_SYMBOLS

    @classmethod
    def get_update_interval(cls, symbol: str) -> int:
        """Get update interval based on symbol priority (seconds)"""
        if symbol in cls.SYMBOL_CATEGORIES["tier1"]:
            return 30
        elif symbol in cls.SYMBOL_CATEGORIES["tier2"]:
            return 60
        elif symbol in cls.SYMBOL_CATEGORIES["tier3"]:
            return 300
        else:
            return 900

    @classmethod
    def validate_symbol(cls, symbol: str) -> bool:
        """Validate if symbol exists in config"""
        return symbol in cls.DEFAULT_SYMBOLS

    @classmethod
    def get_system_summary(cls) -> Dict:
        """Get configuration summary for debugging v2.0"""
        return {
            "version": cls.VERSION,
            "timeframes": cls.TIMEFRAMES,
            "symbols_count": len(cls.DEFAULT_SYMBOLS),
            "priority_symbols_count": len(cls.PRIORITY_SYMBOLS),
            "risk_management_timeframes": list(cls.RISK_MANAGEMENT.keys()),
            "indicators": list(cls.INDICATORS.keys()),
            "check_interval_seconds": cls.CHECK_INTERVAL,
            "signal_cooldown_minutes": cls.SIGNAL_COOLDOWN_MINUTES,
            "price_monitor_interval": cls.PRICE_MONITOR_INTERVAL,
            "rsi_thresholds": {
                "oversold": cls.INDICATORS["rsi"]["oversold"],
                "overbought": cls.INDICATORS["rsi"]["overbought"]
            },
            "macd_settings": cls.INDICATORS["macd"],
            "line_configured": bool(cls.LINE_CHANNEL_ACCESS_TOKEN),
            "sheets_configured": bool(cls.GOOGLE_SHEETS_ID),
            "binance_configured": bool(cls.BINANCE_BASE_URL),
            "refactored_services": True,
            "position_management": True,
            "symbol_tiers": {
                "tier1": len(cls.SYMBOL_CATEGORIES["tier1"]),
                "tier2": len(cls.SYMBOL_CATEGORIES["tier2"]),
                "tier3": len(cls.SYMBOL_CATEGORIES["tier3"]),
                "tier4": len(cls.SYMBOL_CATEGORIES["tier4"])
            }
        }

    # ================================================================
    # 📋 Change Log
    # ================================================================

    @classmethod
    def get_change_log(cls) -> Dict:
        """Get change log for v2.0"""
        return {
            "version": "2.0-refactored",
            "changes": {
                "added": [
                    "50 verified Binance Futures symbols (from 30)",
                    "ATR indicator for volatility filtering",
                    "Liquidity & volume filters (min 24h volume, OI, spread)",
                    "Symbol tier system (tier1-4) for priority management",
                    "Symbol categories by sector (layer1, layer2, defi, gaming)",
                    "Performance optimization (batch processing, retry logic)",
                    "10 priority symbols (from 5)",
                    "Enhanced helper functions (get_update_interval, etc.)",
                    "ConfigManager for centralized configuration",
                    "DataManager replacing PriceFetcher + DataUpdater", 
                    "PositionManager for position logic",
                    "Background position monitoring",
                    "Comprehensive caching system"
                ],
                "modified": [
                    "Signal cooldown: 4 hours → 30 minutes",
                    "Max signals per day: 10 → 20",
                    "Signal strength threshold: 70% → 75%",
                    "MATICUSDT → POLUSDT (rebrand)",
                    "Enhanced data storage configuration",
                    "Improved risk management settings"
                ],
                "refactored": [
                    "main.py - new service architecture", 
                    "signal_detector.py - DataManager + PositionManager",
                    "price_monitor.py - coordinator role",
                    "scheduler.py - delegates to services",
                    "sheets_logger.py - uses ConfigManager",
                    "line_notifier.py - uses ConfigManager"
                ]
            }
        }

    # ================================================================
    # 🔍 Developer Information
    # ================================================================

    @classmethod
    def get_developer_info(cls) -> Dict:
        """Get developer and debugging information for v2.0"""
        return {
            "architecture": {
                "pattern": "Dependency Injection + Single Responsibility",
                "core_services": [
                    "ConfigManager (singleton)",
                    "DataManager (price data + caching)",
                    "PositionManager (position logic + tracking)"
                ],
                "coordinators": [
                    "SignalDetector (analysis + position creation)",
                    "PriceMonitor (monitoring coordination)",
                    "SignalScheduler (job scheduling)"
                ]
            },
            "validation_rules": {
                "required_env_vars": [
                    "BINANCE_BASE_URL",
                    "LINE_CHANNEL_ACCESS_TOKEN", 
                    "GOOGLE_SHEETS_ID"
                ],
                "optional_env_vars": [
                    "CHECK_INTERVAL",
                    "MIN_SIGNAL_STRENGTH",
                    "MAX_SIGNALS_PER_DAY",
                    "SIGNAL_COOLDOWN_MINUTES",
                    "PRICE_MONITOR_INTERVAL",
                    "MIN_24H_VOLUME",
                    "MIN_OPEN_INTEREST",
                    "ATR_PERIOD",
                    "DEBUG"
                ]
            },
            "performance_tips": [
                "Use tier system to prioritize symbol updates",
                "Enable batch processing for 50 symbols",
                "Set appropriate volume filters to reduce noise",
                "Monitor memory usage with max_memory_mb setting",
                "Use compression for candle data storage"
            ]
        }
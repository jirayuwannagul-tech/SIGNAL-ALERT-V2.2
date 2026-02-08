"""
Data Collection Configuration
กำหนด config สำหรับการดึงและเก็บข้อมูล candle data
"""

import os
from datetime import datetime, timedelta

class DataConfig:
    # =============================================================================
    # 📊 DATA STORAGE SETTINGS
    # =============================================================================
    
    # Directory paths
    BASE_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
    CANDLES_DIR = os.path.join(BASE_DATA_DIR, 'candles')
    
    # File naming pattern: BTCUSDT_1h_2024-01.json
    FILE_NAME_PATTERN = "{symbol}_{timeframe}_{year}-{month:02d}.json"
    
    # =============================================================================
    # 🕐 TIME SETTINGS
    # =============================================================================
    
    # Default timeframes to collect
    TIMEFRAMES = ['15m', '1h', '4h', '1d']
    
    # Historical data collection periods
    HISTORICAL_PERIODS = {
        '15m': 7,      # 7 days
        '1h': 30,      # 30 days  
        '4h': 90,      # 90 days
        '1d': 365      # 1 year
    }
    
    # How many candles to keep in memory for analysis
    ANALYSIS_CANDLES = {
        '15m': 300,    # 5 hours
        '1h': 300,     # 12.5 days
        '4h': 300,     # 50 days
        '1d': 300      # 10 months
    }
    
    # Update intervals (seconds)
    UPDATE_INTERVALS = {
        '15m': 60,     # Update every 1 minute
        '1h': 300,     # Update every 5 minutes
        '4h': 900,     # Update every 15 minutes
        '1d': 3600     # Update every 1 hour
    }
    
    # =============================================================================
    # 📈 SYMBOL SETTINGS
    # =============================================================================
    
    # Priority symbols (collect first)
    PRIORITY_SYMBOLS = [
        'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'DOTUSDT',
        'LINKUSDT', 'LTCUSDT', 'XRPUSDT', 'SOLUSDT', 'AVAXUSDT'
    ]
    
    # All symbols to monitor
    DEFAULT_SYMBOLS = [
        # Major pairs
        'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'DOTUSDT',
        'LINKUSDT', 'LTCUSDT', 'XRPUSDT', 'SOLUSDT', 'AVAXUSDT',
        
        # DeFi tokens
        'UNIUSDT', 'AAVEUSDT', 'COMPUSDT', 'MKRUSDT', 'SUSHIUSDT',
        
        # Layer 1
        'NEARUSDT', 'ATOMUSDT', 'ALGOUSDT', 'EGLDUSDT', 'FTMUSDT',
        
        # Meme coins
        'DOGEUSDT', 'SHIBUSDT', 'PEPEUSDT', 'FLOKIUSDT',
        
        # Gaming/NFT
        'AXSUSDT', 'SANDUSDT', 'MANAUSDT', 'ENJUSDT',
        
        # Others
        'POLUSDT', 'VETUSDT', 'ICPUSDT', 'FILUSDT', 'APTUSDT',
        'OPUSDT', 'ARBUSDT', 'SUIUSDT', 'INJUSDT', 'STXUSDT',
        'THETAUSDT', 'IOTAUSDT', 'XLMUSDT', 'TRXUSDT', 'HBARUSDT',
        'GALAUSDT', 'GMTUSDT', 'CHZUSDT', 'FLOWUSDT', 'APTUSDT'
    ]
    
    # =============================================================================
    # 🔧 BINANCE API SETTINGS
    # =============================================================================
    
    # Binance API endpoints
    BINANCE_BASE_URL = "https://api.binance.com"
    KLINES_ENDPOINT = "/api/v3/klines"
    
    # Request limits
    MAX_CANDLES_PER_REQUEST = 1000  # Binance limit
    REQUEST_DELAY = 0.1  # Delay between requests (seconds)
    
    # Retry settings
    MAX_RETRIES = 3
    RETRY_DELAY = 1  # seconds
    
    # =============================================================================
    # 💾 STORAGE SETTINGS
    # =============================================================================
    
    # File compression
    COMPRESS_FILES = True
    
    # Backup settings
    BACKUP_ENABLED = True
    BACKUP_RETENTION_DAYS = 30
    
    # Memory management
    MAX_MEMORY_CANDLES = 10000  # Max candles in memory per symbol
    
    # =============================================================================
    # 📊 DATA VALIDATION
    # =============================================================================
    
    # Required fields in candle data
    REQUIRED_FIELDS = [
        'open_time', 'open', 'high', 'low', 'close',
        'volume', 'close_time', 'quote_volume', 'count'
    ]
    
    # Data quality checks
    VALIDATE_OHLC = True  # Check if OHLC data is valid
    VALIDATE_VOLUME = True  # Check if volume > 0
    VALIDATE_TIME_SEQUENCE = True  # Check if timestamps are sequential
    
    # =============================================================================
    # 🚨 ERROR HANDLING
    # =============================================================================
    
    # Logging
    LOG_LEVEL = 'INFO'
    LOG_FILE = os.path.join(BASE_DATA_DIR, 'logs', 'data_collector.log')
    
    # Error thresholds
    MAX_MISSING_CANDLES = 5  # Max missing candles before alert
    MAX_API_ERRORS = 10  # Max API errors before stopping
    
    @classmethod
    def get_file_path(cls, symbol: str, timeframe: str, date: datetime = None) -> str:
        """
        สร้าง file path สำหรับเก็บข้อมูล candle
        
        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            timeframe: Timeframe (e.g., '1h')
            date: Date for the file (default: current month)
        
        Returns:
            Full file path
        """
        if date is None:
            date = datetime.now()
            
        filename = cls.FILE_NAME_PATTERN.format(
            symbol=symbol,
            timeframe=timeframe,
            year=date.year,
            month=date.month
        )
        
        return os.path.join(cls.CANDLES_DIR, filename)
    
    @classmethod
    def get_historical_start_date(cls, timeframe: str) -> datetime:
        """
        คำนวณวันที่เริ่มต้นสำหรับดึงข้อมูล historical
        
        Args:
            timeframe: Timeframe
            
        Returns:
            Start date for historical data
        """
        days = cls.HISTORICAL_PERIODS.get(timeframe, 30)
        return datetime.now() - timedelta(days=days)
    
    @classmethod
    def ensure_directories(cls):
        """สร้าง directories ที่จำเป็น"""
        os.makedirs(cls.BASE_DATA_DIR, exist_ok=True)
        os.makedirs(cls.CANDLES_DIR, exist_ok=True)
        os.makedirs(os.path.join(cls.BASE_DATA_DIR, 'logs'), exist_ok=True)
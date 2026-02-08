"""
Data Updater Service
อัปเดตข้อมูล candle data แบบ real-time และจัดการ memory cache
"""

import json
import os
import time
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from threading import Thread, Lock
import requests

from config.data_config import DataConfig

logger = logging.getLogger(__name__)

class DataUpdater:
    """
    บริการสำหรับอัปเดตข้อมูล candle data แบบ real-time
    - อัปเดตข้อมูลใหม่จาก Binance API
    - จัดการ memory cache สำหรับการเข้าถึงที่เร็ว
    - เขียนข้อมูลลงไฟล์แบบ batch
    """
    
    def __init__(self):
        self.config = DataConfig
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Python/Trading-Bot-Updater'
        })
        
        # Memory cache: symbol -> timeframe -> candles
        self.cache = {}
        self.cache_lock = Lock()
        
        # Update tracking
        self.last_update = {}  # symbol_timeframe -> timestamp
        self.update_threads = {}  # timeframe -> thread
        self.running = False
        
        # สถิติ
        self.stats = {
            'total_updates': 0,
            'successful_updates': 0,
            'failed_updates': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }
        
        logger.info("DataUpdater initialized")
    
    def get_latest_candles(self, symbol: str, timeframe: str, limit: int = 100) -> List[Dict]:
        """
        ดึงข้อมูล candles ล่าสุดจาก API
        
        Args:
            symbol: Trading pair
            timeframe: Timeframe
            limit: Number of candles to fetch
            
        Returns:
            Latest candle data
        """
        url = f"{self.config.BINANCE_BASE_URL}{self.config.KLINES_ENDPOINT}"
        
        params = {
            'symbol': symbol,
            'interval': timeframe,
            'limit': limit
        }
        
        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            raw_data = response.json()
            
            # แปลงเป็นรูปแบบมาตรฐาน
            formatted_data = []
            for candle in raw_data:
                formatted_candle = {
                    'open_time': int(candle[0]),
                    'open': float(candle[1]),
                    'high': float(candle[2]),
                    'low': float(candle[3]),
                    'close': float(candle[4]),
                    'volume': float(candle[5]),
                    'close_time': int(candle[6]),
                    'quote_volume': float(candle[7]),
                    'count': int(candle[8]),
                    'taker_buy_volume': float(candle[9]),
                    'taker_buy_quote_volume': float(candle[10])
                }
                formatted_data.append(formatted_candle)
            
            return formatted_data
            
        except Exception as e:
            logger.error(f"Failed to get latest candles for {symbol} {timeframe}: {e}")
            return []
    
    def load_cache_from_files(self, symbol: str, timeframe: str) -> List[Dict]:
        """
        โหลดข้อมูลจากไฟล์เข้า cache
        
        Args:
            symbol: Trading pair  
            timeframe: Timeframe
            
        Returns:
            Loaded candle data
        """
        candles = []
        current_date = datetime.now()
        
        # โหลดข้อมูล 3 เดือนล่าสุด
        for i in range(3):
            target_date = current_date - timedelta(days=30 * i)
            file_path = self.config.get_file_path(symbol, timeframe, target_date)
            
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r') as f:
                        data = json.load(f)
                        file_candles = data.get('candles', [])
                        candles.extend(file_candles)
                        
                except Exception as e:
                    logger.error(f"Failed to load file {file_path}: {e}")
        
        # เรียงตาม timestamp และเก็บแค่จำนวนที่กำหนด
        candles.sort(key=lambda x: x['open_time'])
        max_candles = self.config.ANALYSIS_CANDLES.get(timeframe, 300)
        
        return candles[-max_candles:] if len(candles) > max_candles else candles
    
    def update_cache(self, symbol: str, timeframe: str, force_reload: bool = False):
        """
        อัปเดตข้อมูลใน cache
        
        Args:
            symbol: Trading pair
            timeframe: Timeframe  
            force_reload: Force reload from files
        """
        cache_key = f"{symbol}_{timeframe}"
        
        with self.cache_lock:
            # ตรวจสอบว่าต้อง update หรือไม่
            if not force_reload:
                last_update_time = self.last_update.get(cache_key, 0)
                update_interval = self.config.UPDATE_INTERVALS.get(timeframe, 300)
                
                if time.time() - last_update_time < update_interval:
                    return  # ยังไม่ถึงเวลา update
            
            try:
                # สร้าง cache structure ถ้าไม่มี
                if symbol not in self.cache:
                    self.cache[symbol] = {}
                
                # โหลดข้อมูลจากไฟล์ (ถ้าไม่มีใน cache)
                if timeframe not in self.cache[symbol] or force_reload:
                    self.cache[symbol][timeframe] = self.load_cache_from_files(symbol, timeframe)
                    self.stats['cache_misses'] += 1
                else:
                    self.stats['cache_hits'] += 1
                
                # ดึงข้อมูลล่าสุดจาก API
                latest_candles = self.get_latest_candles(symbol, timeframe, limit=50)
                
                if latest_candles:
                    # อัปเดต cache ด้วยข้อมูลใหม่
                    existing_candles = self.cache[symbol][timeframe]
                    updated_candles = self.merge_candles(existing_candles, latest_candles)
                    
                    # เก็บแค่จำนวนที่กำหนด
                    max_candles = self.config.ANALYSIS_CANDLES.get(timeframe, 300)
                    self.cache[symbol][timeframe] = updated_candles[-max_candles:]
                    
                    # อัปเดต timestamp
                    self.last_update[cache_key] = time.time()
                    self.stats['successful_updates'] += 1
                    
                    logger.debug(f"Updated cache for {symbol} {timeframe}: {len(self.cache[symbol][timeframe])} candles")
                    
                else:
                    self.stats['failed_updates'] += 1
                    
                self.stats['total_updates'] += 1
                    
            except Exception as e:
                logger.error(f"Failed to update cache for {symbol} {timeframe}: {e}")
                self.stats['failed_updates'] += 1
    
    def merge_candles(self, existing: List[Dict], new: List[Dict]) -> List[Dict]:
        """
        รวมข้อมูล candles เก่าและใหม่
        
        Args:
            existing: Existing candle data
            new: New candle data
            
        Returns:
            Merged candle data
        """
        if not existing:
            return new
            
        if not new:
            return existing
        
        # สร้าง dict สำหรับ lookup ที่เร็ว
        existing_dict = {candle['open_time']: candle for candle in existing}
        
        # อัปเดตหรือเพิ่มข้อมูลใหม่
        for candle in new:
            existing_dict[candle['open_time']] = candle
        
        # แปลงกลับเป็น list และเรียง
        merged = list(existing_dict.values())
        merged.sort(key=lambda x: x['open_time'])
        
        return merged
    
    def get_candles(self, symbol: str, timeframe: str, limit: int = None) -> List[Dict]:
        """
        ดึงข้อมูล candles จาก cache
        
        Args:
            symbol: Trading pair
            timeframe: Timeframe
            limit: Number of candles to return (default: all)
            
        Returns:
            Candle data from cache
        """
        # อัปเดต cache ก่อน
        self.update_cache(symbol, timeframe)
        
        with self.cache_lock:
            try:
                candles = self.cache[symbol][timeframe]
                
                if limit:
                    return candles[-limit:]
                return candles
                
            except KeyError:
                logger.warning(f"No cache data for {symbol} {timeframe}")
                return []
    
    def get_latest_candle(self, symbol: str, timeframe: str) -> Optional[Dict]:
        """
        ดึง candle ล่าสุด
        
        Args:
            symbol: Trading pair
            timeframe: Timeframe
            
        Returns:
            Latest candle or None
        """
        candles = self.get_candles(symbol, timeframe, limit=1)
        return candles[0] if candles else None
    
    def save_cache_to_files(self):
        """บันทึกข้อมูลจาก cache ลงไฟล์"""
        logger.info("Saving cache to files...")
        saved_count = 0
        
        with self.cache_lock:
            for symbol in self.cache:
                for timeframe in self.cache[symbol]:
                    try:
                        candles = self.cache[symbol][timeframe]
                        
                        if not candles:
                            continue
                        
                        # แยกข้อมูลตาม month
                        monthly_data = {}
                        
                        for candle in candles:
                            candle_date = datetime.fromtimestamp(candle['open_time'] / 1000)
                            month_key = f"{candle_date.year}-{candle_date.month:02d}"
                            
                            if month_key not in monthly_data:
                                monthly_data[month_key] = []
                            monthly_data[month_key].append(candle)
                        
                        # บันทึกแต่ละเดือน
                        for month_key, month_candles in monthly_data.items():
                            year, month = month_key.split('-')
                            file_date = datetime(int(year), int(month), 1)
                            file_path = self.config.get_file_path(symbol, timeframe, file_date)
                            
                            # โหลดข้อมูลเดิม
                            existing_data = []
                            if os.path.exists(file_path):
                                try:
                                    with open(file_path, 'r') as f:
                                        data = json.load(f)
                                        existing_data = data.get('candles', [])
                                except:
                                    pass
                            
                            # รวมกับข้อมูลใหม่
                            merged_data = self.merge_candles(existing_data, month_candles)
                            
                            # บันทึกลงไฟล์
                            data = {
                                'symbol': symbol,
                                'timeframe': timeframe,
                                'updated_at': datetime.now().isoformat(),
                                'count': len(merged_data),
                                'candles': merged_data
                            }
                            
                            os.makedirs(os.path.dirname(file_path), exist_ok=True)
                            with open(file_path, 'w') as f:
                                json.dump(data, f, separators=(',', ':'))
                            
                            saved_count += 1
                            
                    except Exception as e:
                        logger.error(f"Failed to save cache for {symbol} {timeframe}: {e}")
        
        logger.info(f"Saved {saved_count} cache files")
    
    def start_auto_update(self, symbols: List[str] = None, timeframes: List[str] = None):
        """
        เริ่มระบบอัปเดตอัตโนมัติ
        
        Args:
            symbols: List of symbols to update
            timeframes: List of timeframes to update
        """
        if symbols is None:
            symbols = self.config.PRIORITY_SYMBOLS
        if timeframes is None:
            timeframes = self.config.TIMEFRAMES
        
        self.running = True
        logger.info(f"Starting auto update for {len(symbols)} symbols, {len(timeframes)} timeframes")
        
        # สร้าง thread สำหรับแต่ละ timeframe
        for timeframe in timeframes:
            thread = Thread(
                target=self._update_worker,
                args=(symbols, timeframe),
                daemon=True,
                name=f"UpdateWorker-{timeframe}"
            )
            thread.start()
            self.update_threads[timeframe] = thread
        
        # สร้าง thread สำหรับบันทึกไฟล์
        save_thread = Thread(
            target=self._save_worker,
            daemon=True,
            name="SaveWorker"
        )
        save_thread.start()
        
        logger.info("Auto update started")
    
    def _update_worker(self, symbols: List[str], timeframe: str):
        """Worker thread สำหรับอัปเดต timeframe หนึ่ง"""
        interval = self.config.UPDATE_INTERVALS.get(timeframe, 300)
        
        while self.running:
            try:
                for symbol in symbols:
                    if not self.running:
                        break
                    
                    self.update_cache(symbol, timeframe)
                    time.sleep(1)  # หน่วงเล็กน้อยระหว่าง symbol
                
                # รอจนถึงรอบต่อไป
                time.sleep(interval)
                
            except Exception as e:
                logger.error(f"Error in update worker {timeframe}: {e}")
                time.sleep(30)  # รอ 30 วินาทีแล้วลองใหม่
    
    def _save_worker(self):
        """Worker thread สำหรับบันทึกไฟล์"""
        while self.running:
            try:
                time.sleep(300)  # บันทึกทุก 5 นาที
                self.save_cache_to_files()
                
            except Exception as e:
                logger.error(f"Error in save worker: {e}")
                time.sleep(60)  # รอ 1 นาทีแล้วลองใหม่
    
    def stop_auto_update(self):
        """หยุดระบบอัปเดตอัตโนมัติ"""
        self.running = False
        logger.info("Stopping auto update...")
        
        # รอให้ threads หยุด
        for thread in self.update_threads.values():
            if thread.is_alive():
                thread.join(timeout=5)
        
        # บันทึกข้อมูลสุดท้าย
        self.save_cache_to_files()
        
        logger.info("Auto update stopped")
    
    def clear_cache(self, symbol: str = None, timeframe: str = None):
        """ล้าง cache"""
        with self.cache_lock:
            if symbol and timeframe:
                if symbol in self.cache and timeframe in self.cache[symbol]:
                    del self.cache[symbol][timeframe]
                    logger.info(f"Cleared cache for {symbol} {timeframe}")
            elif symbol:
                if symbol in self.cache:
                    del self.cache[symbol]
                    logger.info(f"Cleared cache for {symbol}")
            else:
                self.cache.clear()
                self.last_update.clear()
                logger.info("Cleared all cache")
    
    def get_cache_info(self) -> Dict:
        """ดึงข้อมูลเกี่ยวกับ cache"""
        with self.cache_lock:
            info = {
                'symbols': list(self.cache.keys()),
                'total_entries': 0,
                'memory_usage': {},
                'last_updates': {}
            }
            
            for symbol in self.cache:
                info['memory_usage'][symbol] = {}
                for timeframe in self.cache[symbol]:
                    candle_count = len(self.cache[symbol][timeframe])
                    info['total_entries'] += candle_count
                    info['memory_usage'][symbol][timeframe] = candle_count
                    
                    cache_key = f"{symbol}_{timeframe}"
                    if cache_key in self.last_update:
                        info['last_updates'][cache_key] = datetime.fromtimestamp(
                            self.last_update[cache_key]
                        ).isoformat()
            
            return info
    
    def get_stats(self) -> Dict:
        """ดึงสถิติการทำงาน"""
        cache_info = self.get_cache_info()
        
        return {
            **self.stats,
            'cache_info': cache_info,
            'running': self.running,
            'active_threads': len([t for t in self.update_threads.values() if t.is_alive()])
        }
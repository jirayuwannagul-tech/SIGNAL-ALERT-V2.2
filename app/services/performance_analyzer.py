"""
=============================================================================
📊 PERFORMANCE ANALYZER สำหรับ TRADING ANALYTICS
=============================================================================
ไฟล์นี้จัดการ:
1. วิเคราะห์ผลงานการเทรดจาก Google Sheets
2. คำนวณสถิติต่างๆ (Win Rate, PnL, Drawdown)
3. สร้างรายงานประสิทธิภาพ
4. วิเคราะห์ pattern และ performance ตาม timeframe/symbol
=============================================================================
"""

import logging
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import statistics

logger = logging.getLogger(__name__)


class PerformanceAnalyzer:
    """
    =======================================================================
    📈 PERFORMANCE ANALYZER CLASS - วิเคราะห์ผลงานการเทรด
    =======================================================================
    
    หน้าที่:
    - อ่านข้อมูลการเทรดจาก Google Sheets
    - คำนวณสถิติและ metrics ต่างๆ
    - สร้างรายงานประสิทธิภาพ
    - วิเคราะห์ patterns และ trends
    """

    def __init__(self, config: Dict, sheets_logger=None):
        """
        ===================================================================
        🚀 INITIALIZATION LAYER
        ===================================================================
        """
        self.config = config
        self.sheets_logger = sheets_logger
        
        # 📊 ข้อมูลที่อ่านจาก sheets
        self.trading_data = []
        self.signal_data = []
        
        # 🏆 Performance metrics
        self.performance_cache = {}
        self.last_analysis_time = None
        
        logger.info("PerformanceAnalyzer initialized")

    def load_trading_data(self, days: int = 30) -> bool:
        """
        ===================================================================
        📋 DATA LOADING LAYER - โหลดข้อมูลจาก Google Sheets
        ===================================================================
        
        Args:
            days: จำนวนวันย้อนหลังที่ต้องการวิเคราะห์
            
        Returns:
            True ถ้าโหลดสำเร็จ
        """
        if not self.sheets_logger or not self.sheets_logger._initialized:
            logger.error("SheetsLogger not available")
            return False
            
        try:
            # อ่านข้อมูลจาก Trading_Journal
            worksheet = self.sheets_logger.spreadsheet.worksheet("Trading_Journal")
            records = worksheet.get_all_records()
            
            # กรองข้อมูลตามวันที่
            cutoff_date = datetime.now() - timedelta(days=days)
            filtered_data = []
            
            for record in records:
                try:
                    # แปลงวันที่
                    date_str = record.get("Date", "")
                    if date_str:
                        trade_date = datetime.strptime(date_str, "%Y-%m-%d")
                        if trade_date >= cutoff_date:
                            # ทำความสะอาดข้อมูล
                            clean_record = self._clean_trading_record(record)
                            if clean_record:
                                filtered_data.append(clean_record)
                                
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid date in record: {record}, error: {e}")
                    continue
            
            self.trading_data = filtered_data
            logger.info(f"Loaded {len(self.trading_data)} trading records")
            
            # โหลดข้อมูล signals ด้วย
            self._load_signal_data(days)
            
            return True
            
        except Exception as e:
            logger.error(f"Error loading trading data: {e}")
            return False

    def _clean_trading_record(self, record: Dict) -> Optional[Dict]:
        """ทำความสะอาดข้อมูล trading record"""
        try:
            clean_record = {
                "date": record.get("Date", ""),
                "symbol": record.get("Symbol", ""),
                "direction": record.get("Signal", ""),
                "entry_price": float(record.get("Entry", 0)),
                "sl": float(record.get("SL", 0)),
                "tp1": float(record.get("TP1", 0)),
                "tp2": float(record.get("TP2", 0)),
                "tp3": float(record.get("TP3", 0)),
                "win_loss": record.get("Win/Loss", ""),
                "win_rate": record.get("Win Rate", "")
            }
            
            # ตรวจสอบข้อมูลจำเป็น
            if (clean_record["symbol"] and 
                clean_record["direction"] and 
                clean_record["entry_price"] > 0):
                return clean_record
                
            return None
            
        except (ValueError, TypeError) as e:
            logger.warning(f"Error cleaning record: {e}")
            return None

    def _load_signal_data(self, days: int):
        """โหลดข้อมูล signals จาก Signals worksheet"""
        try:
            worksheet = self.sheets_logger.spreadsheet.worksheet("Signals")
            records = worksheet.get_all_records()
            
            cutoff_date = datetime.now() - timedelta(days=days)
            self.signal_data = []
            
            for record in records:
                try:
                    timestamp_str = record.get("Timestamp", "")
                    if timestamp_str:
                        # แปลง ISO timestamp
                        signal_date = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        if signal_date.replace(tzinfo=None) >= cutoff_date:
                            self.signal_data.append(record)
                            
                except (ValueError, TypeError):
                    continue
                    
            logger.info(f"Loaded {len(self.signal_data)} signal records")
            
        except Exception as e:
            logger.warning(f"Could not load signal data: {e}")
            self.signal_data = []

    def calculate_basic_metrics(self) -> Dict:
        """
        ===================================================================
        📊 BASIC METRICS LAYER - คำนวณ metrics พื้นฐาน
        ===================================================================
        """
        if not self.trading_data:
            return {"error": "No trading data available"}
        
        try:
            total_trades = len(self.trading_data)
            closed_trades = [t for t in self.trading_data if t["win_loss"] in ["WIN", "LOSS"]]
            wins = [t for t in closed_trades if t["win_loss"] == "WIN"]
            losses = [t for t in closed_trades if t["win_loss"] == "LOSS"]
            
            metrics = {
                "total_trades": total_trades,
                "closed_trades": len(closed_trades),
                "open_trades": total_trades - len(closed_trades),
                "wins": len(wins),
                "losses": len(losses),
                "win_rate": round((len(wins) / max(len(closed_trades), 1)) * 100, 1),
                "loss_rate": round((len(losses) / max(len(closed_trades), 1)) * 100, 1)
            }
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error calculating basic metrics: {e}")
            return {"error": str(e)}

    def calculate_pnl_metrics(self) -> Dict:
        """
        ===================================================================
        💰 PNL METRICS LAYER - คำนวณกำไรขาดทุน
        ===================================================================
        """
        if not self.trading_data:
            return {"error": "No trading data available"}
            
        try:
            closed_trades = [t for t in self.trading_data if t["win_loss"] in ["WIN", "LOSS"]]
            
            if not closed_trades:
                return {"message": "No closed trades for PnL calculation"}
            
            pnl_data = []
            
            for trade in closed_trades:
                try:
                    # คำนวณ PnL โดยประมาณจากระยะห่างของ TP/SL
                    entry = trade["entry_price"]
                    sl = trade["sl"]
                    tp1 = trade["tp1"]
                    
                    if trade["win_loss"] == "WIN":
                        # สมมติว่าถึง TP1
                        if trade["direction"] == "LONG":
                            pnl_percent = ((tp1 - entry) / entry) * 100
                        else:  # SHORT
                            pnl_percent = ((entry - tp1) / entry) * 100
                    else:  # LOSS
                        # ถึง SL
                        if trade["direction"] == "LONG":
                            pnl_percent = ((sl - entry) / entry) * 100
                        else:  # SHORT
                            pnl_percent = ((entry - sl) / entry) * 100
                    
                    pnl_data.append(pnl_percent)
                    
                except (ValueError, ZeroDivisionError):
                    continue
            
            if not pnl_data:
                return {"message": "Could not calculate PnL data"}
            
            # คำนวณ metrics
            total_pnl = sum(pnl_data)
            avg_win = statistics.mean([p for p in pnl_data if p > 0]) if any(p > 0 for p in pnl_data) else 0
            avg_loss = statistics.mean([p for p in pnl_data if p < 0]) if any(p < 0 for p in pnl_data) else 0
            
            metrics = {
                "total_pnl_percent": round(total_pnl, 2),
                "average_pnl_percent": round(statistics.mean(pnl_data), 2),
                "median_pnl_percent": round(statistics.median(pnl_data), 2),
                "best_trade_percent": round(max(pnl_data), 2),
                "worst_trade_percent": round(min(pnl_data), 2),
                "average_win_percent": round(avg_win, 2),
                "average_loss_percent": round(avg_loss, 2),
                "profit_factor": round(abs(avg_win / avg_loss), 2) if avg_loss != 0 else 0,
                "total_trades_analyzed": len(pnl_data)
            }
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error calculating PnL metrics: {e}")
            return {"error": str(e)}

    def analyze_by_direction(self) -> Dict:
        """
        ===================================================================
        🧭 DIRECTION ANALYSIS LAYER - วิเคราะห์ตาม LONG/SHORT
        ===================================================================
        """
        if not self.trading_data:
            return {"error": "No trading data available"}
            
        try:
            directions = {}
            
            for direction in ["LONG", "SHORT"]:
                trades = [t for t in self.trading_data if t["direction"] == direction]
                closed_trades = [t for t in trades if t["win_loss"] in ["WIN", "LOSS"]]
                wins = len([t for t in closed_trades if t["win_loss"] == "WIN"])
                
                directions[direction.lower()] = {
                    "total_trades": len(trades),
                    "closed_trades": len(closed_trades),
                    "wins": wins,
                    "losses": len(closed_trades) - wins,
                    "win_rate": round((wins / max(len(closed_trades), 1)) * 100, 1)
                }
            
            return directions
            
        except Exception as e:
            logger.error(f"Error analyzing by direction: {e}")
            return {"error": str(e)}

    def analyze_by_symbol(self, top_n: int = 10) -> Dict:
        """
        ===================================================================
        🏷️ SYMBOL ANALYSIS LAYER - วิเคราะห์ตาม Symbol
        ===================================================================
        """
        if not self.trading_data:
            return {"error": "No trading data available"}
            
        try:
            symbols = {}
            
            # รวมข้อมูลตาม symbol
            for trade in self.trading_data:
                symbol = trade["symbol"]
                if symbol not in symbols:
                    symbols[symbol] = {
                        "total_trades": 0,
                        "closed_trades": 0,
                        "wins": 0,
                        "losses": 0,
                        "win_rate": 0
                    }
                
                symbols[symbol]["total_trades"] += 1
                
                if trade["win_loss"] in ["WIN", "LOSS"]:
                    symbols[symbol]["closed_trades"] += 1
                    if trade["win_loss"] == "WIN":
                        symbols[symbol]["wins"] += 1
                    else:
                        symbols[symbol]["losses"] += 1
            
            # คำนวณ win rate
            for symbol in symbols:
                closed = symbols[symbol]["closed_trades"]
                if closed > 0:
                    symbols[symbol]["win_rate"] = round(
                        (symbols[symbol]["wins"] / closed) * 100, 1
                    )
            
            # เรียงตาม total trades และเอาแค่ top N
            sorted_symbols = sorted(
                symbols.items(), 
                key=lambda x: x[1]["total_trades"], 
                reverse=True
            )[:top_n]
            
            return dict(sorted_symbols)
            
        except Exception as e:
            logger.error(f"Error analyzing by symbol: {e}")
            return {"error": str(e)}

    def analyze_signal_quality(self) -> Dict:
        """
        ===================================================================
        🎯 SIGNAL QUALITY LAYER - วิเคราะห์คุณภาพสัญญาณ
        ===================================================================
        """
        if not self.signal_data:
            return {"message": "No signal data available"}
            
        try:
            total_signals = len(self.signal_data)
            
            # นับตามประเภทสัญญาณ
            signal_types = {}
            timeframes = {}
            
            for signal in self.signal_data:
                # ประเภทสัญญาณ
                signal_type = signal.get("Signal", "UNKNOWN")
                signal_types[signal_type] = signal_types.get(signal_type, 0) + 1
                
                # Timeframe
                timeframe = signal.get("Timeframe", "UNKNOWN")
                timeframes[timeframe] = timeframes.get(timeframe, 0) + 1
            
            return {
                "total_signals": total_signals,
                "signal_types": signal_types,
                "timeframes": timeframes,
                "signals_per_day": round(total_signals / max(30, 1), 1)  # สมมติ 30 วัน
            }
            
        except Exception as e:
            logger.error(f"Error analyzing signal quality: {e}")
            return {"error": str(e)}

    def generate_performance_report(self, days: int = 30) -> Dict:
        """
        ===================================================================
        📋 REPORT GENERATION LAYER - สร้างรายงานประสิทธิภาพ
        ===================================================================
        """
        # โหลดข้อมูลใหม่
        if not self.load_trading_data(days):
            return {"error": "Could not load trading data"}
        
        try:
            report = {
                "report_date": datetime.now().isoformat(),
                "analysis_period_days": days,
                "basic_metrics": self.calculate_basic_metrics(),
                "pnl_metrics": self.calculate_pnl_metrics(),
                "direction_analysis": self.analyze_by_direction(),
                "symbol_analysis": self.analyze_by_symbol(top_n=10),
                "signal_analysis": self.analyze_signal_quality()
            }
            
            # Cache ผลลัพธ์
            self.performance_cache = report
            self.last_analysis_time = datetime.now()
            
            logger.info(f"Generated performance report for {days} days")
            return report
            
        except Exception as e:
            logger.error(f"Error generating performance report: {e}")
            return {"error": str(e)}

    def get_summary_stats(self) -> Dict:
        """
        ===================================================================
        📊 SUMMARY STATS LAYER - สถิติสรุปแบบย่อ
        ===================================================================
        """
        if not self.trading_data:
            if not self.load_trading_data(7):  # โหลด 7 วันล่าสุด
                return {"error": "No data available"}
        
        try:
            basic = self.calculate_basic_metrics()
            
            return {
                "total_trades": basic.get("total_trades", 0),
                "win_rate": basic.get("win_rate", 0),
                "active_positions": basic.get("open_trades", 0),
                "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
        except Exception as e:
            logger.error(f"Error getting summary stats: {e}")
            return {"error": str(e)}

    def compare_timeframes(self) -> Dict:
        """
        ===================================================================
        ⏰ TIMEFRAME COMPARISON LAYER - เปรียบเทียบ performance ตาม timeframe
        ===================================================================
        """
        if not self.signal_data:
            return {"message": "No signal data for timeframe analysis"}
            
        try:
            timeframe_performance = {}
            
            # จับคู่ signals กับ trades (ถ้าเป็นไปได้)
            for signal in self.signal_data:
                timeframe = signal.get("Timeframe", "UNKNOWN")
                symbol = signal.get("Symbol", "")
                
                if timeframe not in timeframe_performance:
                    timeframe_performance[timeframe] = {
                        "total_signals": 0,
                        "signal_strength": []
                    }
                
                timeframe_performance[timeframe]["total_signals"] += 1
                
                # เก็บ signal strength ถ้ามี
                strength = signal.get("Signal_Strength", 0)
                if strength:
                    timeframe_performance[timeframe]["signal_strength"].append(float(strength))
            
            # คำนวณค่าเฉลี่ย signal strength
            for tf in timeframe_performance:
                strengths = timeframe_performance[tf]["signal_strength"]
                if strengths:
                    timeframe_performance[tf]["avg_signal_strength"] = round(
                        statistics.mean(strengths), 1
                    )
                else:
                    timeframe_performance[tf]["avg_signal_strength"] = 0
            
            return timeframe_performance
            
        except Exception as e:
            logger.error(f"Error comparing timeframes: {e}")
            return {"error": str(e)}

    def get_recent_performance(self, days: int = 7) -> Dict:
        """ดูผลงาน N วันล่าสุด"""
        return self.generate_performance_report(days)

    def export_data_for_analysis(self) -> Dict:
        """
        ===================================================================
        📤 DATA EXPORT LAYER - Export ข้อมูลสำหรับวิเคราะห์เพิ่มเติม
        ===================================================================
        """
        try:
            export_data = {
                "trading_data": self.trading_data,
                "signal_data": self.signal_data,
                "export_timestamp": datetime.now().isoformat(),
                "data_summary": {
                    "total_trades": len(self.trading_data),
                    "total_signals": len(self.signal_data),
                    "date_range": {
                        "oldest_trade": min([t["date"] for t in self.trading_data]) if self.trading_data else None,
                        "newest_trade": max([t["date"] for t in self.trading_data]) if self.trading_data else None
                    }
                }
            }
            
            return export_data
            
        except Exception as e:
            logger.error(f"Error exporting data: {e}")
            return {"error": str(e)}
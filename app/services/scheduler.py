"""
Auto Scheduler for Signal Detection and Notification - REFACTORED for v2.0
Simplified to use refactored services architecture
"""
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from config.settings import Config

logger = logging.getLogger(__name__)


class SignalScheduler:
    """
    REFACTORED Signal Scheduler for v2.0
    
    Main responsibilities:
    - Schedule automated signal scanning
    - Coordinate between refactored services
    - Send notifications and log data
    - Prevent duplicate signals with cooldown system
    
    Uses refactored services:
    - SignalDetector (with integrated DataManager + PositionManager)
    - LineNotifier (via ConfigManager)
    - SheetsLogger (via ConfigManager)
    """

    def __init__(self, config: Dict):
        """
        Initialize scheduler with refactored architecture
        
        Args:
            config: Configuration dictionary from ConfigManager
        """
        # Basic configuration
        self.config = config
        self.scheduler = BackgroundScheduler()
        self.running = False
        
        # Services (will be injected)
        self.signal_detector = None
        self.position_manager = None
        self.line_notifier = None
        self.sheets_logger = None
        
        # Signal deduplication system
        self.last_signals = {}  # Store signal history
        self.cooldown_minutes = Config.SIGNAL_COOLDOWN_MINUTES
        self.signal_history_file = "data/signal_history.json"
        
        # Load signal history from file
        self._load_signal_history()
        
        logger.info(f"SignalScheduler v2.0 initialized with {self.cooldown_minutes}min cooldown")

    def _load_signal_history(self):
        """Load signal history from file"""
        try:
            if os.path.exists(self.signal_history_file):
                with open(self.signal_history_file, 'r') as f:
                    data = json.load(f)
                
                # Convert string timestamps back to datetime
                for key, timestamp_str in data.items():
                    self.last_signals[key] = datetime.fromisoformat(timestamp_str)
                
                logger.info(f"Loaded {len(self.last_signals)} signal history records")
            else:
                logger.info("No signal history file found, starting fresh")
                
        except Exception as e:
            logger.error(f"Error loading signal history: {e}")
            self.last_signals = {}

    def _save_signal_history(self):
        """Save signal history to file"""
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.signal_history_file), exist_ok=True)
            
            # Convert datetime to string for JSON storage
            data = {}
            for key, timestamp in self.last_signals.items():
                data[key] = timestamp.isoformat()
            
            with open(self.signal_history_file, 'w') as f:
                json.dump(data, f, indent=2)
                
            logger.debug(f"Saved {len(data)} signal history records")
            
        except Exception as e:
            logger.error(f"Error saving signal history: {e}")

    def _is_duplicate_signal(self, symbol: str, timeframe: str, direction: str) -> bool:
        """
        Check if signal is duplicate within cooldown period
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            direction: Signal direction (LONG/SHORT)
            
        Returns:
            bool: True if signal is duplicate
        """
        signal_key = f"{symbol}_{timeframe}_{direction}"
        current_time = datetime.now()
        
        # Check if we've sent this signal recently
        if signal_key in self.last_signals:
            last_time = self.last_signals[signal_key]
            time_diff = current_time - last_time
            
            # If still within cooldown period
            if time_diff.total_seconds() < (self.cooldown_minutes * 60):
                remaining_minutes = self.cooldown_minutes - (time_diff.total_seconds() / 60)
                logger.debug(f"Signal cooldown active for {signal_key}: {remaining_minutes:.1f} minutes remaining")
                return True
        
        # Clean up old data (keep only last 24 hours)
        cutoff_time = current_time - timedelta(hours=24)
        keys_to_remove = [
            key for key, timestamp in self.last_signals.items()
            if timestamp < cutoff_time
        ]
        for key in keys_to_remove:
            del self.last_signals[key]
        
        return False

    def _record_signal(self, symbol: str, timeframe: str, direction: str):
        """Record signal that was sent"""
        signal_key = f"{symbol}_{timeframe}_{direction}"
        self.last_signals[signal_key] = datetime.now()
        
        # Save to file immediately
        self._save_signal_history()
        logger.debug(f"Recorded signal: {signal_key}")

    def set_services(self, signal_detector, position_manager, line_notifier, sheets_logger):
        """
        Inject refactored services
        
        Args:
            signal_detector: SignalDetector instance
            position_manager: PositionManager instance
            line_notifier: LineNotifier instance
            sheets_logger: SheetsLogger instance
        """
        self.signal_detector = signal_detector
        self.position_manager = position_manager
        self.line_notifier = line_notifier
        self.sheets_logger = sheets_logger
        
        logger.info("Refactored services injected into scheduler")

    def start_scheduler(self):
        """Start the automated scheduler"""
        if self.running:
            logger.warning("Scheduler already running")
            return
        
        if not all([self.signal_detector, self.position_manager]):
            logger.error("Required services not set")
            return
        
        # Job 1: Scan 4H signals - ทุก 15 นาที
        self.scheduler.add_job(
            func=self._scan_4h_signals,
            trigger="cron",
            hour="*",
            minute="*/15",      # ← แก้ตรงนี้! เดิมเป็น "0"
            id="scan_4h_signals",
            name="4H Signal Scanner v2.0",
            replace_existing=True,
        )

        # Job 2: ถูกต้องแล้ว ✅
        self.scheduler.add_job(
            func=self._scan_1d_signals,
            trigger="cron",
            hour="0,4,8,12,16,20",
            minute=0,
            id="scan_1d_signals",
            name="1D Signal Scanner v2.0 (Every 4H)",
            replace_existing=True,
        )
        
        # Job 2: Update positions every 2 minutes (via PositionManager)
        self.scheduler.add_job(
            func=self._update_positions_refactored,
            trigger=IntervalTrigger(minutes=2),
            id="update_positions",
            name="Position Tracker v2.0",
            replace_existing=True,
        )
        
        # Job 3: Daily summary at midnight
        self.scheduler.add_job(
            func=self._send_daily_summary,
            trigger="cron",
            hour=0,
            minute=0,
            id="daily_summary",
            name="Daily Summary v2.0",
            replace_existing=True,
        )
        
        # Start scheduler
        self.scheduler.start()
        self.running = True
        
        logger.info("SignalScheduler v2.0 started successfully")
        logger.info("Scheduled jobs:")
        logger.info(" - 4H signals: every 15 minutes")
        logger.info(" - 1D signals: every 4 hours (00:00, 04:00, 08:00, 12:00, 16:00, 20:00 UTC)")
        logger.info(" - Position updates: every 2 minutes (via PositionManager)")
        logger.info(" - Daily summary: daily at 00:00 UTC (07:00 ICT)")
        logger.info(f" - Signal cooldown: {self.cooldown_minutes} minutes")

    def stop_scheduler(self):
        """Stop the scheduler"""
        if not self.running:
            logger.warning("Scheduler not running")
            return
        
        # Save history before stopping
        self._save_signal_history()
        
        self.scheduler.shutdown(wait=False)
        self.running = False
        
        logger.info("SignalScheduler v2.0 stopped")

    def get_scheduler_status(self) -> Dict:
        """Get current scheduler status"""
        if not self.running:
            return {
                "status": "stopped",
                "jobs": [],
                "next_run_times": {},
                "signal_history_count": len(self.last_signals),
                "version": "2.0-refactored"
            }
        
        jobs = []
        next_run_times = {}
        
        for job in self.scheduler.get_jobs():
            job_info = {
                "id": job.id,
                "name": job.name,
                "next_run": (
                    job.next_run_time.isoformat() if job.next_run_time else None
                ),
                "trigger": str(job.trigger),
            }
            jobs.append(job_info)
            next_run_times[job.id] = job_info["next_run"]
        
        return {
            "status": "running",
            "jobs": jobs,
            "next_run_times": next_run_times,
            "scheduler_state": str(self.scheduler.state),
            "signal_history_count": len(self.last_signals),
            "cooldown_minutes": self.cooldown_minutes,
            "version": "2.0-refactored",
            "services_connected": {
                "signal_detector": self.signal_detector is not None,
                "position_manager": self.position_manager is not None,
                "line_notifier": self.line_notifier is not None,
                "sheets_logger": self.sheets_logger is not None
            }
        }

    def _scan_4h_signals(self):
        """Scan 4H signals"""
        try:
            logger.info("Starting 4H signal scan v2.0...")
            
            symbols = Config.DEFAULT_SYMBOLS if hasattr(Config, 'DEFAULT_SYMBOLS') else ["BTCUSDT", "ETHUSDT"]
        
            if not symbols:
                logger.warning("No symbols configured for scanning")
                return
            
            active_signals = self.signal_detector.get_active_signals(symbols, ["4h"])
            logger.info(f"Found {len(active_signals)} active signals on 4H")
            
            processed_count = 0
            for signal in active_signals:
                if self._process_signal_refactored(signal, "4h"):
                    processed_count += 1
            
            logger.info(f"Processed {processed_count}/{len(active_signals)} signals on 4H")
            
        except Exception as e:
            logger.error(f"Error in 4H signal scan: {e}")

    def _scan_1d_signals(self):
        """Scan 1D signals using refactored SignalDetector"""
        try:
            logger.info("Starting 1D signal scan v2.0...")
            
            symbols = Config.DEFAULT_SYMBOLS if hasattr(Config, 'DEFAULT_SYMBOLS') else ["BTCUSDT", "ETHUSDT"]
        
            if not symbols:
                logger.warning("No symbols configured for scanning")
                return
            
            # Use refactored SignalDetector
            active_signals = self.signal_detector.get_active_signals(symbols, ["1d"])
            logger.info(f"Found {len(active_signals)} active signals on 1D")
            
            processed_count = 0
            for signal in active_signals:
                if self._process_signal_refactored(signal, "1d"):
                    processed_count += 1
            
            logger.info(f"Processed {processed_count}/{len(active_signals)} signals on 1D")
            
        except Exception as e:
            logger.error(f"Error in 1D signal scan: {e}")
            if self.line_notifier:
                try:
                    self.line_notifier.send_error_alert(
                        f"1D signal scan failed: {str(e)}", "Scheduler v2.0"
                    )
                except:
                    pass

    def _process_signal_refactored(self, signal: Dict, timeframe: str) -> bool:
        """
        Process signal using refactored architecture
        
        Args:
            signal: Signal data from SignalDetector
            timeframe: Timeframe being processed
            
        Returns:
            bool: True if signal was processed successfully
        """
        try:
            # Extract basic signal information
            symbol = signal.get("symbol")
            signals = signal.get("signals", {})
            signal_strength = signal.get("signal_strength", 0)
            position_created = signal.get("position_created", False)
            
            # Validate basic data
            if not symbol:
                return False
            
            # Check signal strength threshold (75%)
            if signal_strength < 75:
                logger.debug(f"Skipping {symbol} {timeframe} - signal strength {signal_strength} < 75")
                return False
            
            # Determine trading direction
            direction = None
            if signals.get("buy"):
                direction = "LONG"
            elif signals.get("short"):
                direction = "SHORT"
            
            if not direction:
                logger.debug(f"No valid signal direction for {symbol} {timeframe}")
                return False
            
            # Check for duplicate signals
            if self._is_duplicate_signal(symbol, timeframe, direction):
                logger.info(f"⏭️ SKIPPED DUPLICATE: {symbol} {timeframe} {direction}")
                return False
            
            # SignalDetector should have already created position if valid
            if not position_created:
                logger.debug(f"Position not auto-created for {symbol} {timeframe}")
                # Still record to prevent duplicate attempts
                self._record_signal(symbol, timeframe, direction)
                return False
            
            # Send LINE notification for new signals with positions
            if self.line_notifier:
                try:
                    self.line_notifier.send_signal_alert(signal)
                    logger.info(f"Sent LINE notification for {symbol} {timeframe} {direction}")
                except Exception as e:
                    logger.warning(f"Failed to send LINE notification: {e}")
            
            # Log to Google Sheets for new signals with positions
            if self.sheets_logger:
                try:
                    self.sheets_logger.log_trading_journal(signal)
                    logger.info(f"Logged to Google Sheets: {symbol} {timeframe} {direction}")
                except Exception as e:
                    logger.warning(f"Failed to log to Google Sheets: {e}")
            
            # Record signal in history
            self._record_signal(symbol, timeframe, direction)
            
            logger.info(f"Processed new signal: {symbol} {timeframe} {direction} (Strength: {signal_strength})")
            return True
            
        except Exception as e:
            logger.error(f"Error processing signal {signal.get('symbol', 'UNKNOWN')}: {e}")
            return False

    def _update_positions_refactored(self):
        """
        Update positions using refactored PositionManager
        
        This method now simply triggers PositionManager to update all positions
        and handles any notifications/logging for the results
        """
        try:
            if not self.position_manager:
                logger.warning("No PositionManager available for position updates")
                return
            
            # Get current active positions count
            summary = self.position_manager.get_positions_summary()
            active_count = summary.get("active_positions", 0)
            
            logger.info(f"📍 Checking {active_count} active positions...")
            
            if active_count == 0:
                logger.debug("No active positions to update")
                return
            
            # Trigger PositionManager to update all positions
            updates = self.position_manager.update_positions()
            
            # Process any position updates for notifications
            notifications_sent = 0
            sheets_logged = 0
            
            for position_id, update_info in updates.items():
                try:
                    # Check if any important events occurred
                    events = []
                    if update_info.get('position_closed'):
                        events.append("Position closed")
                    
                    for tp_level in ['TP1', 'TP2', 'TP3']:
                        if update_info.get(f'{tp_level}_hit', {}).get('hit', False):
                            events.append(f"{tp_level} hit")
                    
                    if update_info.get('sl_hit', {}).get('hit', False):
                        events.append("SL hit")
                    
                    if events:
                        logger.info(f"Position {position_id}: {', '.join(events)}")
                        
                        # Send LINE notification if available
                        if self.line_notifier:
                            try:
                                # Format update for LINE notification
                                position_data = self.position_manager.positions.get(position_id)
                                if position_data:
                                    notification_data = {
                                        "position": position_data,
                                        "updates": update_info,
                                        "events": events
                                    }
                                    self.line_notifier.send_position_update(notification_data)
                                    notifications_sent += 1
                            except Exception as e:
                                logger.warning(f"Failed to send position update notification: {e}")
                        
                        # Log to Google Sheets if available
                        if self.sheets_logger:
                            try:
                                position_data = self.position_manager.positions.get(position_id)
                                if position_data:
                                    self.sheets_logger.log_position_update({
                                        "position": position_data,
                                        "updates": update_info
                                    })
                                    sheets_logged += 1
                            except Exception as e:
                                logger.warning(f"Failed to log position update: {e}")
                                
                except Exception as e:
                    logger.error(f"Error processing update for {position_id}: {e}")
            
            if notifications_sent > 0 or sheets_logged > 0:
                logger.info(f"Position updates: {notifications_sent} LINE notifications, {sheets_logged} sheets logs")
                
        except Exception as e:
            logger.error(f"Error in refactored position update: {e}")

    def _send_daily_summary(self):
        """Send daily summary using refactored services"""
        try:
            logger.info("Generating daily summary v2.0...")
            
            # Get statistics from sheets logger if available
            if self.sheets_logger:
                try:
                    stats = self.sheets_logger.get_trading_statistics(days=1)
                except:
                    stats = {}
            else:
                stats = {}
            
            # Get position summary from PositionManager
            if self.position_manager:
                try:
                    position_summary = self.position_manager.get_positions_summary()
                except:
                    position_summary = {}
            else:
                position_summary = {}
            
            daily_summary = {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "version": "2.0-refactored",
                "total_signals": stats.get("total_trades", 0),
                "active_positions": position_summary.get("active_positions", 0),
                "closed_positions": position_summary.get("closed_positions", 0),
                "total_positions": position_summary.get("total_positions", 0),
                "win_rate_pct": position_summary.get("win_rate_pct", 0),
                "total_pnl_pct": position_summary.get("total_pnl_pct", 0),
                "wins": position_summary.get("wins", 0),
                "losses": position_summary.get("losses", 0),
                "signal_history_count": len(self.last_signals),
                "best_performer": stats.get("best_performer", ""),
                "worst_performer": stats.get("worst_performer", "")
            }
            
            # Send LINE notification
            if self.line_notifier:
                try:
                    self.line_notifier.send_daily_summary(daily_summary)
                    logger.info("Daily summary sent via LINE")
                except Exception as e:
                    logger.warning(f"Failed to send daily summary via LINE: {e}")
            
            # Log to Google Sheets
            if self.sheets_logger:
                try:
                    self.sheets_logger.log_daily_summary(daily_summary)
                    logger.info("Daily summary logged to sheets")
                except Exception as e:
                    logger.warning(f"Failed to log daily summary: {e}")
            
        except Exception as e:
            logger.error(f"Error sending daily summary: {e}")

    def get_enhanced_status(self) -> Dict:
        """Get detailed status including position summary"""
        try:
            scheduler_status = self.get_scheduler_status()
            
            # Add position summary if available
            if self.position_manager:
                try:
                    position_summary = self.position_manager.get_positions_summary()
                    scheduler_status["position_summary"] = position_summary
                except Exception as e:
                    logger.error(f"Error getting position summary: {e}")
            
            # Add signal history details
            scheduler_status["signal_history"] = self.get_signal_history()
            
            return scheduler_status
            
        except Exception as e:
            logger.error(f"Error getting enhanced status: {e}")
            return self.get_scheduler_status()

    def force_scan_now(self, timeframe: str = "1d") -> Dict:
        """Force immediate signal scan"""
        try:
            if timeframe == "1d":
                self._scan_1d_signals()
                return {"status": "1D scan completed", "version": "2.0-refactored"}
            else:
                return {"error": "Invalid timeframe. Use '1d' only"}
        except Exception as e:
            logger.error(f"Error in force scan: {e}")
            return {"error": str(e)}

    def force_update_positions(self) -> Dict:
        """Force immediate position update"""
        try:
            self._update_positions_refactored()
            return {"status": "Position update completed", "version": "2.0-refactored"}
        except Exception as e:
            logger.error(f"Error in force position update: {e}")
            return {"error": str(e)}

    def clear_signal_history(self):
        """Clear all signal history (for testing)"""
        self.last_signals = {}
        self._save_signal_history()
        logger.info("Signal history cleared")

    def get_signal_history(self) -> Dict:
        """Get signal history with timestamps"""
        history = {}
        for key, timestamp in self.last_signals.items():
            history[key] = {
                "timestamp": timestamp.isoformat(),
                "minutes_ago": (datetime.now() - timestamp).total_seconds() / 60
            }
        return history

    def _process_signal(self, signal: Dict, timeframe: str):
        """Legacy method - redirects to refactored version"""
        return self._process_signal_refactored(signal, timeframe)

    def _update_positions(self):
        """Legacy method - redirects to refactored version"""
        self._update_positions_refactored()
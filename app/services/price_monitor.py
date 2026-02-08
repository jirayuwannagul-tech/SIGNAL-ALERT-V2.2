"""
Price Monitor - REFACTORED for v2.0
Simplified coordinator that delegates position tracking to PositionManager
"""

import logging
import time
from datetime import datetime
from typing import Dict, List, Optional
from threading import Thread, Lock

logger = logging.getLogger(__name__)


class PriceMonitor:
    """
    REFACTORED Price Monitor - Now acts as coordinator only
    
    Main responsibilities:
    - Coordinate with PositionManager for position updates
    - Handle Google Sheets logging
    - Provide monitoring status and controls
    
    Removed responsibilities (now handled by PositionManager):
    - TP/SL calculation and detection
    - Position tracking logic
    - Price fetching (delegated to DataManager)
    """

    def __init__(self, config: Dict, sheets_logger=None):
        """
        Initialize simplified Price Monitor coordinator
        
        Args:
            config: Configuration dictionary
            sheets_logger: SheetsLogger instance for Google Sheets integration
        """
        self.config = config
        self.sheets_logger = sheets_logger
        
        # Monitoring control
        self.monitoring = False
        self.monitor_thread = None
        self.monitor_lock = Lock()
        
        # Configuration
        self.update_interval = config.get("PRICE_MONITOR_INTERVAL", 30)
        
        # Statistics
        self.stats = {
            "monitoring_cycles": 0,
            "positions_updated": 0,
            "tp_hits_logged": 0,
            "sl_hits_logged": 0,
            "last_check": None,
            "errors": 0
        }
        
        # Services (will be injected)
        self.position_manager = None
        self.data_manager = None
        
        logger.info(f"PriceMonitor v2.0 initialized as coordinator (interval: {self.update_interval}s)")

    def set_services(self, position_manager=None, data_manager=None):
        """
        Inject refactored services
        
        Args:
            position_manager: PositionManager instance
            data_manager: DataManager instance
        """
        self.position_manager = position_manager
        self.data_manager = data_manager
        logger.info("Services injected into PriceMonitor")

    def start_monitoring(self):
        """Start the monitoring coordinator"""
        if self.monitoring:
            logger.warning("Monitoring already running")
            return
        
        if not self.position_manager:
            logger.error("Cannot start monitoring: No PositionManager available")
            return
            
        self.monitoring = True
        self.monitor_thread = Thread(
            target=self._monitoring_loop,
            daemon=True,
            name="PriceMonitorCoordinator"
        )
        self.monitor_thread.start()
        
        logger.info("PriceMonitor coordinator started")

    def stop_monitoring(self):
        """Stop the monitoring coordinator"""
        if not self.monitoring:
            return
            
        self.monitoring = False
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            logger.info("Stopping price monitor coordinator...")
            self.monitor_thread.join(timeout=15)
            
        logger.info("Price monitor coordinator stopped")

    def _monitoring_loop(self):
        """
        Main monitoring loop - simplified coordinator
        
        This loop now focuses on:
        1. Triggering PositionManager updates
        2. Logging results to Google Sheets
        3. Collecting statistics
        """
        logger.info("PriceMonitor coordinator loop started")
        
        while self.monitoring:
            try:
                self.stats["last_check"] = datetime.now().isoformat()
                self.stats["monitoring_cycles"] += 1
                
                # Check if we have services available
                if not self.position_manager:
                    logger.warning("No PositionManager available, skipping cycle")
                    time.sleep(self.update_interval)
                    continue
                
                # Get active positions count
                summary = self.position_manager.get_positions_summary()
                active_count = summary.get("active_positions", 0)
                
                if active_count == 0:
                    logger.debug("No active positions to monitor")
                    time.sleep(self.update_interval)
                    continue
                
                logger.info(f"Monitoring {active_count} active positions")
                
                # Trigger PositionManager to update all positions
                updates = self.position_manager.update_positions()
                self.stats["positions_updated"] += len(updates)
                
                # Process updates and log to sheets if available
                if updates and self.sheets_logger:
                    self._process_updates_for_sheets(updates)
                
                # Log summary
                if updates:
                    logger.info(f"Processed {len(updates)} position updates")
                    for position_id, update_info in updates.items():
                        if update_info.get('position_closed'):
                            logger.info(f"Position closed: {position_id}")
                        elif any(key.endswith('_hit') for key in update_info.keys()):
                            tp_hits = [k for k in update_info.keys() if k.endswith('_hit') and k.startswith('TP')]
                            if tp_hits:
                                logger.info(f"TP hit: {position_id} - {tp_hits}")
                
                # Sleep until next cycle
                time.sleep(self.update_interval)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                self.stats["errors"] += 1
                time.sleep(30)  # Wait 30 seconds on error

    def _process_updates_for_sheets(self, updates: Dict):
        """
        Process position updates for Google Sheets logging
        
        Args:
            updates: Dictionary of position updates from PositionManager
        """
        try:
            if not self.sheets_logger:
                return
                
            for position_id, update_info in updates.items():
                # Get the position data
                position_data = self.position_manager.positions.get(position_id)
                if not position_data:
                    continue
                
                # Log TP hits
                for tp_level in ['TP1', 'TP2', 'TP3']:
                    tp_key = f'{tp_level}_hit'
                    if update_info.get(tp_key, {}).get('hit', False):
                        try:
                            self.sheets_logger.log_tp_hit(position_data, update_info[tp_key])
                            self.stats["tp_hits_logged"] += 1
                            logger.info(f"Logged {tp_level} hit for {position_id}")
                        except Exception as e:
                            logger.error(f"Error logging {tp_level} hit: {e}")
                
                # Log SL hits
                if update_info.get('sl_hit', {}).get('hit', False):
                    try:
                        self.sheets_logger.log_sl_hit(position_data, update_info['sl_hit'])
                        self.stats["sl_hits_logged"] += 1
                        logger.info(f"Logged SL hit for {position_id}")
                    except Exception as e:
                        logger.error(f"Error logging SL hit: {e}")
                
                # Log position closure
                if update_info.get('position_closed', False):
                    try:
                        self.sheets_logger.log_position_close(position_data)
                        logger.info(f"Logged position closure for {position_id}")
                    except Exception as e:
                        logger.error(f"Error logging position closure: {e}")
                        
        except Exception as e:
            logger.error(f"Error processing updates for sheets: {e}")

    def get_monitoring_status(self) -> Dict:
        """Get current monitoring status"""
        status = {
            "monitoring": self.monitoring,
            "thread_alive": self.monitor_thread.is_alive() if self.monitor_thread else False,
            "update_interval": self.update_interval,
            "sheets_connected": self.sheets_logger is not None,
            "services": {
                "position_manager": self.position_manager is not None,
                "data_manager": self.data_manager is not None
            },
            "stats": self.stats.copy(),
            "version": "2.0-refactored"
        }
        
        # Add position summary if available
        if self.position_manager:
            try:
                summary = self.position_manager.get_positions_summary()
                status["positions_count"] = summary.get("active_positions", 0)
                status["total_positions"] = summary.get("total_positions", 0)
            except Exception as e:
                logger.error(f"Error getting position summary: {e}")
                status["positions_count"] = 0
                status["total_positions"] = 0
        
        return status

    def force_check_all_positions(self) -> Dict:
        """
        Force check all positions immediately via PositionManager
        
        Returns:
            Dict with check results
        """
        try:
            if not self.position_manager:
                return {"error": "No PositionManager available"}
            
            logger.info("Force checking all positions via PositionManager")
            
            # Get current active positions
            active_positions = self.position_manager.get_active_positions()
            
            # Trigger immediate update
            updates = self.position_manager.update_positions()
            
            # Process any updates for sheets
            if updates and self.sheets_logger:
                self._process_updates_for_sheets(updates)
            
            return {
                "status": "success",
                "message": "Force check completed",
                "positions_checked": len(active_positions),
                "updates_found": len(updates),
                "updates": updates,
                "timestamp": datetime.now().isoformat(),
                "version": "2.0-refactored"
            }
            
        except Exception as e:
            logger.error(f"Error in force check: {e}")
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    def get_price_for_symbol(self, symbol: str) -> Dict:
        """
        Get current price for symbol via DataManager
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Dict with price information
        """
        try:
            if not self.data_manager:
                return {"error": "No DataManager available"}
            
            price = self.data_manager.get_single_price(symbol.upper())
            
            if price is not None:
                return {
                    "status": "success",
                    "symbol": symbol.upper(),
                    "current_price": price,
                    "timestamp": datetime.now().isoformat(),
                    "version": "2.0-refactored"
                }
            else:
                return {
                    "status": "error",
                    "error": f"Could not get price for {symbol}",
                    "symbol": symbol.upper()
                }
                
        except Exception as e:
            logger.error(f"Error getting price for {symbol}: {e}")
            return {
                "status": "error",
                "error": str(e),
                "symbol": symbol.upper()
            }

    # Legacy compatibility methods
    def get_current_price(self, symbol: str) -> Optional[float]:
        """
        Legacy method for getting current price
        Delegates to DataManager if available
        """
        try:
            if self.data_manager:
                return self.data_manager.get_single_price(symbol)
            else:
                logger.warning("No DataManager available for price fetch")
                return None
        except Exception as e:
            logger.error(f"Error getting current price for {symbol}: {e}")
            return None

    def get_stats(self) -> Dict:
        """Get monitoring statistics"""
        stats = self.stats.copy()
        stats["version"] = "2.0-refactored"
        stats["monitoring_active"] = self.monitoring
        
        if self.position_manager:
            try:
                summary = self.position_manager.get_positions_summary()
                stats["current_active_positions"] = summary.get("active_positions", 0)
                stats["total_positions"] = summary.get("total_positions", 0)
            except Exception as e:
                logger.error(f"Error getting position stats: {e}")
        
        return stats

    def reset_stats(self):
        """Reset monitoring statistics"""
        self.stats = {
            "monitoring_cycles": 0,
            "positions_updated": 0,
            "tp_hits_logged": 0,
            "sl_hits_logged": 0,
            "last_check": None,
            "errors": 0
        }
        logger.info("Monitoring statistics reset")

    def shutdown(self):
        """Shutdown the price monitor"""
        try:
            logger.info("Shutting down PriceMonitor v2.0...")
            self.stop_monitoring()
            logger.info("PriceMonitor shutdown complete")
        except Exception as e:
            logger.error(f"Error during PriceMonitor shutdown: {e}")

    # Removed methods that are now handled by PositionManager:
    # - get_active_positions_from_sheets() -> PositionManager handles positions
    # - update_sheet_cell() -> SheetsLogger handles sheet updates  
    # - check_tp_sl_levels() -> PositionManager._check_tp_sl_hits() handles this
    # - monitor_positions() -> replaced with _monitoring_loop() coordinator
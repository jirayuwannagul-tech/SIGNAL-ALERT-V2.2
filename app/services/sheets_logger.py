"""
Google Sheets Integration for Trading Signal Logging - REFACTORED for v2.0
Simplified to use ConfigManager for configuration
FIXED: worksheet attribute error + Base64 credentials support
"""

import base64
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    import gspread
    from google.oauth2.service_account import Credentials
    SHEETS_AVAILABLE = True
except ImportError:
    SHEETS_AVAILABLE = False
    gspread = None
    Credentials = None

logger = logging.getLogger(__name__)


class SheetsLogger:
    """
    REFACTORED Google Sheets Logger for v2.0
    
    Main responsibilities:
    - Connect to Google Sheets using ConfigManager settings
    - Log trading signals and results
    - Track Trading Journal with Win/Loss tracking
    - Calculate Win Rate automatically
    - Generate trading statistics
    
    Uses ConfigManager for:
    - Google Sheets ID
    - Credentials path/content
    """

    def __init__(self, config: Dict):
        """
        Initialize SheetsLogger with ConfigManager config
        
        Args:
            config: Configuration from ConfigManager.get_google_config()
                   Expected keys: 'sheets_id', 'credentials_path'
        """
        # Configuration from ConfigManager
        self.credentials_path = config.get("credentials_path")
        self.spreadsheet_id = config.get("sheets_id")
        
        # Connection state
        self.gc = None                    # Google Sheets client
        self.spreadsheet = None           # Spreadsheet object
        self._cached_worksheet = None     # Current worksheet cache (FIXED)
        self._initialized = False         # Initialization status

        # Show configuration status
        logger.info("Initializing SheetsLogger v2.0...")
        logger.info(f"Credentials configured: {bool(self.credentials_path)}")
        logger.info(f"Spreadsheet ID configured: {bool(self.spreadsheet_id)}")

        # Check dependencies
        if not SHEETS_AVAILABLE:
            logger.warning("Google Sheets dependencies not installed")
            return

        # Check configuration
        if not self.credentials_path or not self.spreadsheet_id:
            logger.warning("Google Sheets credentials or spreadsheet ID not configured")
            logger.warning(f"   Credentials: {'available' if self.credentials_path else 'missing'}")
            logger.warning(f"   Spreadsheet ID: {'available' if self.spreadsheet_id else 'missing'}")
            return

        # Attempt connection
        try:
            self._initialize_connection()
            self._initialized = True
            logger.info("SheetsLogger v2.0 initialization completed successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Google Sheets connection: {e}")
            self._initialized = False

    @property
    def worksheet(self):
        """
        Property to safely access Trading_Journal worksheet
        Returns None if not initialized or worksheet not available
        """
        if not self._initialized or not self.spreadsheet:
            return None
        
        try:
            # Try to get cached worksheet first
            if self._cached_worksheet:
                return self._cached_worksheet
            
            # Get worksheet from spreadsheet
            worksheet = self.spreadsheet.worksheet("Trading_Journal")
            self._cached_worksheet = worksheet
            return worksheet
            
        except Exception as e:
            logger.error(f"Error accessing Trading_Journal worksheet: {e}")
            return None

    def _initialize_connection(self):
        """Initialize connection to Google Sheets"""
        if not SHEETS_AVAILABLE:
            return

        try:
            # Define OAuth permissions
            scope = [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive",
            ]

            logger.info(f"Loading credentials type: {type(self.credentials_path)}")

            credentials_str = str(self.credentials_path).strip()

            # ลองโหลดเป็น JSON string ก่อน
            if credentials_str.startswith('{'):
                try:
                    logger.info("Loading credentials from JSON string")
                    creds_info = json.loads(credentials_str)
                    creds = Credentials.from_service_account_info(creds_info, scopes=scope)
                    logger.info("✅ Successfully loaded credentials from JSON string")
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON in credentials: {e}")
                    raise
            # ถ้าเป็นไฟล์
            elif os.path.isfile(credentials_str):
                logger.info(f"Loading credentials from file: {credentials_str}")
                creds = Credentials.from_service_account_file(
                    credentials_str, scopes=scope
                )
                logger.info("✅ Successfully loaded credentials from file")
            else:
                logger.error(f"Invalid credentials format (not JSON or file): {credentials_str[:100]}")
                raise ValueError(f"Invalid credentials format")

            # Create authorized client
            self.gc = gspread.authorize(creds)
            
            # Connect to spreadsheet
            self.spreadsheet = self.gc.open_by_key(self.spreadsheet_id)

            # Try to access or create the main worksheet
            try:
                self._cached_worksheet = self.spreadsheet.worksheet("Trading_Journal")
                logger.info("Connected to existing Trading_Journal worksheet")
            except gspread.WorksheetNotFound:
                # Create Trading_Journal worksheet if it doesn't exist
                headers = ["Date", "Symbol", "Signal", "Entry", "SL", "TP1", "TP2", "TP3", "Win/Loss", "Win Rate"]
                self._cached_worksheet = self.spreadsheet.add_worksheet(
                    title="Trading_Journal", rows=1000, cols=len(headers)
                )
                self._cached_worksheet.append_row(headers)
                logger.info("Created new Trading_Journal worksheet")

            logger.info("Google Sheets connection established")
            logger.info(f"Spreadsheet: {self.spreadsheet.title}")
            logger.info(f"Spreadsheet ID: {self.spreadsheet_id}")

        except Exception as e:
            logger.error(f"Google Sheets initialization error: {e}")
            logger.error(f"Credentials path: {self.credentials_path}")
            logger.error(f"Spreadsheet ID: {self.spreadsheet_id}")
            raise   

    def _ensure_worksheet_exists(self, worksheet_name: str, headers: List[str]) -> Optional[Any]:
        """Ensure worksheet exists with proper headers"""
        if not self.spreadsheet:
            logger.error("Spreadsheet not initialized")
            return None

        try:
            # Try to find existing worksheet
            try:
                worksheet = self.spreadsheet.worksheet(worksheet_name)
                logger.info(f"Found existing worksheet: {worksheet_name}")

                # Check headers
                existing_headers = worksheet.row_values(1)
                if not existing_headers or existing_headers != headers:
                    worksheet.clear()
                    worksheet.append_row(headers)
                    logger.info(f"Updated headers for worksheet: {worksheet_name}")

                return worksheet

            # Create new worksheet if not found
            except gspread.WorksheetNotFound:
                logger.info(f"Creating new worksheet: {worksheet_name}")
                worksheet = self.spreadsheet.add_worksheet(
                    title=worksheet_name, 
                    rows=1000,
                    cols=len(headers)
                )
                worksheet.append_row(headers)
                logger.info(f"Created new worksheet: {worksheet_name}")
                return worksheet

        except Exception as e:
            logger.error(f"Error ensuring worksheet exists: {e}")
            return None

    def _determine_signal_type(self, signals: Dict) -> str:
        """Determine signal type from signals dictionary"""
        # Strong signals (highest priority)
        if signals.get("strong_buy"):
            return "STRONG_BUY"
        elif signals.get("strong_short"):
            return "STRONG_SHORT"
        
        # Medium signals
        elif signals.get("medium_buy"):
            return "MEDIUM_BUY"
        elif signals.get("medium_short"):
            return "MEDIUM_SHORT"
        
        # Weak signals
        elif signals.get("weak_buy"):
            return "WEAK_BUY"
        elif signals.get("weak_short"):
            return "WEAK_SHORT"
        
        # Experimental signals
        elif signals.get("experimental_buy"):
            return "EXPERIMENTAL_BUY"
        elif signals.get("experimental_short"):
            return "EXPERIMENTAL_SHORT"
        
        # Basic signals (legacy support)
        elif signals.get("buy"):
            return "BUY"
        elif signals.get("short"):
            return "SHORT"
        elif signals.get("sell"):
            return "SELL"
        elif signals.get("cover"):
            return "COVER"
        
        # No signal
        else:
            return "NONE"

    def _has_tradeable_signal(self, signals: Dict) -> bool:
        """Check if signals contain tradeable signals"""
        return any([
            # Strong signals
            signals.get("strong_buy", False),
            signals.get("strong_short", False),
            
            # Medium signals  
            signals.get("medium_buy", False),
            signals.get("medium_short", False),
            
            # Weak signals
            signals.get("weak_buy", False),
            signals.get("weak_short", False),
            
            # Experimental signals
            signals.get("experimental_buy", False),
            signals.get("experimental_short", False),
            
            # Basic signals (legacy)
            signals.get("buy", False),
            signals.get("short", False)
        ])

    def _get_trade_direction(self, signals: Dict) -> Optional[str]:
        """Get trade direction from signals"""
        # LONG/BUY signals
        if any([
            signals.get("strong_buy", False),
            signals.get("medium_buy", False), 
            signals.get("weak_buy", False),
            signals.get("experimental_buy", False),
            signals.get("buy", False)
        ]):
            return "LONG"
        
        # SHORT signals
        elif any([
            signals.get("strong_short", False),
            signals.get("medium_short", False),
            signals.get("weak_short", False), 
            signals.get("experimental_short", False),
            signals.get("short", False)
        ]):
            return "SHORT"
        
        # No clear direction
        else:
            return None

    def log_signal(self, analysis: Dict) -> bool:
        """
        Log detailed signal information to Signals worksheet
        
        Args:
            analysis: Complete analysis from SignalDetector
            
        Returns:
            bool: True if logged successfully
        """
        # Check connection status
        if not self._initialized:
            logger.warning("SheetsLogger not properly initialized, skipping detailed signal log")
            return False
            
        if not self.spreadsheet:
            logger.warning("Google Sheets not initialized, skipping detailed signal log")
            return False

        try:
            symbol = analysis.get("symbol", "UNKNOWN")
            timeframe = analysis.get("timeframe", "UNKNOWN")
            logger.info(f"Attempting to log detailed signal: {symbol} ({timeframe})")
            
            # Define headers for detailed logging
            headers = [
                "Timestamp", "Symbol", "Timeframe", "Price", "Signal", "Recommendation",
                "Squeeze_Off", "Momentum", "MACD_Cross", "RSI_Value", "RSI_Level", 
                "Signal_Strength", "Entry_Price", "Stop_Loss", "TP1", "TP2", "TP3", "Risk_Reward"
            ]

            # Prepare worksheet
            logger.info("Ensuring Signals worksheet exists...")
            worksheet = self._ensure_worksheet_exists("Signals", headers)
            if not worksheet:
                logger.error("Failed to create/access Signals worksheet")
                return False

            # Extract data from analysis
            signals = analysis.get("signals", {})
            indicators = analysis.get("indicators", {})
            risk_levels = analysis.get("risk_levels", {})

            # Determine signal type
            signal_type = self._determine_signal_type(signals)
            logger.info(f"Signal type determined: {signal_type}")

            # Prepare row data
            try:
                row_data = [
                    analysis.get("timestamp", datetime.now().isoformat()),
                    symbol,
                    timeframe,
                    float(analysis.get("current_price", 0)),
                    signal_type,
                    analysis.get("recommendation", ""),
                    bool(indicators.get("squeeze", {}).get("squeeze_off", False)),
                    str(indicators.get("squeeze", {}).get("momentum_direction", "")),
                    str(indicators.get("macd", {}).get("cross_direction", "")),
                    float(indicators.get("rsi", {}).get("value", 0)),
                    str(indicators.get("rsi", {}).get("extreme_level", "")),
                    float(analysis.get("signal_strength", 0)),
                    float(risk_levels.get("entry_price", 0)),
                    float(risk_levels.get("stop_loss", 0)),
                    float(risk_levels.get("take_profit_1", 0)),
                    float(risk_levels.get("take_profit_2", 0)),
                    float(risk_levels.get("take_profit_3", 0)),
                    float(risk_levels.get("risk_reward_ratio", 0)),
                ]
                
                logger.info(f"Row data prepared: {len(row_data)} columns")
                
            except Exception as e:
                logger.error(f"Error preparing row data: {e}")
                return False

            # Append to worksheet
            logger.info("Appending row to worksheet...")
            worksheet.append_row(row_data)

            logger.info(f"Detailed signal logged successfully: {symbol} - {signal_type}")
            return True

        except Exception as e:
            logger.error(f"Error logging detailed signal to sheets: {e}")
            return False

    def log_trading_journal(self, analysis: Dict) -> bool:
        """
        Log tradeable signals to Trading_Journal worksheet
        
        Args:
            analysis: Analysis from SignalDetector
            
        Returns:
            bool: True if logged successfully
        """
        # Check connection status
        if not self._initialized or not self.spreadsheet:
            logger.warning("SheetsLogger not initialized, skipping trading journal log")
            return False

        try:
            signals = analysis.get("signals", {})
            
            # Check for tradeable signals
            if not self._has_tradeable_signal(signals):
                logger.debug(f"No tradeable signals found for {analysis.get('symbol', 'UNKNOWN')}")
                return False
            
            # Headers for Trading Journal
            headers = [
                "Date", "Symbol", "Signal", "Entry", "SL", 
                "TP1", "TP2", "TP3", "Win/Loss", "Win Rate"
            ]

            # Prepare worksheet (use main worksheet if available)
            worksheet = self.worksheet
            if not worksheet:
                worksheet = self._ensure_worksheet_exists("Trading_Journal", headers)
                if not worksheet:
                    logger.error("Failed to create/access Trading_Journal worksheet")
                    return False

            risk_levels = analysis.get("risk_levels", {})
            
            # Get trade direction
            trade_direction = self._get_trade_direction(signals)
            if not trade_direction:
                logger.debug(f"No clear trade direction for {analysis.get('symbol', 'UNKNOWN')}")
                return False
            
            # Check for duplicates before logging
            symbol = analysis.get("symbol", "")
            records = worksheet.get_all_records()
            today = datetime.now().strftime("%Y-%m-%d")

            for rec in records:
                if (rec.get("Date") == today and 
                    rec.get("Symbol") == symbol and 
                    rec.get("Signal") == trade_direction and
                    not rec.get("Win/Loss")):
                    logger.warning(f"Duplicate signal blocked: {symbol} {trade_direction}")
                    return False

            # Prepare row data
            row_data = [
                datetime.now().strftime("%Y-%m-%d"),
                analysis.get("symbol", ""),
                trade_direction,
                float(risk_levels.get("entry_price", 0)),
                float(risk_levels.get("stop_loss", 0)),
                float(risk_levels.get("take_profit_1", 0)),
                float(risk_levels.get("take_profit_2", 0)),
                float(risk_levels.get("take_profit_3", 0)),
                "",
                ""
            ]

            # Append to worksheet
            worksheet.append_row(row_data)
            logger.info(f"Trading journal logged: {analysis.get('symbol')} - {trade_direction} (Signal: {self._determine_signal_type(signals)})")
            return True

        except Exception as e:
            logger.error(f"Error logging trading journal: {e}")
            return False

    def log_tp_hit(self, position_data: Dict, tp_info: Dict) -> bool:
        """
        Log Take Profit hit to Google Sheets
        
        Args:
            position_data: Position information
            tp_info: TP hit information
            
        Returns:
            bool: True if logged successfully
        """
        if not self._initialized or not self.spreadsheet:
            logger.warning("SheetsLogger not initialized, skipping TP hit log")
            return False

        try:
            symbol = position_data.get("symbol", "")
            entry_price = position_data.get("entry_price", 0)
            tp_price = tp_info.get("target_price", 0)
            current_price = tp_info.get("price", 0)
            
            # Determine which TP was hit from the price
            tp_levels = position_data.get("tp_levels", {})
            tp_level = "TP1"  # Default
            
            for tp_name, tp_target in tp_levels.items():
                if abs(tp_target - tp_price) < 0.001:  # Account for floating point precision
                    tp_level = tp_name
                    break
            
            return self.update_trading_result(symbol, entry_price, f"take_profit_{tp_level[-1]}", current_price)

        except Exception as e:
            logger.error(f"Error logging TP hit: {e}")
            return False

    def log_sl_hit(self, position_data: Dict, sl_info: Dict) -> bool:
        """
        Log Stop Loss hit to Google Sheets
        
        Args:
            position_data: Position information
            sl_info: SL hit information
            
        Returns:
            bool: True if logged successfully
        """
        if not self._initialized or not self.spreadsheet:
            logger.warning("SheetsLogger not initialized, skipping SL hit log")
            return False

        try:
            symbol = position_data.get("symbol", "")
            entry_price = position_data.get("entry_price", 0)
            current_price = sl_info.get("price", 0)
            
            return self.update_trading_result(symbol, entry_price, "stop_loss", current_price)

        except Exception as e:
            logger.error(f"Error logging SL hit: {e}")
            return False

    def log_position_close(self, position_data: Dict) -> bool:
        """
        Log position closure to Google Sheets
        
        Args:
            position_data: Position information
            
        Returns:
            bool: True if logged successfully
        """
        if not self._initialized or not self.spreadsheet:
            logger.warning("SheetsLogger not initialized, skipping position close log")
            return False

        try:
            symbol = position_data.get("symbol", "")
            entry_price = position_data.get("entry_price", 0)
            close_reason = position_data.get("close_reason", "MANUAL")
            
            # Determine if it's a win or loss based on close reason
            if close_reason in ["ALL_TP_HIT", "TP3_HIT"]:
                result_type = "WIN"
            elif close_reason == "SL_HIT":
                result_type = "LOSS"
            else:
                result_type = "MANUAL_CLOSE"
            
            # Update the trading journal
            return self._update_position_status(symbol, entry_price, result_type)

        except Exception as e:
            logger.error(f"Error logging position close: {e}")
            return False

    def update_trading_result(self, symbol: str, entry_price: float, triggered_level: str, triggered_price: float) -> bool:
        """
        Update trading result with TP/SL marks
        
        Args:
            symbol: Trading symbol
            entry_price: Entry price to match
            triggered_level: Level that was triggered (e.g., "take_profit_1", "stop_loss")
            triggered_price: Price at which level was triggered
            
        Returns:
            bool: True if updated successfully
        """
        if not self._initialized or not self.spreadsheet:
            logger.warning("SheetsLogger not initialized, skipping result update")
            return False

        try:
            # Access Trading Journal worksheet - FIXED: use safe access
            worksheet = self.worksheet
            if not worksheet:
                logger.error("Cannot access Trading_Journal worksheet")
                return False

            records = worksheet.get_all_records()

            # Find matching row
            for i, record in enumerate(records, start=2):  # start=2 because row 1 is header
                if (record.get("Symbol") == symbol and 
                    abs(float(record.get("Entry", 0)) - entry_price) < 0.001 and  # Account for floating point precision
                    not record.get("Win/Loss")):  # Not yet updated
                    
                    # Update based on triggered level
                    if triggered_level == "stop_loss":
                        # Mark SL column (column E = 5)
                        current_sl = worksheet.cell(i, 5).value
                        worksheet.update_cell(i, 5, f"❌ {current_sl}")
                        worksheet.update_cell(i, 9, "LOSS")  # Win/Loss column
                        logger.info(f"Updated LOSS: {symbol} hit SL at {triggered_price}")
                        
                    elif triggered_level.startswith("take_profit"):
                        # Mark appropriate TP column
                        if triggered_level == "take_profit_1":
                            col = 6  # TP1 column
                        elif triggered_level == "take_profit_2":
                            col = 7  # TP2 column
                        elif triggered_level == "take_profit_3":
                            col = 8  # TP3 column
                        else:
                            continue
                        
                        current_tp = worksheet.cell(i, col).value
                        worksheet.update_cell(i, col, f"✅ {current_tp}")
                        worksheet.update_cell(i, 9, "WIN")  # Win/Loss column
                        logger.info(f"Updated WIN: {symbol} hit {triggered_level} at {triggered_price}")
                    
                    # Update Win Rate
                    self._update_win_rate(worksheet)
                    
                    logger.info(f"Trading result updated successfully: {symbol} - {triggered_level}")
                    return True
            
            logger.warning(f"No matching trade found for {symbol} at {entry_price}")
            return False

        except Exception as e:
            logger.error(f"Error updating trading result: {e}")
            return False

    def _update_position_status(self, symbol: str, entry_price: float, status: str) -> bool:
        """Update position status in trading journal"""
        try:
            worksheet = self.worksheet
            if not worksheet:
                logger.error("Cannot access Trading_Journal worksheet")
                return False

            records = worksheet.get_all_records()

            # Find matching row
            for i, record in enumerate(records, start=2):
                if (record.get("Symbol") == symbol and 
                    abs(float(record.get("Entry", 0)) - entry_price) < 0.001 and
                    not record.get("Win/Loss")):
                    
                    worksheet.update_cell(i, 9, status)  # Win/Loss column
                    self._update_win_rate(worksheet)
                    
                    logger.info(f"Updated position status: {symbol} - {status}")
                    return True
            
            return False

        except Exception as e:
            logger.error(f"Error updating position status: {e}")
            return False

    def _update_win_rate(self, worksheet):
        """Calculate and update Win Rate"""
        try:
            # Get all records
            records = worksheet.get_all_records()
            
            # Filter completed trades
            completed_trades = [r for r in records if r.get("Win/Loss") in ["WIN", "LOSS"]]
            
            if not completed_trades:
                logger.debug("No completed trades found for win rate calculation")
                return
            
            # Calculate Win Rate
            total = len(completed_trades)
            wins = len([r for r in completed_trades if r.get("Win/Loss") == "WIN"])
            win_rate = f"{round(wins / total * 100, 1)}%"
            
            logger.info(f"Win Rate calculated: {wins}/{total} = {win_rate}")
            
            # Update Win Rate in the last row with data
            for i in range(len(records), 1, -1):  # From bottom to top
                if records[i-2].get("Win/Loss"):  # i-2 because records start from 0
                    worksheet.update_cell(i, 10, win_rate)  # Win Rate column (column J = 10)
                    logger.info(f"Win Rate updated in row {i}: {win_rate}")
                    break
                    
        except Exception as e:
            logger.error(f"Error updating win rate: {e}")

    def test_connection(self) -> bool:
        """Test Google Sheets connection"""
        try:
            if not self.spreadsheet:
                logger.error("Spreadsheet object is None")
                return False

            title = self.spreadsheet.title
            worksheet_count = len(self.spreadsheet.worksheets())
            
            logger.info(f"Google Sheets connection test successful!")
            logger.info(f"  Spreadsheet: {title}")
            logger.info(f"  Worksheets: {worksheet_count}")
            logger.info(f"  URL: https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}")
            
            return True

        except Exception as e:
            logger.error(f"Google Sheets connection test failed: {e}")
            return False

    def get_trading_statistics(self, days: int = 30) -> Dict:
        """
        Generate trading statistics
        
        Args:
            days: Number of days to analyze (simplified - uses all data for now)
            
        Returns:
            Dict with trading statistics
        """
        if not self._initialized or not self.spreadsheet:
            return {}

        try:
            worksheet = self.worksheet
            if not worksheet:
                return {}

            records = worksheet.get_all_records()
            
            # Filter completed trades (simplified - use all for now)
            completed_trades = [r for r in records if r.get("Win/Loss") in ["WIN", "LOSS"]]
            
            if not completed_trades:
                return {"total_trades": 0, "win_rate": 0, "total_pnl": 0}
            
            # Calculate statistics
            total_trades = len(completed_trades)
            wins = len([r for r in completed_trades if r.get("Win/Loss") == "WIN"])
            win_rate = round(wins / total_trades * 100, 1) if total_trades > 0 else 0
            
            return {
                "total_trades": total_trades,
                "wins": wins,
                "losses": total_trades - wins,
                "win_rate": win_rate,
                "total_pnl": 0,  # TODO: Calculate from actual prices
                "best_performer": "",
                "worst_performer": "",
                "version": "2.0-refactored"
            }
            
        except Exception as e:
            logger.error(f"Error getting trading statistics: {e}")
            return {}

    def log_daily_summary(self, summary_data: Dict) -> bool:
        """
        Log daily summary to Google Sheets
        
        Args:
            summary_data: Summary data dictionary
            
        Returns:
            bool: True if logged successfully
        """
        if not self._initialized or not self.spreadsheet:
            return False

        try:
            headers = [
                "Date", "Total_Signals", "Active_Positions", "Closed_Positions", 
                "Total_PnL", "Win_Rate", "Best_Performer", "Worst_Performer", "Version"
            ]

            worksheet = self._ensure_worksheet_exists("Daily_Summary", headers)
            if not worksheet:
                return False

            row_data = [
                summary_data.get("date", ""),
                summary_data.get("total_signals", 0),
                summary_data.get("active_positions", 0),
                summary_data.get("closed_positions", 0),
                summary_data.get("total_pnl", 0),
                summary_data.get("win_rate", 0),
                summary_data.get("best_performer", ""),
                summary_data.get("worst_performer", ""),
                summary_data.get("version", "2.0-refactored"),
            ]

            worksheet.append_row(row_data)
            logger.info(f"Daily summary logged for {summary_data.get('date', 'today')}")
            return True

        except Exception as e:
            logger.error(f"Error logging daily summary: {e}")
            return False

    def log_position_update(self, update_data: Dict) -> bool:
        """
        Log position update information
        
        Args:
            update_data: Position update data
            
        Returns:
            bool: True if logged successfully
        """
        if not self._initialized or not self.spreadsheet:
            return False

        try:
            # Extract position and update information
            position = update_data.get("position", {})
            updates = update_data.get("updates", {})
            
            if not position or not updates:
                return False
            
            symbol = position.get("symbol", "")
            entry_price = position.get("entry_price", 0)
            
            # Process TP hits
            for tp_level in ['TP1', 'TP2', 'TP3']:
                tp_key = f'{tp_level}_hit'
                if updates.get(tp_key, {}).get('hit', False):
                    tp_info = updates[tp_key]
                    self.log_tp_hit(position, tp_info)
            
            # Process SL hits
            if updates.get('sl_hit', {}).get('hit', False):
                sl_info = updates['sl_hit']
                self.log_sl_hit(position, sl_info)
            
            # Process position closure
            if updates.get('position_closed', False):
                self.log_position_close(position)
            
            return True

        except Exception as e:
            logger.error(f"Error logging position update: {e}")

            return False

    def shutdown(self):
        """Shutdown SheetsLogger"""
        try:
            logger.info("Shutting down SheetsLogger v2.0...")
            # Clean up any resources if needed
            self._cached_worksheet = None
            logger.info("SheetsLogger shutdown complete")
        except Exception as e:
            logger.error(f"Error during SheetsLogger shutdown: {e}")
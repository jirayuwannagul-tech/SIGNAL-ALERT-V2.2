import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import pandas as pd

from ..utils.core_utils import JSONManager, ErrorHandler
from ..utils.data_types import DataConverter
try:
    from config.settings import RISK_MANAGEMENT
except ImportError:
    # Fallback if settings not available
    RISK_MANAGEMENT = {
        "4h": {"tp_levels": [3.0, 5.0, 7.0], "sl_level": 3.0},
        "1h": {"tp_levels": [2.0, 3.5, 5.0], "sl_level": 2.0},
        "1d": {"tp_levels": [5.0, 8.0, 12.0], "sl_level": 4.0}
    }

class PositionManager:
    """Centralized position management - รวม PositionTracker + PriceMonitor logic"""
    
    PRICE_TOLERANCE = 0.005  # 0.1% tolerance for TP/SL detection
    
    def __init__(self, data_manager):
        self.logger = logging.getLogger(__name__)
        self.json_manager = JSONManager()
        self.data_converter = DataConverter()
        self.data_manager = data_manager
        self.positions_file = "data/positions.json"
        self.positions = self._load_positions()
        
        self.logger.info("✅ PositionManager initialized")
    
    @ErrorHandler.service_error_handler("PositionManager")
    def create_position(self, signal_data: Dict) -> Optional[str]:
        """Create new position from signal"""
        try:
            symbol = signal_data['symbol']
            timeframe = signal_data['timeframe']
            direction = signal_data['direction']
            entry_price = signal_data['current_price']
            
            # Validate entry price
            if not self.data_converter.validate_price_data(entry_price):
                self.logger.error(f"Invalid entry price: {entry_price}")
                return None
            
            # Check price sanity (เทียบกับ cached price ถ้ามี)
            cached_price = self.data_manager.price_cache.get(symbol)
            if not self.validate_price_sanity(symbol, entry_price, cached_price):
                self.logger.error(f"Invalid entry price: {symbol} = {entry_price}")
                return None
            
            # Check for existing position
            position_id = f"{symbol}_{timeframe}_{direction}"
            if position_id in self.positions:
                existing = self.positions[position_id]
                if existing['status'] == 'ACTIVE':
                    self.logger.info(f"Position {position_id} already exists")
                    return None
            
            # Calculate TP/SL levels
            tp_levels, sl_level = self._calculate_levels(entry_price, direction, timeframe)
            
            position = {
                'id': position_id,
                'symbol': symbol,
                'timeframe': timeframe,
                'direction': direction,
                'entry_price': entry_price,
                'entry_time': datetime.now().isoformat(),
                'status': 'ACTIVE',
                'tp_levels': tp_levels,
                'sl_level': sl_level,
                'tp_hit': {'TP1': False, 'TP2': False, 'TP3': False},
                'sl_hit': False,
                'current_price': entry_price,
                'pnl_pct': 0.0,
                'signal_strength': signal_data.get('signal_strength', 0),
                'created_by': 'signal_detector',
                'last_update': datetime.now().isoformat()
            }
            
            # Sanitize data before saving
            position = self.data_converter.sanitize_signal_data(position)
            
            self.positions[position_id] = position
            self._save_positions()
            
            self.logger.info(f"✅ Created position: {position_id} at {entry_price}")
            return position_id
            
        except Exception as e:
            self.logger.error(f"Error creating position: {e}")
            return None
    
    @ErrorHandler.service_error_handler("PositionManager")
    def update_positions(self) -> Dict[str, Dict]:
        """Update all active positions with current prices"""
        updates = {}
        
        try:
            active_positions = {k: v for k, v in self.positions.items() 
                              if v['status'] == 'ACTIVE'}
            
            if not active_positions:
                return updates
            
            # Get current prices for all active symbols
            symbols = list(set([pos['symbol'] for pos in active_positions.values()]))
            current_prices = self.data_manager.get_current_prices_cached(symbols)
            
            for position_id, position in active_positions.items():
                symbol = position['symbol']
                current_price = current_prices.get(symbol)
                
                if current_price is None:
                    continue
                
                # Update position with current price
                old_price = position['current_price']
                position['current_price'] = current_price
                position['last_update'] = datetime.now().isoformat()
                
                # Calculate P&L
                entry_price = position['entry_price']
                direction = position['direction']
                
                if direction == 'LONG':
                    pnl_pct = ((current_price - entry_price) / entry_price) * 100
                else:  # SHORT
                    pnl_pct = ((entry_price - current_price) / entry_price) * 100
                
                position['pnl_pct'] = round(pnl_pct, 2)
                
                # Check TP/SL hits
                tp_sl_update = self._check_tp_sl_hits(position, old_price, current_price)
                if tp_sl_update:
                    updates[position_id] = tp_sl_update
            
            self._save_positions()
            
            if updates:
                self.logger.info(f"📊 Updated {len(updates)} positions with TP/SL hits")
            
            return updates
            
        except Exception as e:
            self.logger.error(f"Error updating positions: {e}")
            return {}
    
    def _check_tp_sl_hits(self, position: Dict, old_price: float, current_price: float) -> Optional[Dict]:
        """Check if TP/SL levels are hit"""
        direction = position['direction']
        tp_levels = position['tp_levels']
        sl_level = position['sl_level']
        updates = {}
        
        try:
            # Check TP hits
            for tp_name, tp_price in tp_levels.items():
                if not position['tp_hit'][tp_name]:
                    hit = False
                    
                    if direction == 'LONG':
                        tp_threshold = tp_price * (1 - self.PRICE_TOLERANCE)
                        hit = current_price >= tp_threshold
                    else:  # SHORT
                        tp_threshold = tp_price * (1 + self.PRICE_TOLERANCE)
                        hit = current_price <= tp_threshold
                    
                    if hit:
                        position['tp_hit'][tp_name] = True
                        updates[f'{tp_name}_hit'] = {
                            'hit': True,
                            'price': current_price,
                            'target_price': tp_price,
                            'timestamp': datetime.now().isoformat()
                        }
                        
                        self.logger.info(f"🎯 {tp_name} hit for {position['symbol']}: {current_price}")
                        
                        # Check if all TPs hit
                        if all(position['tp_hit'].values()):
                            position['status'] = 'CLOSED'
                            position['close_reason'] = 'ALL_TP_HIT'
                            position['close_time'] = datetime.now().isoformat()
                            updates['position_closed'] = True
            
            # Check SL hit
            if not position['sl_hit']:
                sl_hit = False
                
                if direction == 'LONG':
                    sl_threshold = sl_level * (1 + self.PRICE_TOLERANCE)
                    sl_hit = current_price <= sl_threshold
                else:  # SHORT
                    sl_threshold = sl_level * (1 - self.PRICE_TOLERANCE)
                    sl_hit = current_price >= sl_threshold
                
                if sl_hit:
                    position['sl_hit'] = True
                    position['status'] = 'CLOSED'
                    position['close_reason'] = 'SL_HIT'
                    position['close_time'] = datetime.now().isoformat()
                    updates['sl_hit'] = {
                        'hit': True,
                        'price': current_price,
                        'target_price': sl_level,
                        'timestamp': datetime.now().isoformat()
                    }
                    updates['position_closed'] = True
                    
                    self.logger.info(f"🛑 SL hit for {position['symbol']}: {current_price}")
            
            return updates if updates else None
            
        except Exception as e:
            self.logger.error(f"Error checking TP/SL hits: {e}")
            return None
    
    def _calculate_levels(self, entry_price: float, direction: str, timeframe: str) -> Tuple[Dict, float]:
        """Calculate TP and SL levels"""
        risk_config = RISK_MANAGEMENT.get(timeframe, RISK_MANAGEMENT['4h'])
        tp_percentages = risk_config['tp_levels']  # [3.0, 5.0, 7.0]
        sl_percentage = risk_config['sl_level']    # 3.0
        
        tp_levels = {}
        
        if direction == 'LONG':
            tp_levels['TP1'] = round(entry_price * (1 + tp_percentages[0] / 100), 8)
            tp_levels['TP2'] = round(entry_price * (1 + tp_percentages[1] / 100), 8)
            tp_levels['TP3'] = round(entry_price * (1 + tp_percentages[2] / 100), 8)
            sl_level = round(entry_price * (1 - sl_percentage / 100), 8)
        else:  # SHORT
            tp_levels['TP1'] = round(entry_price * (1 - tp_percentages[0] / 100), 8)
            tp_levels['TP2'] = round(entry_price * (1 - tp_percentages[1] / 100), 8)
            tp_levels['TP3'] = round(entry_price * (1 - tp_percentages[2] / 100), 8)
            sl_level = round(entry_price * (1 + sl_percentage / 100), 8)
        
        return tp_levels, sl_level
    
    def get_active_positions(self) -> Dict:
        """Get all active positions"""
        return {k: v for k, v in self.positions.items() if v['status'] == 'ACTIVE'}
    
    def get_position_status(self, symbol: str, timeframe: str) -> Optional[Dict]:
        """Get position status for symbol/timeframe"""
        for position in self.positions.values():
            if (position['symbol'] == symbol and 
                position['timeframe'] == timeframe and 
                position['status'] == 'ACTIVE'):
                return position
        return None
    
    @ErrorHandler.service_error_handler("PositionManager")
    def close_position(self, position_id: str, reason: str = 'MANUAL') -> bool:
        """Manually close a position"""
        try:
            if position_id in self.positions:
                self.positions[position_id]['status'] = 'CLOSED'
                self.positions[position_id]['close_reason'] = reason
                self.positions[position_id]['close_time'] = datetime.now().isoformat()
                self._save_positions()
                self.logger.info(f"🔒 Closed position {position_id}: {reason}")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error closing position: {e}")
            return False
    
    def get_positions_summary(self) -> Dict:
        """Get positions summary statistics"""
        all_positions = self.positions
        active_positions = self.get_active_positions()
        closed_positions = [pos for pos in all_positions.values() if pos['status'] == 'CLOSED']
        
        # Calculate P&L stats
        total_pnl = sum(pos.get('pnl_pct', 0) for pos in active_positions.values())
        wins = len([pos for pos in closed_positions if pos.get('pnl_pct', 0) > 0])
        losses = len([pos for pos in closed_positions if pos.get('pnl_pct', 0) < 0])
        win_rate = (wins / len(closed_positions) * 100) if closed_positions else 0
        
        return {
            'total_positions': len(all_positions),
            'active_positions': len(active_positions),
            'closed_positions': len(closed_positions),
            'total_pnl_pct': round(total_pnl, 2),
            'win_rate_pct': round(win_rate, 2),
            'wins': wins,
            'losses': losses
        }
    
    def _load_positions(self) -> Dict:
        """Load positions from JSON file"""
        positions = self.json_manager.load_json(self.positions_file, {})
        self.logger.info(f"📂 Loaded {len(positions)} positions")
        return positions
    
    def _save_positions(self):
        """Save positions to JSON file"""
        success = self.json_manager.save_json(self.positions, self.positions_file)
        if not success:
            self.logger.error("❌ Failed to save positions")
    
    def cleanup_old_positions(self, days_old: int = 30):
        """Clean up old closed positions"""
        try:
            cutoff_date = datetime.now().timestamp() - (days_old * 24 * 60 * 60)
            
            positions_to_remove = []
            for pos_id, position in self.positions.items():
                if position['status'] == 'CLOSED':
                    close_time = position.get('close_time')
                    if close_time:
                        close_timestamp = pd.to_datetime(close_time).timestamp()
                        if close_timestamp < cutoff_date:
                            positions_to_remove.append(pos_id)
            
            for pos_id in positions_to_remove:
                del self.positions[pos_id]
            
            if positions_to_remove:
                self._save_positions()
                self.logger.info(f"🧹 Cleaned up {len(positions_to_remove)} old positions")
            
        except Exception as e:
            self.logger.error(f"Error cleaning up positions: {e}")
    
    def validate_price_sanity(self, symbol: str, price: float, previous_price: float = None) -> bool:
        """Check if price is within reasonable range"""

        # Check zero or negative
        if price <= 0:
            self.logger.error(f"INVALID PRICE: {symbol} = {price} (zero or negative)")
            return False

        # Check percentage change if we have previous price
        if previous_price and previous_price > 0:
            pct_change = abs((price - previous_price) / previous_price * 100)
            if pct_change > 30:
                self.logger.error(
                    f"SUSPICIOUS PRICE CHANGE: {symbol} {previous_price} -> {price} ({pct_change:.1f}%)"
                )
                return False

        return True

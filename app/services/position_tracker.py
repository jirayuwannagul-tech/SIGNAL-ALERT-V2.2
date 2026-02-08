"""Position tracking service to manage active trades and prevent duplicate signals."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class Position:
    """Individual position data structure."""

    def __init__(
        self,
        symbol: str,
        timeframe: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        take_profits: List[float],
        timestamp: str = None,
    ):
        """
        Initialize a new position.

        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT')
            timeframe: Position timeframe ('1h', '1d')
            direction: 'LONG' or 'SHORT'
            entry_price: Entry price level
            stop_loss: Stop loss price level
            take_profits: List of take profit levels
            timestamp: Position creation timestamp
        """
        self.symbol = symbol
        self.timeframe = timeframe
        self.direction = direction
        self.entry_price = entry_price
        self.stop_loss = stop_loss
        self.take_profits = take_profits
        self.timestamp = timestamp or datetime.now().isoformat()
        self.status = "ACTIVE"
        self.hit_tps = []  # Track which TPs have been hit
        self.current_pnl = 0.0
        self.max_pnl = 0.0
        self.min_pnl = 0.0

    def to_dict(self) -> Dict:
        """Convert position to dictionary."""
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profits": self.take_profits,
            "timestamp": self.timestamp,
            "status": self.status,
            "hit_tps": self.hit_tps,
            "current_pnl": self.current_pnl,
            "max_pnl": self.max_pnl,
            "min_pnl": self.min_pnl,
        }

    @classmethod
    def from_dict(cls, data: Dict):
        """Create position from dictionary."""
        position = cls(
            symbol=data["symbol"],
            timeframe=data["timeframe"],
            direction=data["direction"],
            entry_price=data["entry_price"],
            stop_loss=data["stop_loss"],
            take_profits=data["take_profits"],
            timestamp=data["timestamp"],
        )
        position.status = data.get("status", "ACTIVE")
        position.hit_tps = data.get("hit_tps", [])
        position.current_pnl = data.get("current_pnl", 0.0)
        position.max_pnl = data.get("max_pnl", 0.0)
        position.min_pnl = data.get("min_pnl", 0.0)
        return position

    def update_pnl(self, current_price: float) -> float:
        """Update P&L based on current price."""
        if self.direction == "LONG":
            pnl_percent = ((current_price - self.entry_price) / self.entry_price) * 100
        else:  # SHORT
            pnl_percent = ((self.entry_price - current_price) / self.entry_price) * 100

        self.current_pnl = pnl_percent
        self.max_pnl = max(self.max_pnl, pnl_percent)
        self.min_pnl = min(self.min_pnl, pnl_percent)

        return pnl_percent


class PositionTracker:
    """Track active positions and manage entry/exit logic."""

    def __init__(self, positions_file: str = "data/positions.json"):
        """
        Initialize position tracker.

        Args:
            positions_file: Path to JSON file for storing positions
        """
        self.positions_file = Path(positions_file)
        self.positions: Dict[str, Position] = {}

        # Ensure data directory exists
        self.positions_file.parent.mkdir(parents=True, exist_ok=True)

        # Load existing positions
        self.load_positions()

    def load_positions(self) -> None:
        """Load positions from file."""
        try:
            if self.positions_file.exists():
                with open(self.positions_file, "r") as f:
                    data = json.load(f)

                for key, pos_data in data.items():
                    self.positions[key] = Position.from_dict(pos_data)

                logger.info(f"Loaded {len(self.positions)} positions from file")
            else:
                logger.info("No existing positions file found, starting fresh")

        except Exception as e:
            logger.error(f"Error loading positions: {e}")
            self.positions = {}

    def save_positions(self) -> None:
        """Save positions to file."""
        try:
            data = {}
            for key, position in self.positions.items():
                data[key] = position.to_dict()

            with open(self.positions_file, "w") as f:
                json.dump(data, f, indent=2, default=str)

            logger.debug(f"Saved {len(self.positions)} positions to file")

        except Exception as e:
            logger.error(f"Error saving positions: {e}")

    def get_position_key(self, symbol: str, timeframe: str) -> str:
        """Generate unique key for position."""
        return f"{symbol}_{timeframe}"

    def has_active_position(self, symbol: str, timeframe: str) -> bool:
        """Check if there's an active position for symbol/timeframe."""
        key = self.get_position_key(symbol, timeframe)
        return key in self.positions and self.positions[key].status == "ACTIVE"

    def get_position(self, symbol: str, timeframe: str) -> Optional[Position]:
        """Get position for symbol/timeframe."""
        key = self.get_position_key(symbol, timeframe)
        return self.positions.get(key)

    def create_position(
        self,
        symbol: str,
        timeframe: str,
        direction: str,
        entry_price: float,
        risk_levels: Dict,
    ) -> Position:
        """
        Create new position.

        Args:
            symbol: Trading symbol
            timeframe: Position timeframe
            direction: 'LONG' or 'SHORT'
            entry_price: Entry price
            risk_levels: Risk management levels from signal analysis

        Returns:
            Created Position object
        """
        try:
            key = self.get_position_key(symbol, timeframe)

            # Close any existing position first
            if key in self.positions:
                self.close_position(symbol, timeframe, "REPLACED")

            # Extract TP/SL levels
            stop_loss = risk_levels.get("stop_loss", entry_price)
            take_profits = [
                risk_levels.get("take_profit_1", entry_price),
                risk_levels.get("take_profit_2", entry_price),
                risk_levels.get("take_profit_3", entry_price),
            ]

            # Create new position
            position = Position(
                symbol=symbol,
                timeframe=timeframe,
                direction=direction,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profits=take_profits,
            )

            self.positions[key] = position
            self.save_positions()

            logger.info(
                f"Created {direction} position for {symbol} {timeframe} at {entry_price}"
            )
            return position

        except Exception as e:
            logger.error(f"Error creating position: {e}")
            raise

    def close_position(
        self, symbol: str, timeframe: str, reason: str = "MANUAL"
    ) -> Optional[Position]:
        """
        Close position.

        Args:
            symbol: Trading symbol
            timeframe: Position timeframe
            reason: Closure reason (SL, TP1, TP2, TP3, MANUAL, etc.)

        Returns:
            Closed Position object or None if not found
        """
        try:
            key = self.get_position_key(symbol, timeframe)

            if key in self.positions:
                position = self.positions[key]
                position.status = f"CLOSED_{reason}"

                # Remove from active positions
                del self.positions[key]
                self.save_positions()

                logger.info(
                    f"Closed {position.direction} position for {symbol} {timeframe} - {reason}"
                )
                return position

            return None

        except Exception as e:
            logger.error(f"Error closing position: {e}")
            return None

    def update_position_tracking(
        self, symbol: str, timeframe: str, current_price: float
    ) -> Dict:
        """
        🔧 FIXED: Update position tracking and check for TP/SL hits.
        แก้ไขปัญหา TP2 ไม่ติ๊กโดยการเช็คทุก TP levels พร้อมกัน

        Args:
            symbol: Trading symbol
            timeframe: Position timeframe
            current_price: Current market price

        Returns:
            Dict with tracking results and any triggered levels
        """
        try:
            key = self.get_position_key(symbol, timeframe)

            if key not in self.positions:
                return {"status": "NO_POSITION"}

            position = self.positions[key]

            if position.status != "ACTIVE":
                return {"status": "INACTIVE_POSITION"}

            # Update P&L
            pnl_percent = position.update_pnl(current_price)

            result = {
                "status": "TRACKING",
                "symbol": symbol,
                "timeframe": timeframe,
                "direction": position.direction,
                "entry_price": position.entry_price,
                "current_price": current_price,
                "pnl_percent": pnl_percent,
                "triggered_levels": [],
            }

            # ✅ Check for Stop Loss hit FIRST
            sl_hit = False
            if position.direction == "LONG":
                sl_hit = current_price <= position.stop_loss
            else:  # SHORT
                sl_hit = current_price >= position.stop_loss
            
            if sl_hit:
                self.close_position(symbol, timeframe, "SL")
                result["triggered_levels"].append(
                    {"type": "SL", "price": position.stop_loss}
                )
                result["final_pnl"] = pnl_percent
                logger.info(f"{symbol} STOP LOSS hit at {current_price}")
                return result

            # 🎯 FIXED: Check ALL TP levels simultaneously
            new_tp_hits = []  # เก็บ TP ที่ hit ใหม่ในรอบนี้
            
            for i, tp_price in enumerate(position.take_profits, 1):
                tp_key = f"TP{i}"
                
                # ตรวจสอบว่า TP นี้ hit แล้วหรือยัง
                if tp_key not in position.hit_tps:
                    tp_hit = False
                    
                    if position.direction == "LONG":
                        tp_hit = current_price >= tp_price
                    else:  # SHORT
                        tp_hit = current_price <= tp_price
                    
                    if tp_hit:
                        new_tp_hits.append({
                            "key": tp_key,
                            "price": tp_price,
                            "level": i
                        })

            # 📝 Process new TP hits in order
            if new_tp_hits:
                # เรียงตามระดับ (TP1, TP2, TP3)
                new_tp_hits.sort(key=lambda x: x["level"])
                
                for tp_hit in new_tp_hits:
                    tp_key = tp_hit["key"]
                    tp_price = tp_hit["price"]
                    
                    # เพิ่มใน hit_tps
                    position.hit_tps.append(tp_key)
                    
                    # เพิ่มใน result
                    result["triggered_levels"].append({
                        "type": tp_key,
                        "price": tp_price,
                        "pnl_percent": pnl_percent,
                    })
                    
                    logger.info(f"🎯 {symbol} {tp_key} HIT at {current_price} (target: {tp_price})")

            # 🔄 เรียงลำดับ hit_tps ให้ถูกต้อง
            if position.hit_tps:
                position.hit_tps.sort(key=lambda x: int(x[2:]))

            # ✅ Close position on TP3 hit
            if "TP3" in position.hit_tps:
                self.close_position(symbol, timeframe, "TP3")
                result["final_pnl"] = pnl_percent
                logger.info(f"🏁 {symbol} position CLOSED on TP3")

            # 💾 Save updated position
            if position.status == "ACTIVE":
                self.save_positions()

            return result

        except Exception as e:
            logger.error(f"❌ Error updating position tracking: {e}")
            return {"status": "ERROR", "error": str(e)}

    def get_position_status(self, symbol: str, timeframe: str) -> Dict:
        """
        🔍 NEW: Get detailed status of specific position
        ใช้สำหรับ debug และตรวจสอบ TP levels
        """
        try:
            key = self.get_position_key(symbol, timeframe)
            
            if key not in self.positions:
                return {"status": "NO_POSITION", "symbol": symbol, "timeframe": timeframe}
            
            position = self.positions[key]
            
            return {
                "status": position.status,
                "symbol": symbol,
                "timeframe": timeframe,
                "direction": position.direction,
                "entry_price": position.entry_price,
                "current_pnl": position.current_pnl,
                "max_pnl": position.max_pnl,
                "min_pnl": position.min_pnl,
                "stop_loss": position.stop_loss,
                "take_profits": {
                    "TP1": position.take_profits[0] if len(position.take_profits) > 0 else None,
                    "TP2": position.take_profits[1] if len(position.take_profits) > 1 else None,
                    "TP3": position.take_profits[2] if len(position.take_profits) > 2 else None,
                },
                "hit_tps": position.hit_tps,
                "timestamp": position.timestamp,
            }
            
        except Exception as e:
            logger.error(f"Error getting position status: {e}")
            return {"status": "ERROR", "error": str(e)}

    def force_check_tp_levels(self, symbol: str, timeframe: str, current_price: float) -> Dict:
        """
        🚨 NEW: Force check TP levels for debugging
        ใช้เมื่อต้องการตรวจสอบว่าทำไม TP ไม่ติ๊ก
        """
        try:
            position = self.get_position(symbol, timeframe)
            
            if not position:
                return {"error": "No position found"}
            
            result = {
                "symbol": symbol,
                "current_price": current_price,
                "entry_price": position.entry_price,
                "direction": position.direction,
                "hit_tps": position.hit_tps,
                "tp_analysis": {}
            }
            
            # วิเคราะห์แต่ละ TP level
            for i, tp_price in enumerate(position.take_profits, 1):
                tp_key = f"TP{i}"
                already_hit = tp_key in position.hit_tps
                
                if position.direction == "LONG":
                    should_hit = current_price >= tp_price
                    distance = current_price - tp_price
                else:  # SHORT
                    should_hit = current_price <= tp_price
                    distance = tp_price - current_price
                
                result["tp_analysis"][tp_key] = {
                    "target_price": tp_price,
                    "already_hit": already_hit,
                    "should_hit_now": should_hit,
                    "price_distance": distance,
                    "hit_condition": f"current_price {'≥' if position.direction == 'LONG' else '≤'} {tp_price}"
                }
            
            return result
            
        except Exception as e:
            logger.error(f"Error in force TP check: {e}")
            return {"error": str(e)}

    def get_all_active_positions(self) -> List[Position]:
        """Get all active positions."""
        return [pos for pos in self.positions.values() if pos.status == "ACTIVE"]

    def get_position_summary(self) -> Dict:
        """Get summary of all positions."""
        active_positions = self.get_all_active_positions()

        summary = {
            "total_active": len(active_positions),
            "by_timeframe": {},
            "by_direction": {"LONG": 0, "SHORT": 0},
            "positions": [],
        }

        for position in active_positions:
            # Count by timeframe
            tf = position.timeframe
            summary["by_timeframe"][tf] = summary["by_timeframe"].get(tf, 0) + 1

            # Count by direction
            summary["by_direction"][position.direction] += 1

            # Add position info
            summary["positions"].append(
                {
                    "symbol": position.symbol,
                    "timeframe": position.timeframe,
                    "direction": position.direction,
                    "entry_price": position.entry_price,
                    "current_pnl": position.current_pnl,
                    "max_pnl": position.max_pnl,
                    "min_pnl": position.min_pnl,
                    "hit_tps": position.hit_tps,
                    "timestamp": position.timestamp,
                }
            )

        return summary

    def cleanup_old_positions(self, days: int = 7) -> int:
        """
        Clean up old inactive positions.

        Args:
            days: Remove positions older than this many days

        Returns:
            Number of positions cleaned up
        """
        try:
            from datetime import datetime, timedelta

            cutoff_date = datetime.now() - timedelta(days=days)
            positions_to_remove = []

            for key, position in self.positions.items():
                if position.status != "ACTIVE":
                    pos_date = datetime.fromisoformat(
                        position.timestamp.replace("Z", "+00:00")
                    )
                    if pos_date < cutoff_date:
                        positions_to_remove.append(key)

            for key in positions_to_remove:
                del self.positions[key]

            if positions_to_remove:
                self.save_positions()
                logger.info(f"Cleaned up {len(positions_to_remove)} old positions")

            return len(positions_to_remove)

        except Exception as e:
            logger.error(f"Error cleaning up positions: {e}")
            return 0
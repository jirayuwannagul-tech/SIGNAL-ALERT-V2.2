# app/utils/pnl_utils.py

def calculate_pnl_pct(direction: str, entry: float, current: float) -> float:
    """
    คำนวณ PnL เป็น %
    LONG : (current - entry) / entry * 100
    SHORT: (entry - current) / entry * 100
    """
    try:
        entry = float(entry)
        current = float(current)
        if entry <= 0:
            return 0.0

        if direction.upper() == "LONG":
            return ((current - entry) / entry) * 100
        else:
            return ((entry - current) / entry) * 100
    except Exception:
        return 0.0

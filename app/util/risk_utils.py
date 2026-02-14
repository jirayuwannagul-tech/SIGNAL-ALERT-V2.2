class RiskCalculator:
    """
    Centralized TP/SL & Risk Level Calculator
    """

    @staticmethod
    def calculate_levels(entry: float, direction: str, sl_pct: float, tp_levels: list):
        """
        entry      : ราคาเข้า
        direction  : LONG / SHORT
        sl_pct     : % SL เช่น 3 = 3%
        tp_levels  : [3,5,7] = %

        return dict {stop_loss, take_profit_1..3}
        """

        if not entry or entry <= 0:
            return {}

        direction = direction.upper()

        if direction == "LONG":
            sl = entry * (1 - sl_pct / 100)
            tps = [entry * (1 + p / 100) for p in tp_levels]
        else:  # SHORT
            sl = entry * (1 + sl_pct / 100)
            tps = [entry * (1 - p / 100) for p in tp_levels]

        return {
            "entry_price": entry,
            "stop_loss": round(sl, 6),
            "take_profit_1": round(tps[0], 6),
            "take_profit_2": round(tps[1], 6),
            "take_profit_3": round(tps[2], 6),
        }
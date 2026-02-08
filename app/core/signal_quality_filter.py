"""
Signal Quality Filter - Enhanced version for 65-70% Win Rate
ระบบกรองสัญญาณเพื่อให้เหลือแค่สัญญาณคุณภาพสูง
"""

import logging
from typing import Dict, Tuple
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class SignalQualityFilter:
    """
    กรองสัญญาณให้เหลือแค่คุณภาพสูง 65-70%
    
    Scoring System (0-100):
    - Squeeze Quality: 0-25 points
    - MACD Quality: 0-25 points
    - Trend Strength: 0-25 points
    - RSI Quality: 0-15 points
    - Volume Confirmation: 0-10 points
    """
    
    def __init__(self, min_quality_score: float = 75.0):
        """
        Initialize Signal Quality Filter
        
        Args:
            min_quality_score: คะแนนขั้นต่ำที่ยอมรับ (0-100)
                             75 = Very Good (แนะนำ)
                             85 = Excellent (เข้มงวดมาก)
        """
        self.min_quality_score = min_quality_score
        logger.info(f"✅ SignalQualityFilter initialized (min score: {min_quality_score})")
    
    def calculate_quality_score(
        self, 
        analysis: Dict, 
        signals: Dict,
        df: pd.DataFrame
    ) -> Tuple[float, Dict]:
        """
        คำนวณคะแนนคุณภาพสัญญาณ (0-100)
        
        Args:
            analysis: Analysis result from TechnicalIndicators
            signals: Signal dictionary from SignalDetector
            df: Price DataFrame
            
        Returns:
            (quality_score, details_dict)
        """
        score = 0.0
        details = {}
        
        try:
            # ========================================
            # 1️⃣ Squeeze Quality (0-25 points)
            # ========================================
            squeeze_score = self._score_squeeze_quality(analysis, details)
            score += squeeze_score
            
            # ========================================
            # 2️⃣ MACD Quality (0-25 points)
            # ========================================
            macd_score = self._score_macd_quality(analysis, signals, details)
            score += macd_score
            
            # ========================================
            # 3️⃣ Trend Strength (0-25 points)
            # ========================================
            trend_score = self._calculate_trend_strength(df, signals)
            score += trend_score
            details["trend_strength_score"] = trend_score
            
            # ========================================
            # 4️⃣ RSI Quality (0-15 points)
            # ========================================
            rsi_score = self._score_rsi_quality(analysis, signals, details)
            score += rsi_score
            
            # ========================================
            # 5️⃣ Volume Confirmation (0-10 points)
            # ========================================
            volume_score = self._check_volume_confirmation(df)
            score += volume_score
            details["volume_score"] = volume_score
            
            # ========================================
            # 📊 Final Score & Grade
            # ========================================
            score = min(score, 100.0)  # Cap at 100
            details["final_score"] = score
            details["grade"] = self._get_grade(score)
            
            return score, details
            
        except Exception as e:
            logger.error(f"Error calculating quality score: {e}")
            return 0.0, {"error": str(e)}
    
    def _score_squeeze_quality(self, analysis: Dict, details: Dict) -> float:
        """Score Squeeze indicator quality (0-25)"""
        try:
            squeeze = analysis.get("squeeze", {})
            score = 0.0
            
            if squeeze.get("squeeze_off"):
                score += 15  # Base score
                details["squeeze_breakout"] = True
                
                # Bonus: Squeeze intensity
                squeeze_details = squeeze.get("details", {})
                intensity = squeeze_details.get("squeeze_intensity", 1.0)
                
                if intensity < 0.8:
                    score += 10
                    details["strong_squeeze"] = True
                elif intensity < 0.9:
                    score += 5
                    details["moderate_squeeze"] = True
            else:
                details["squeeze_breakout"] = False
            
            return score
            
        except Exception as e:
            logger.error(f"Error scoring squeeze: {e}")
            return 0.0
    
    def _score_macd_quality(self, analysis: Dict, signals: Dict, details: Dict) -> float:
        """Score MACD quality (0-25)"""
        try:
            macd = analysis.get("macd", {})
            macd_cross = macd.get("cross_direction", "NONE")
            macd_details = macd.get("details", {})
            score = 0.0
            
            if macd_cross in ["UP", "DOWN"]:
                score += 10  # Base score
                details["macd_cross"] = macd_cross
                
                # Bonus 1: Histogram alignment
                histogram = macd_details.get("histogram", 0)
                if (signals.get("buy") and histogram > 0) or \
                   (signals.get("short") and histogram < 0):
                    score += 8
                    details["macd_histogram_aligned"] = True
                
                # Bonus 2: Zero line alignment
                macd_above_zero = macd_details.get("macd_above_zero", False)
                if (signals.get("buy") and macd_above_zero) or \
                   (signals.get("short") and not macd_above_zero):
                    score += 7
                    details["macd_zero_line_aligned"] = True
            
            return score
            
        except Exception as e:
            logger.error(f"Error scoring MACD: {e}")
            return 0.0
    
    def _calculate_trend_strength(self, df: pd.DataFrame, signals: Dict) -> float:
        """
        คำนวณความแรงของ trend (0-25)
        ใช้ MA20, MA50
        """
        try:
            close = df['close']
            
            # Calculate MAs
            ma_20 = close.rolling(20).mean()
            ma_50 = close.rolling(50).mean() if len(close) >= 50 else None
            
            current_price = close.iloc[-1]
            ma_20_current = ma_20.iloc[-1]
            
            score = 0.0
            
            # Check 1: Price vs MA20 distance
            price_ma20_distance = abs(current_price - ma_20_current) / ma_20_current * 100
            
            if signals.get("buy"):
                if current_price > ma_20_current:
                    score += 8
                    if price_ma20_distance < 2.0:
                        score += 4
                else:
                    return 0.0  # Price below MA20 = reject
            
            elif signals.get("short"):
                if current_price < ma_20_current:
                    score += 8
                    if price_ma20_distance < 2.0:
                        score += 4
                else:
                    return 0.0  # Price above MA20 = reject
            
            # Check 2: MA20 vs MA50 alignment
            if ma_50 is not None:
                ma_50_current = ma_50.iloc[-1]
                ma_distance = abs(ma_20_current - ma_50_current) / ma_50_current * 100
                
                if signals.get("buy") and ma_20_current > ma_50_current:
                    score += 8
                    if ma_distance > 1.0:
                        score += 5
                
                elif signals.get("short") and ma_20_current < ma_50_current:
                    score += 8
                    if ma_distance > 1.0:
                        score += 5
            else:
                score += 5  # Partial credit
            
            return min(score, 25.0)
            
        except Exception as e:
            logger.error(f"Error calculating trend strength: {e}")
            return 0.0
    
    def _score_rsi_quality(self, analysis: Dict, signals: Dict, details: Dict) -> float:
        """Score RSI quality (0-15)"""
        try:
            rsi = analysis.get("rsi", {})
            rsi_value = rsi.get("value", 50)
            rsi_details = rsi.get("details", {})
            score = 0.0
            
            # LONG: RSI 35-50 optimal
            if signals.get("buy"):
                if 35 <= rsi_value <= 50:
                    score += 15
                    details["rsi_optimal"] = True
                elif 30 <= rsi_value <= 60:
                    score += 10
                    details["rsi_acceptable"] = True
                else:
                    score += 5
                    details["rsi_marginal"] = True
            
            # SHORT: RSI 55-70 optimal
            elif signals.get("short"):
                if 55 <= rsi_value <= 70:
                    score += 15
                    details["rsi_optimal"] = True
                elif 45 <= rsi_value <= 75:
                    score += 10
                    details["rsi_acceptable"] = True
                else:
                    score += 5
                    details["rsi_marginal"] = True
            
            # Bonus: RSI trend alignment
            rsi_trend = rsi_details.get("rsi_trend", "NEUTRAL")
            if (signals.get("buy") and rsi_trend == "RISING") or \
               (signals.get("short") and rsi_trend == "FALLING"):
                score += 5
                details["rsi_trend_aligned"] = True
            
            return min(score, 15.0)
            
        except Exception as e:
            logger.error(f"Error scoring RSI: {e}")
            return 0.0
    
    def _check_volume_confirmation(self, df: pd.DataFrame) -> float:
        """Check volume confirmation (0-10)"""
        try:
            volume = df['volume']
            vol_ma_20 = volume.rolling(20).mean()
            
            current_vol = volume.iloc[-1]
            avg_vol = vol_ma_20.iloc[-1]
            
            vol_ratio = current_vol / avg_vol if avg_vol > 0 else 1.0
            
            if vol_ratio >= 1.5:
                return 10.0
            elif vol_ratio >= 1.2:
                return 8.0
            elif vol_ratio >= 0.9:
                return 5.0
            else:
                return 2.0
            
        except Exception as e:
            logger.error(f"Error checking volume: {e}")
            return 5.0
    
    def _get_grade(self, score: float) -> str:
        """Get grade from score"""
        if score >= 85:
            return "EXCELLENT"
        elif score >= 75:
            return "VERY GOOD"
        elif score >= 65:
            return "GOOD"
        elif score >= 50:
            return "AVERAGE"
        else:
            return "POOR"
    
    def should_take_signal(
        self, 
        analysis: Dict, 
        signals: Dict,
        df: pd.DataFrame
    ) -> Tuple[bool, float, Dict]:
        """
        ตัดสินใจว่าควร entry หรือไม่
        
        Args:
            analysis: Analysis from TechnicalIndicators
            signals: Signals from SignalDetector
            df: Price DataFrame
            
        Returns:
            (should_take, quality_score, details)
        """
        try:
            # Calculate quality score
            quality_score, details = self.calculate_quality_score(analysis, signals, df)
            
            # Decision
            should_take = quality_score >= self.min_quality_score
            
            if should_take:
                logger.info(
                    f"✅ SIGNAL ACCEPTED: Score {quality_score:.1f} "
                    f"(Grade: {details.get('grade')})"
                )
            else:
                logger.debug(
                    f"❌ SIGNAL REJECTED: Score {quality_score:.1f} < "
                    f"Min {self.min_quality_score} "
                    f"(Grade: {details.get('grade')})"
                )
            
            return should_take, quality_score, details
            
        except Exception as e:
            logger.error(f"Error in should_take_signal: {e}")
            return False, 0.0, {"error": str(e)}


# ========================================
# 🧪 Testing Functions
# ========================================

def test_quality_filter():
    """ทดสอบ Quality Filter"""
    print("\n" + "="*60)
    print("🧪 Testing SignalQualityFilter")
    print("="*60)
    
    # Create mock data
    dates = pd.date_range('2025-01-01', periods=100, freq='4h')
    
    # Uptrend scenario
    prices_up = pd.Series([100 + i*0.5 for i in range(100)])
    df_up = pd.DataFrame({
        'close': prices_up,
        'high': prices_up * 1.01,
        'low': prices_up * 0.99,
        'open': prices_up,
        'volume': [1000000 * (1 + np.random.random()*0.5) for _ in range(100)]
    }, index=dates)
    
    # Mock analysis
    mock_analysis = {
        "squeeze": {
            "squeeze_off": True,
            "momentum_direction": "UP",
            "details": {"squeeze_intensity": 0.75}
        },
        "macd": {
            "cross_direction": "UP",
            "details": {
                "histogram": 0.05,
                "macd_above_zero": True
            }
        },
        "rsi": {
            "value": 45,
            "extreme_level": "NORMAL",
            "details": {"rsi_trend": "RISING"}
        }
    }
    
    mock_signals = {"buy": True, "short": False}
    
    # Test filter
    quality_filter = SignalQualityFilter(min_quality_score=75.0)
    should_take, score, details = quality_filter.should_take_signal(
        mock_analysis, mock_signals, df_up
    )
    
    print(f"\n📊 Test Results:")
    print(f"Should Take Signal: {'✅ YES' if should_take else '❌ NO'}")
    print(f"Quality Score: {score:.1f}/100")
    print(f"Grade: {details.get('grade')}")
    print(f"\nScore Breakdown:")
    print(f"  - Squeeze: {'✅' if details.get('squeeze_breakout') else '❌'}")
    print(f"  - MACD Cross: {details.get('macd_cross', 'N/A')}")
    print(f"  - Trend Strength: {details.get('trend_strength_score', 0):.1f}")
    print(f"  - RSI Optimal: {'✅' if details.get('rsi_optimal') else '❌'}")
    print(f"  - Volume: {details.get('volume_score', 0):.1f}")
    
    print("\n" + "="*60)


if __name__ == "__main__":
    test_quality_filter()

import numpy as np
from typing import Any, Dict, List
import pandas as pd

class DataConverter:
    """Centralized data type conversion utilities"""
    
    @staticmethod
    def convert_numpy_types(data: Any) -> Any:
        """Convert numpy types to Python native types"""
        if isinstance(data, np.integer):
            return int(data)
        elif isinstance(data, np.floating):
            return float(data)
        elif isinstance(data, np.bool_):
            return bool(data)
        elif isinstance(data, np.ndarray):
            return data.tolist()
        elif isinstance(data, dict):
            return {k: DataConverter.convert_numpy_types(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [DataConverter.convert_numpy_types(item) for item in data]
        else:
            return data
    
    @staticmethod
    def validate_dataframe(df: pd.DataFrame, min_rows: int = 50) -> bool:
        """Validate DataFrame for technical analysis"""
        if df is None or df.empty:
            return False
        
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        if not all(col in df.columns for col in required_columns):
            return False
            
        if len(df) < min_rows:
            return False
            
        # Check for null values
        if df[required_columns].isnull().any().any():
            return False
            
        return True
    
    @staticmethod
    def sanitize_signal_data(signal_data: Dict) -> Dict:
        """Sanitize signal data for JSON serialization"""
        sanitized = {}
        
        for key, value in signal_data.items():
            if isinstance(value, (pd.Timestamp, np.datetime64)):
                sanitized[key] = value.isoformat() if hasattr(value, 'isoformat') else str(value)
            else:
                sanitized[key] = DataConverter.convert_numpy_types(value)
        
        return sanitized
    
    @staticmethod
    def validate_price_data(price: Any) -> bool:
        """Validate price data"""
        if price is None:
            return False
        
        try:
            price_float = float(price)
            return price_float > 0
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def format_percentage(value: float, decimals: int = 2) -> str:
        """Format percentage with proper decimals"""
        try:
            return f"{round(float(value), decimals):.{decimals}f}%"
        except (ValueError, TypeError):
            return "0.00%"
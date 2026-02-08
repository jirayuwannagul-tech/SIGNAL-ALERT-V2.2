# Add to app/utils/helpers.py

from typing import Any, Dict, List, Union

import numpy as np


def convert_numpy_types(obj: Any) -> Any:
    """
    Convert NumPy types to Python native types for JSON serialization.

    Args:
        obj: Object to convert

    Returns:
        Object with NumPy types converted to Python natives
    """
    if isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(
        obj, (np.int_, np.intc, np.intp, np.int8, np.int16, np.int32, np.int64)
    ):
        return int(obj)
    elif isinstance(obj, (np.float64, np.float16, np.float32, np.float64)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    else:
        return obj


def safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert value to float."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_bool(value: Any, default: bool = False) -> bool:
    """Safely convert value to bool."""
    try:
        return bool(value)
    except (ValueError, TypeError):
        return default

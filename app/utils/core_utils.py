import json
import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from functools import wraps

class JSONManager:
    """Centralized JSON file operations"""
    
    @staticmethod
    def ensure_directory(file_path: str):
        """Ensure directory exists for file path"""
        directory = os.path.dirname(file_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
    
    @staticmethod
    def save_json(data: Dict[Any, Any], file_path: str) -> bool:
        """Safe JSON save with backup"""
        try:
            JSONManager.ensure_directory(file_path)
            
            # Create backup if file exists
            if os.path.exists(file_path):
                backup_path = f"{file_path}.backup"
                os.rename(file_path, backup_path)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            
            return True
        except Exception as e:
            logging.error(f"Error saving JSON {file_path}: {e}")
            return False
    
    @staticmethod
    def load_json(file_path: str, default: Dict[Any, Any] = None) -> Dict[Any, Any]:
        """Safe JSON load with fallback"""
        if default is None:
            default = {}
            
        if not os.path.exists(file_path):
            return default
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Error loading JSON {file_path}: {e}")
            # Try backup
            backup_path = f"{file_path}.backup"
            if os.path.exists(backup_path):
                try:
                    with open(backup_path, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except:
                    pass
            return default

class ErrorHandler:
    """Centralized error handling patterns"""
    
    @staticmethod
    def api_error_handler(func):
        """Decorator for API error handling"""
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logging.error(f"API Error in {func.__name__}: {e}")
                return {"error": str(e), "timestamp": datetime.now().isoformat()}
        return wrapper
    
    @staticmethod
    def service_error_handler(service_name: str):
        """Decorator factory for service error handling"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    logging.error(f"Service Error [{service_name}] in {func.__name__}: {e}")
                    return None
            return wrapper
        return decorator

class ConfigValidator:
    """Configuration validation utilities"""
    
    @staticmethod
    def validate_required_env_vars(required_vars: list) -> Dict[str, str]:
        """Validate and return required environment variables"""
        config = {}
        missing_vars = []
        
        for var in required_vars:
            value = os.getenv(var)
            if not value:
                missing_vars.append(var)
            else:
                config[var] = value
        
        if missing_vars:
            raise EnvironmentError(f"Missing required environment variables: {missing_vars}")
        
        return config
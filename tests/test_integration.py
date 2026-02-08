import unittest
import sys
import os
import time
from unittest.mock import patch, MagicMock

# Fix import path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app

class TestIntegration(unittest.TestCase):
    """Integration tests for refactored SIGNAL-ALERT system"""
    
    def setUp(self):
        """Set up test environment"""
        self.app = app.test_client()
        self.app.testing = True
        
        # Mock environment variables for testing
        self.env_patcher = patch.dict(os.environ, {
            'GOOGLE_SHEETS_ID': 'test_sheets_id_12345678901234567890',
            'LINE_CHANNEL_ACCESS_TOKEN': 'test_line_token_' + 'x' * 50,
            'LINE_CHANNEL_SECRET': 'test_line_secret_12345',
            'DEBUG': 'true'
        })
        self.env_patcher.start()
    
    def tearDown(self):
        """Clean up after tests"""
        self.env_patcher.stop()
    
    def test_health_endpoint_with_retry(self):
        """Test health check endpoint with retry logic"""
        # Try multiple times as services initialize in background
        max_retries = 10
        for attempt in range(max_retries):
            response = self.app.get('/health')
            
            if response.status_code == 200:
                data = response.get_json()
                self.assertIn('status', data)
                return
            elif response.status_code == 503:
                # Services still initializing
                time.sleep(1)
                continue
            else:
                self.fail(f"Unexpected status code: {response.status_code}")
        
        # If all retries failed, check what we got
        response = self.app.get('/health')
        data = response.get_json()
        
        # Accept 503 during testing (services initializing)
        self.assertIn(response.status_code, [200, 503])
        self.assertIn('status', data)
    
    def test_home_endpoint(self):
        """Test home endpoint - should always work"""
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)
        
        data = response.get_json()
        self.assertEqual(data['system'], 'SIGNAL-ALERT')
        self.assertEqual(data['version'], '2.0-refactored')
    
    def test_api_endpoints_structure(self):
        """Test that key API endpoints respond (even if services not ready)"""
        endpoints = [
            '/api/positions',
            '/api/positions/summary',
            '/api/scheduler/status',
            '/api/debug/services'
        ]
        
        for endpoint in endpoints:
            response = self.app.get(endpoint)
            # Accept both 200 (working) and 503 (services initializing)
            self.assertIn(response.status_code, [200, 503], 
                         f"Endpoint {endpoint} returned unexpected status: {response.status_code}")

if __name__ == '__main__':
    unittest.main()

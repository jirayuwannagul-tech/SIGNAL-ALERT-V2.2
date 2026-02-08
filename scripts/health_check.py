#!/usr/bin/env python3
"""
Health check script for SIGNAL-ALERT v2.0 deployment
Comprehensive system health verification tool
"""

import requests
import time
import json
import sys
import argparse
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class HealthChecker:
    """Comprehensive health checker for SIGNAL-ALERT v2.0"""
    
    def __init__(self, service_url, timeout=30):
        self.service_url = service_url.rstrip('/')
        self.timeout = timeout
        self.results = {}
        
    def check_endpoint(self, endpoint, expected_keys=None, method='GET', payload=None):
        """Check if endpoint is responding correctly"""
        try:
            url = f"{self.service_url}{endpoint}"
            
            if method.upper() == 'GET':
                response = requests.get(url, timeout=self.timeout)
            elif method.upper() == 'POST':
                response = requests.post(url, json=payload, timeout=self.timeout)
            else:
                return False, f"Unsupported method: {method}"
            
            if response.status_code != 200:
                return False, f"Status code: {response.status_code}"
            
            try:
                data = response.json()
            except json.JSONDecodeError:
                return False, "Invalid JSON response"
            
            if expected_keys:
                missing_keys = [key for key in expected_keys if key not in data]
                if missing_keys:
                    return False, f"Missing keys: {missing_keys}"
            
            return True, data
            
        except requests.exceptions.Timeout:
            return False, "Request timeout"
        except requests.exceptions.ConnectionError:
            return False, "Connection error"
        except Exception as e:
            return False, str(e)
    
    def run_basic_health_checks(self):
        """Run basic health checks"""
        checks = [
            ("Home", "/", ["system", "status"]),
            ("Health", "/health", ["status", "metrics"]), 
            ("Positions", "/api/positions", ["status", "total_positions"]),
            ("Positions Summary", "/api/positions/summary", ["status", "summary"]),
            ("Scheduler Status", "/api/scheduler/status", ["status", "scheduler"]),
            ("Monitor Status", "/api/monitor/status", ["status", "active_positions_count"]),
            ("Debug Services", "/api/debug/services", ["services"]),
            ("Debug Positions", "/api/debug/positions", ["total_positions"])
        ]
        
        print("🏥 Running Basic Health Checks")
        print("-" * 40)
        
        for name, endpoint, expected_keys in checks:
            print(f"Checking {name:20} ...", end=" ")
            
            success, result = self.check_endpoint(endpoint, expected_keys)
            self.results[name] = {"success": success, "result": result, "endpoint": endpoint}
            
            if success:
                print("✅ PASS")
            else:
                print(f"❌ FAIL - {result}")
        
        return self.results
    
    def test_signal_detection(self):
        """Test signal detection functionality"""
        print("\n🎯 Testing Signal Detection")
        print("-" * 30)
        
        test_cases = [
            ("Single Symbol", "/api/signals?symbols=BTCUSDT&timeframes=4h"),
            ("Multiple Symbols", "/api/signals?symbols=BTCUSDT,ETHUSDT&timeframes=4h"),
            ("Active Signals", "/api/signals/active")
        ]
        
        for name, endpoint in test_cases:
            print(f"Testing {name:20} ...", end=" ")
            
            success, result = self.check_endpoint(endpoint, ["status"], method='GET')
            
            if success:
                signals_found = result.get('signals_found', result.get('active_signals', 0))
                print(f"✅ PASS ({signals_found} signals)")
            else:
                print(f"❌ FAIL - {result}")
                
            self.results[f"Signal_{name}"] = {"success": success, "result": result}
    
    def test_position_management(self):
        """Test position management functionality"""
        print("\n📊 Testing Position Management")
        print("-" * 35)
        
        test_cases = [
            ("Position Status", "/api/positions/status/BTCUSDT/4h", ["position_found"]),
            ("Update Positions", "/api/positions/update", ["positions_updated"], "POST"),
            ("Force Check", "/api/monitor/force-check", ["status"], "POST")
        ]
        
        for name, endpoint, expected_keys, *method in test_cases:
            method = method[0] if method else "GET"
            print(f"Testing {name:20} ...", end=" ")
            
            success, result = self.check_endpoint(endpoint, expected_keys, method)
            
            if success:
                if "positions_updated" in result:
                    count = result["positions_updated"]
                    print(f"✅ PASS ({count} positions updated)")
                elif "position_found" in result:
                    found = result["position_found"]
                    status = "Found" if found else "Not Found"
                    print(f"✅ PASS ({status})")
                else:
                    print("✅ PASS")
            else:
                print(f"❌ FAIL - {result}")
                
            self.results[f"Position_{name}"] = {"success": success, "result": result}
    
    def test_price_monitoring(self):
        """Test price monitoring functionality"""
        print("\n💰 Testing Price Monitoring")
        print("-" * 30)
        
        symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
        
        for symbol in symbols:
            print(f"Checking {symbol:10} price ...", end=" ")
            
            success, result = self.check_endpoint(f"/api/monitor/check/{symbol}", 
                                                ["current_price"])
            
            if success:
                price = result.get("current_price")
                print(f"✅ PASS (${price:,.2f})")
            else:
                print(f"❌ FAIL - {result}")
                
            self.results[f"Price_{symbol}"] = {"success": success, "result": result}
    
    def test_scheduler_operations(self):
        """Test scheduler operations"""
        print("\n⏰ Testing Scheduler Operations")
        print("-" * 35)
        
        # Get current status first
        print("Checking current status ...", end=" ")
        success, result = self.check_endpoint("/api/scheduler/status", ["scheduler"])
        
        if success:
            current_status = result["scheduler"]
            print(f"✅ Status: {current_status}")
            
            # Test stop/start cycle if currently running
            if "running" in str(current_status).lower():
                print("Testing stop operation ...", end=" ")
                success, result = self.check_endpoint("/api/scheduler/stop", 
                                                    ["status"], "POST")
                if success:
                    print("✅ PASS")
                    time.sleep(2)  # Wait a moment
                    
                    print("Testing start operation ...", end=" ")
                    success, result = self.check_endpoint("/api/scheduler/start", 
                                                        ["status"], "POST")
                    if success:
                        print("✅ PASS")
                    else:
                        print(f"❌ FAIL - {result}")
                else:
                    print(f"❌ FAIL - {result}")
        else:
            print(f"❌ FAIL - {result}")
    
    def run_performance_test(self):
        """Run basic performance test"""
        print("\n⚡ Running Performance Test")
        print("-" * 30)
        
        endpoint = "/health"
        iterations = 10
        
        print(f"Testing {endpoint} ({iterations} requests) ...", end=" ")
        
        times = []
        errors = 0
        
        for i in range(iterations):
            start_time = time.time()
            success, result = self.check_endpoint(endpoint, ["status"])
            end_time = time.time()
            
            if success:
                times.append(end_time - start_time)
            else:
                errors += 1
            
            time.sleep(0.1)  # Small delay between requests
        
        if times:
            avg_time = sum(times) / len(times)
            min_time = min(times)
            max_time = max(times)
            
            print(f"✅ PASS")
            print(f"   Avg: {avg_time*1000:.1f}ms | Min: {min_time*1000:.1f}ms | Max: {max_time*1000:.1f}ms")
            print(f"   Success Rate: {len(times)}/{iterations} ({len(times)/iterations*100:.1f}%)")
            
            self.results["Performance"] = {
                "success": True,
                "avg_ms": round(avg_time * 1000, 1),
                "min_ms": round(min_time * 1000, 1),
                "max_ms": round(max_time * 1000, 1),
                "success_rate": len(times) / iterations * 100,
                "errors": errors
            }
        else:
            print(f"❌ FAIL - All requests failed")
            self.results["Performance"] = {"success": False, "errors": errors}
    
    def generate_summary(self):
        """Generate health check summary"""
        print("\n📊 Health Check Summary")
        print("=" * 50)
        
        total_checks = len(self.results)
        passed_checks = sum(1 for r in self.results.values() if r.get('success', False))
        
        print(f"Total Checks: {total_checks}")
        print(f"Passed: {passed_checks}")
        print(f"Failed: {total_checks - passed_checks}")
        print(f"Success Rate: {passed_checks/total_checks*100:.1f}%")
        
        # Overall health score
        if passed_checks == total_checks:
            print("\n🎉 System Status: HEALTHY")
            health_score = 100
        elif passed_checks / total_checks >= 0.9:
            print("\n✅ System Status: GOOD")
            health_score = 90
        elif passed_checks / total_checks >= 0.7:
            print("\n⚠️  System Status: WARNING")
            health_score = 70
        else:
            print("\n❌ System Status: CRITICAL")
            health_score = 40
        
        print(f"Health Score: {health_score}/100")
        
        # Show failed checks
        failed_checks = [name for name, result in self.results.items() 
                        if not result.get('success', False)]
        
        if failed_checks:
            print(f"\n❌ Failed Checks:")
            for check_name in failed_checks:
                result = self.results[check_name]
                endpoint = result.get('endpoint', 'N/A')
                error = result.get('result', 'Unknown error')
                print(f"   - {check_name} ({endpoint}): {error}")
        
        return health_score >= 70
    
    def save_results(self, filename=None):
        """Save health check results to JSON"""
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"health_check_results_{timestamp}.json"
        
        try:
            report_data = {
                'timestamp': datetime.now().isoformat(),
                'service_url': self.service_url,
                'results': self.results,
                'summary': {
                    'total_checks': len(self.results),
                    'passed_checks': sum(1 for r in self.results.values() if r.get('success', False)),
                    'failed_checks': sum(1 for r in self.results.values() if not r.get('success', False))
                }
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, ensure_ascii=False, indent=2)
            
            print(f"\n💾 Results saved to: {filename}")
            
        except Exception as e:
            logger.warning(f"Could not save results: {e}")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='SIGNAL-ALERT v2.0 Health Check')
    parser.add_argument('--url', '-u', required=True,
                       help='Service URL (e.g., https://squeeze-bot-xxxxx-as.a.run.app)')
    parser.add_argument('--timeout', '-t', type=int, default=30,
                       help='Request timeout in seconds (default: 30)')
    parser.add_argument('--save', '-s', action='store_true',
                       help='Save results to JSON file')
    parser.add_argument('--quick', '-q', action='store_true',
                       help='Run only basic health checks')
    
    args = parser.parse_args()
    
    print("🏥 SIGNAL-ALERT v2.0 Health Check")
    print(f"Service URL: {args.url}")
    print(f"Timeout: {args.timeout}s")
    print("=" * 60)
    
    start_time = datetime.now()
    checker = HealthChecker(args.url, args.timeout)
    
    try:
        # Run basic health checks
        checker.run_basic_health_checks()
        
        if not args.quick:
            # Run comprehensive tests
            checker.test_signal_detection()
            checker.test_position_management()
            checker.test_price_monitoring()
            checker.test_scheduler_operations()
            checker.run_performance_test()
        
        # Generate summary
        system_healthy = checker.generate_summary()
        
        # Save results if requested
        if args.save:
            checker.save_results()
        
        duration = datetime.now() - start_time
        print(f"\n⏱️  Duration: {duration.total_seconds():.1f}s")
        
        # Exit with appropriate code
        return 0 if system_healthy else 1
        
    except KeyboardInterrupt:
        print("\n⚠️ Health check cancelled by user")
        return 130
    except Exception as e:
        print(f"\n💥 Health check error: {e}")
        logger.error(f"Health check failed: {e}")
        return 1

if __name__ == '__main__':
    exit(main())
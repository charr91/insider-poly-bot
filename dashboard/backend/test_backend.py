"""
Quick test to verify the dashboard backend components work correctly
"""

import sys
import json
from pathlib import Path

def test_imports():
    """Test that all modules can be imported"""
    print("🔍 Testing imports...")
    
    try:
        from main import app, ws_manager, dashboard_config
        from websocket_manager import WebSocketManager
        from api_routes import router
        from config_manager import DashboardConfig
        print("✅ All imports successful")
        return True
    except Exception as e:
        print(f"❌ Import error: {e}")
        return False

def test_fastapi_app():
    """Test that FastAPI app is properly configured"""
    print("🔍 Testing FastAPI app configuration...")
    
    try:
        from main import app
        
        # Check app properties
        assert app.title == "Polymarket Insider Trading Detection Dashboard"
        assert app.version == "1.0.0"
        assert "/api/docs" in str(app.docs_url)
        
        # Check routes are registered
        routes = [route.path for route in app.routes]
        expected_routes = ["/", "/ws", "/health"]
        
        for expected in expected_routes:
            assert expected in routes, f"Route {expected} not found"
        
        print("✅ FastAPI app configuration valid")
        return True
    except Exception as e:
        print(f"❌ FastAPI app error: {e}")
        return False

def test_websocket_manager():
    """Test WebSocket manager initialization"""
    print("🔍 Testing WebSocket manager...")
    
    try:
        from websocket_manager import WebSocketManager
        
        ws_mgr = WebSocketManager()
        
        # Check default state
        assert len(ws_mgr.active_connections) == 0
        assert not ws_mgr.streaming_active
        assert len(ws_mgr.streaming_tasks) == 0
        
        # Check subscription channels
        expected_channels = [
            "alerts", "markets", "anomaly_scores", "system_health",
            "wallet_coordination", "cross_market_correlation", 
            "wash_trading", "historical_baseline"
        ]
        
        for channel in expected_channels:
            assert channel in ws_mgr.subscriptions
        
        # Test stats method
        stats = ws_mgr.get_stats()
        assert "total_connections" in stats
        assert "channel_subscriptions" in stats
        
        print("✅ WebSocket manager initialization successful")
        return True
    except Exception as e:
        print(f"❌ WebSocket manager error: {e}")
        return False

def test_config_manager():
    """Test configuration manager"""
    print("🔍 Testing configuration manager...")
    
    try:
        from config_manager import DashboardConfig
        
        config = DashboardConfig()
        
        # Test basic configuration access
        port = config.get("dashboard.port", 8000)
        assert isinstance(port, int)
        
        host = config.get("dashboard.host", "127.0.0.1")
        assert isinstance(host, str)
        
        # Test validation
        validation = config.validate_config()
        assert "valid" in validation
        assert "errors" in validation
        assert "warnings" in validation
        
        # Test specialized getters
        dashboard_config = config.get_dashboard_config()
        detection_config = config.get_detection_config()
        
        assert "port" in dashboard_config
        assert "host" in dashboard_config
        
        print("✅ Configuration manager working correctly")
        return True
    except Exception as e:
        print(f"❌ Configuration manager error: {e}")
        return False

def test_api_routes():
    """Test API routes structure"""
    print("🔍 Testing API routes...")
    
    try:
        from api_routes import router
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        
        # Create test app
        test_app = FastAPI()
        test_app.include_router(router, prefix="/api/v1")
        
        # Check that routes are registered
        routes = [route.path for route in test_app.routes]
        expected_routes = [
            "/api/v1/alerts",
            "/api/v1/performance", 
            "/api/v1/markets",
            "/api/v1/config",
            "/api/v1/system/health"
        ]
        
        for expected in expected_routes:
            assert expected in routes, f"API route {expected} not found"
        
        print("✅ API routes structure valid")
        return True
    except Exception as e:
        print(f"❌ API routes error: {e}")
        return False

def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("🚀 DASHBOARD BACKEND COMPONENT TESTS")
    print("="*60)
    
    tests = [
        test_imports,
        test_fastapi_app,
        test_websocket_manager,
        test_config_manager,
        test_api_routes
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
            print()
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
            print()
    
    print("-"*60)
    print(f"📊 TEST RESULTS: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Backend is ready.")
        return 0
    else:
        print("❌ Some tests failed. Check the errors above.")
        return 1

if __name__ == "__main__":
    # Change to backend directory
    backend_dir = Path(__file__).parent
    sys.path.insert(0, str(backend_dir))
    
    exit_code = main()
    sys.exit(exit_code)
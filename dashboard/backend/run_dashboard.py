#!/usr/bin/env python3
"""
Dashboard Backend Startup Script

Runs the FastAPI backend server for the insider trading detection dashboard.
"""

import sys
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

import uvicorn
from config_manager import DashboardConfig


def main():
    """Start the dashboard backend server"""
    # Initialize configuration
    config = DashboardConfig()
    dashboard_config = config.get_dashboard_config()
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO if not dashboard_config["debug"] else logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    logger = logging.getLogger(__name__)
    
    # Validate configuration
    validation = config.validate_config()
    if not validation["valid"]:
        logger.error("❌ Configuration validation failed:")
        for error in validation["errors"]:
            logger.error(f"  • {error}")
        sys.exit(1)
    
    if validation["warnings"]:
        logger.warning("⚠️  Configuration warnings:")
        for warning in validation["warnings"]:
            logger.warning(f"  • {warning}")
    
    logger.info("✅ Configuration validated successfully")
    
    # Print startup banner
    print("\n" + "="*80)
    print("🚀 POLYMARKET INSIDER TRADING DETECTION DASHBOARD")
    print("📊 FastAPI Backend with WebSocket Support")
    print("="*80)
    print(f"🌐 Dashboard URL: http://{dashboard_config['host']}:{dashboard_config['port']}")
    print(f"📖 API Documentation: http://{dashboard_config['host']}:{dashboard_config['port']}/api/docs")
    print(f"🔌 WebSocket Endpoint: ws://{dashboard_config['host']}:{dashboard_config['port']}/ws")
    print(f"🐛 Debug Mode: {'Enabled' if dashboard_config['debug'] else 'Disabled'}")
    print("-"*80)
    
    # Start server
    try:
        uvicorn.run(
            "main:app",
            host=dashboard_config["host"],
            port=dashboard_config["port"],
            reload=dashboard_config["debug"],
            log_level="info" if not dashboard_config["debug"] else "debug",
            access_log=True,
            ws_ping_interval=dashboard_config["websocket_ping_interval"],
            ws_ping_timeout=dashboard_config["websocket_ping_interval"] * 2
        )
    except KeyboardInterrupt:
        logger.info("🛑 Dashboard backend stopped by user")
    except Exception as e:
        logger.error(f"❌ Failed to start dashboard backend: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
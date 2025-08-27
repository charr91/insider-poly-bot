#!/usr/bin/env python3
"""
New Polymarket Insider Trading Bot
Uses modular architecture with WebSocket + Data API approach
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from market_monitor import MarketMonitor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('insider_bot.log')
    ]
)

logger = logging.getLogger(__name__)

async def main():
    """Main execution function"""
    logger.info("🚀 Starting Polymarket Insider Trading Detection Bot")
    logger.info("📊 Using modular architecture with WebSocket + Data API")
    
    # Initialize market monitor
    monitor = MarketMonitor("insider_config.json")
    
    # Log configuration summary
    config_summary = monitor.settings.get_config_summary()
    logger.info(f"⚙️ Configuration: {config_summary}")
    
    try:
        # Start monitoring
        await monitor.start_monitoring()
        
    except KeyboardInterrupt:
        logger.info("🛑 Received shutdown signal")
        
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        
    finally:
        # Cleanup
        await monitor.stop_monitoring()
        logger.info("👋 Bot shutdown complete")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Startup error: {e}")
        sys.exit(1)
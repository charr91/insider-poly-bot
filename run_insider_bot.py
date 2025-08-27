#!/usr/bin/env python3
"""
Insider Activity Detection Bot Runner
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/insider_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def load_config():
    """Load configuration"""
    config_path = Path("insider_config.json")
    
    if not config_path.exists():
        default_config = {
            "monitoring": {
                "markets": [],  # Empty = monitor all top markets
                "volume_threshold": 1000,
                "max_markets": 50,
                "sort_by_volume": True,
                "check_interval": 60
            },
            "detection": {
                "volume_spike_multiplier": 3.0,
                "price_movement_threshold": 15,
                "whale_threshold_usd": 10000,
                "min_severity": "MEDIUM"  # Only alert MEDIUM and above
            },
            "alerts": {
                "discord_webhook": "",
                "telegram_bot": "",
                "email": "",
                "sound_alert": True
            }
        }
        
        with open(config_path, 'w') as f:
            json.dump(default_config, f, indent=2)
            
        logger.info("Created default config file: insider_config.json")
        logger.info("Please configure and restart")
        sys.exit(0)
    
    with open(config_path) as f:
        return json.load(f)

async def main():
    """Main execution loop"""
    config = load_config()
    
    # Import after config check
    from insider_bot import UnusualActivityDetector
    
    logger.info("="*60)
    logger.info("🔍 UNUSUAL ACTIVITY DETECTION BOT")
    logger.info("="*60)
    logger.info(f"Volume threshold: ${config['monitoring']['volume_threshold']}")
    logger.info(f"Max markets: {config['monitoring']['max_markets']}")
    logger.info(f"Min severity: {config['detection']['min_severity']}")
    
    # Initialize bot with config
    detector = UnusualActivityDetector(config)
    
    # Apply detection thresholds from config
    detector.thresholds.update(config['detection'])
    
    # Start monitoring
    try:
        await detector.monitor_markets(config['monitoring'].get('markets'))
    except KeyboardInterrupt:
        logger.info("\n👋 Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())
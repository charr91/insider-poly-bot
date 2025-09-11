#!/usr/bin/env python3
"""
New Polymarket Insider Trading Bot
Uses modular architecture with WebSocket + Data API approach
"""

import asyncio
import logging
import sys
from pathlib import Path
from colorama import init, Fore, Back, Style
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize colorama for cross-platform colored output
init(autoreset=True)

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

def _log_config_summary(config: dict):
    """Format and log configuration summary nicely"""
    monitoring = config.get('monitoring', {})
    detection = config.get('detection', {})
    alerts = config.get('alerts', {})
    api = config.get('api', {})
    
    print(f"  📊 {Fore.CYAN}Markets:{Style.RESET_ALL} {monitoring.get('max_markets', 0)} max, {Fore.GREEN}${monitoring.get('volume_threshold', 0):,}{Style.RESET_ALL} min volume")
    print(f"  🔍 {Fore.CYAN}Detection:{Style.RESET_ALL} {Fore.YELLOW}{detection.get('volume_spike_multiplier', 0)}x{Style.RESET_ALL} volume spike, {Fore.GREEN}${detection.get('whale_threshold_usd', 0):,}{Style.RESET_ALL} whale threshold")
    print(f"  🔔 {Fore.CYAN}Alerts:{Style.RESET_ALL} {alerts.get('min_severity', 'N/A')} severity, Discord {'✅' if alerts.get('discord_configured') else '❌'}")
    print(f"  🌐 {Fore.CYAN}Mode:{Style.RESET_ALL} {Fore.GREEN + '🟢 Live Trading' if not api.get('simulation_mode') else Fore.YELLOW + '🟡 Simulation'}{Style.RESET_ALL}")
    print(f"  🔐 {Fore.CYAN}Auth:{Style.RESET_ALL} {'✅ CLOB API' if api.get('clob_authenticated') else Fore.RED + '❌ No CLOB API' + Style.RESET_ALL}")

async def main():
    """Main execution function"""
    print(f"\n{Fore.BLUE}{'='*80}{Style.RESET_ALL}")
    print(f"{Fore.CYAN + Style.BRIGHT}🚀 POLYMARKET INSIDER TRADING DETECTION BOT{Style.RESET_ALL}")
    print(f"{Fore.WHITE}📊 Modular WebSocket + Data API Architecture{Style.RESET_ALL}")
    print(f"{Fore.BLUE}{'='*80}{Style.RESET_ALL}\n")
    
    # Initialize market monitor
    monitor = MarketMonitor("insider_config.json")
    
    # Log configuration summary in a nice format
    config_summary = monitor.settings.get_config_summary()
    print(f"{Fore.YELLOW + Style.BRIGHT}⚙️  CONFIGURATION SUMMARY{Style.RESET_ALL}")
    print(f"{Fore.BLUE}{'─' * 40}{Style.RESET_ALL}")
    _log_config_summary(config_summary)
    print()
    
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
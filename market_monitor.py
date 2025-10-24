"""
Market Monitor Orchestrator
Coordinates data sources and detection algorithms for insider trading detection
"""

import asyncio
import logging
import tracemalloc
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
import json
from pathlib import Path
import aiohttp
from colorama import init, Fore, Back, Style

# Initialize colorama
init(autoreset=True)

from data_sources.data_api_client import DataAPIClient
from data_sources.websocket_client import WebSocketClient
from detection import VolumeDetector, WhaleDetector, PriceDetector, CoordinationDetector
from detection.fresh_wallet_detector import FreshWalletDetector
from alerts.alert_manager import AlertManager
from config.settings import Settings
from config.database import DATABASE_PATH
from common import (
    AlertType, AlertSeverity, BaselineType, MarketStatus, DetectorStatus,
    AlertMetadata, Alert, MarketBaseline, DetectionResult,
    ConfidenceThresholds, TimeConstants, VolumeConstants
)
from database import DatabaseManager
from persistence.alert_storage import DatabaseAlertStorage
from persistence.whale_tracker import WhaleTracker
from persistence.outcome_tracker import OutcomeTracker

logger = logging.getLogger(__name__)

class MarketMonitor:
    """Main orchestrator for market monitoring and insider detection"""
    
    def __init__(self, config_path: str = "insider_config.json", db_path: str = DATABASE_PATH):
        # Load configuration
        self.config = self._load_config(config_path)
        self.settings = Settings(self.config)

        # Debug configuration
        self.debug_config = self.config.get('debug', {})
        self.debug_mode = self.debug_config.get('debug_mode', False)
        self.show_normal_activity = self.debug_config.get('show_normal_activity', False)

        # Initialize database
        self.db_manager = DatabaseManager.get_instance(f"sqlite+aiosqlite:///{db_path}")

        # Initialize data sources
        # DataAPIClient will be initialized in start_monitoring() for proper async context
        self.data_api = DataAPIClient()
        self.websocket_client = None
        self.gamma_session = None  # Session for Gamma API requests

        # Initialize detection algorithms
        self.volume_detector = VolumeDetector(self.config)
        self.whale_detector = WhaleDetector(self.config)
        self.price_detector = PriceDetector(self.config)
        self.coordination_detector = CoordinationDetector(self.config)
        # Note: fresh_wallet_detector initialization deferred until after whale_tracker is created

        # Market data storage (must be initialized before AlertManager)
        self.monitored_markets = {}  # High-volume markets (full analysis)
        self.low_volume_markets = {}  # Low-volume markets (whale-only scanning)
        self.escalated_markets = set()  # Markets escalated from low-volume to full monitoring
        self.market_baselines = {}
        self.trade_history = {}
        self.token_to_outcome = {}  # Maps token ID to "Yes" or "No"

        # Initialize persistence layer
        self.alert_storage = DatabaseAlertStorage(self.db_manager)
        self.whale_tracker = WhaleTracker(self.db_manager)
        self.outcome_tracker = OutcomeTracker(self.db_manager, self.data_api)

        # Initialize fresh wallet detector (requires data_api and whale_tracker)
        self.fresh_wallet_detector = FreshWalletDetector(self.config, self.data_api, self.whale_tracker)

        # Initialize alert manager with database storage and token mapping
        self.alert_manager = AlertManager(
            self.settings,
            storage=self.alert_storage,
            token_to_outcome=self.token_to_outcome
        )
        
        # Cross-market activity tracking for context filtering
        self.recent_market_activities = {}
        self.cross_market_window_minutes = TimeConstants.CROSS_MARKET_WINDOW_MINUTES
        
        # Control flags
        self.running = False
        self.market_discovery_interval = 300  # 5 minutes
        self.analysis_interval = 60  # 1 minute
        
        # Activity tracking for debug mode
        self.analysis_count = 0
        self.alerts_generated = 0
        self.last_status_report = datetime.now(timezone.utc)
        self.status_report_interval = self.debug_config.get('activity_report_interval', 300)  # 5 minutes
        
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from file"""
        try:
            config_file = Path(config_path)
            if not config_file.exists():
                logger.error(f"Config file not found: {config_path}")
                logger.error("Config file is required. Please ensure insider_config.json exists and is valid.")
                raise RuntimeError(f"Cannot load configuration file: {config_path} not found")

            with open(config_file) as f:
                config = json.load(f)
            logger.info(f"Loaded configuration from {config_path}")
            return config
        except RuntimeError:
            # Re-raise RuntimeError as-is
            raise
        except Exception as e:
            logger.error(f"Failed to load config from {config_path}: {e}")
            logger.error("Config file is required. Please ensure insider_config.json exists and is valid.")
            raise RuntimeError(f"Cannot load configuration file: {e}")
    
    async def start_monitoring(self):
        """Start the market monitoring system"""
        logger.info("🚀 Starting Market Monitor")

        # Initialize async sessions
        await self.data_api.__aenter__()

        # Create persistent session for Gamma API to prevent memory leaks
        import aiohttp
        self.gamma_session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={'User-Agent': 'PolymarketInsiderBot/1.0'}
        )

        # Initialize database
        logger.info("📊 Initializing database...")
        await self.db_manager.init_db()
        logger.info("✅ Database initialized")

        # Test connections
        if not await self._test_connections():
            logger.error("❌ Connection tests failed - aborting startup")
            return

        self.running = True

        # Start concurrent tasks
        tasks = [
            asyncio.create_task(self._market_discovery_loop(), name="market_discovery"),
            asyncio.create_task(self._analysis_loop(), name="analysis"),
            asyncio.create_task(self._websocket_monitor(), name="websocket"),
            asyncio.create_task(self._status_reporter(), name="status_reporter"),
            asyncio.create_task(self._trade_polling_loop(), name="trade_polling"),  # Real-time trade polling
            asyncio.create_task(self._outcome_update_loop(), name="outcome_updates")  # Outcome tracking updates
        ]

        # Add low-volume scanning task if enabled
        if self.settings.monitoring.enable_low_volume_scanning:
            tasks.append(asyncio.create_task(self._low_volume_scan_loop(), name="low_volume_scan"))
            logger.info("🔍 Low-volume whale scanning enabled")

        try:
            await asyncio.gather(*tasks, return_exceptions=True)
            # If we reach here, one or more tasks completed unexpectedly
            logger.error("❌ CRITICAL: One or more monitoring tasks completed unexpectedly!")
            for task in tasks:
                if task.done():
                    task_name = task.get_name()
                    if task.exception():
                        logger.error(f"Task '{task_name}' failed with exception: {task.exception()}")
                    else:
                        logger.error(f"Task '{task_name}' completed without exception (unexpected)")
        except Exception as e:
            logger.error(f"Error in monitoring tasks: {e}", exc_info=True)
        finally:
            await self.stop_monitoring()
    
    async def stop_monitoring(self):
        """Stop the monitoring system"""
        logger.info("🛑 Stopping Market Monitor")
        self.running = False

        if self.websocket_client:
            self.websocket_client.disconnect()

        # Close HTTP sessions to prevent memory leaks
        if self.data_api:
            await self.data_api.close()

        if self.gamma_session and not self.gamma_session.closed:
            await self.gamma_session.close()
    
    async def _test_connections(self) -> bool:
        """Test all external connections"""
        logger.info("🔍 Testing connections...")

        # Test Data API
        if not await self.data_api.test_connection():
            logger.error("❌ Data API connection failed")
            return False

        logger.info("✅ Data API connection successful")

        # Test WebSocket (will be tested when markets are discovered)
        # Test alert systems
        await self.alert_manager.test_connections()

        return True
    
    async def _market_discovery_loop(self):
        """Continuously discover and update monitored markets"""
        while self.running:
            try:
                await self._discover_markets()
                await asyncio.sleep(self.market_discovery_interval)
            except Exception as e:
                logger.error(f"Error in market discovery: {e}")
                await asyncio.sleep(60)  # Wait before retrying

        # Log if loop exits
        logger.error(f"❌ CRITICAL: market_discovery_loop exited! self.running={self.running}")
    
    async def _discover_markets(self):
        """Discover high-volume markets to monitor"""
        logger.info("🔍 Discovering markets...")

        gamma_api = "https://gamma-api.polymarket.com"
        volume_threshold = self.config.get('monitoring', {}).get('volume_threshold', 1000)
        max_markets = self.config.get('monitoring', {}).get('max_markets', 50)
        sort_by_volume = self.config.get('monitoring', {}).get('sort_by_volume', True)

        try:
            # Use persistent session if available, otherwise create temporary (for tests)
            import aiohttp
            if self.gamma_session:
                session = self.gamma_session
                async with session.get(f"{gamma_api}/markets?active=true&closed=false&limit={max_markets}") as resp:
                    await self._process_markets_response(resp, volume_threshold, max_markets, sort_by_volume)
            else:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{gamma_api}/markets?active=true&closed=false&limit={max_markets}") as resp:
                        await self._process_markets_response(resp, volume_threshold, max_markets, sort_by_volume)
        except Exception as e:
            logger.error(f"Error discovering markets: {e}", exc_info=True)

    async def _process_markets_response(self, resp, volume_threshold, max_markets, sort_by_volume):
        """Process the markets API response and categorize into high/low volume"""
        if resp.status != 200:
            logger.error(f"Failed to fetch markets: HTTP {resp.status}")
            return

        markets = await resp.json()

        # Handle different response formats
        if isinstance(markets, dict):
            if 'data' in markets:
                markets = markets['data']
            elif 'markets' in markets:
                markets = markets['markets']

        if not isinstance(markets, list):
            logger.error(f"Expected list of markets, got {type(markets)}")
            return

        # Sort by volume if configured
        if sort_by_volume:
            try:
                markets.sort(key=lambda m: float(m.get('volume24hr', 0)), reverse=True)
            except (ValueError, TypeError):
                logger.warning("Could not sort markets by volume")

        # Determine monitoring mode
        monitor_all = self.settings.monitoring.monitor_all_markets
        enable_low_volume = self.settings.monitoring.enable_low_volume_scanning
        max_high_volume = self.settings.monitoring.max_markets
        max_low_volume = self.settings.monitoring.max_low_volume_markets

        # Filter and categorize markets
        updated_high_volume_markets = {}
        updated_low_volume_markets = {}
        websocket_token_ids = []
        high_volume_count = 0
        low_volume_count = 0

        for market in markets:
            try:
                condition_id = market.get('conditionId', '')
                volume = float(market.get('volume24hr', 0))

                if not condition_id:
                    continue

                # Process token IDs for all markets
                token_ids_raw = market.get('clobTokenIds', [])
                token_ids = None  # Initialize to None
                if token_ids_raw:
                    try:
                        if isinstance(token_ids_raw, str):
                            token_ids = json.loads(token_ids_raw)
                        else:
                            token_ids = token_ids_raw

                        if isinstance(token_ids, list) and len(token_ids) >= 2:
                            self.token_to_outcome[token_ids[0]] = "Yes"
                            self.token_to_outcome[token_ids[1]] = "No"
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.debug(f"Could not parse token IDs for {condition_id}: {e}")

                # Categorize market based on mode
                if monitor_all:
                    # Monitor ALL markets with full analysis
                    if max_high_volume is None or high_volume_count < max_high_volume:
                        updated_high_volume_markets[condition_id] = market
                        high_volume_count += 1

                        # Add to websocket and initialize baseline
                        if token_ids and isinstance(token_ids, list) and len(token_ids) >= 2:
                            websocket_token_ids.extend(token_ids[:2])
                        if condition_id not in self.monitored_markets and condition_id not in self.escalated_markets:
                            await self._initialize_market_baseline(condition_id, market)

                elif volume >= volume_threshold:
                    # High-volume market
                    if max_high_volume is None or high_volume_count < max_high_volume:
                        updated_high_volume_markets[condition_id] = market
                        high_volume_count += 1

                        # Add to websocket and initialize baseline
                        if token_ids and isinstance(token_ids, list) and len(token_ids) >= 2:
                            websocket_token_ids.extend(token_ids[:2])
                        if condition_id not in self.monitored_markets and condition_id not in self.escalated_markets:
                            await self._initialize_market_baseline(condition_id, market)

                elif enable_low_volume:
                    # Low-volume market (whale scanning only)
                    if max_low_volume is None or low_volume_count < max_low_volume:
                        updated_low_volume_markets[condition_id] = market
                        low_volume_count += 1

            except (KeyError, ValueError, TypeError) as e:
                logger.debug(f"Error processing market: {e}")
                continue

        # Update market dictionaries
        old_high_count = len(self.monitored_markets)
        old_low_count = len(self.low_volume_markets)
        self.monitored_markets = updated_high_volume_markets
        self.low_volume_markets = updated_low_volume_markets

        # Log discovery results
        if monitor_all:
            logger.info(f"📊 Monitoring ALL {len(self.monitored_markets)} markets (was {old_high_count})")
        else:
            logger.info(f"📊 High-volume: {len(self.monitored_markets)} markets (was {old_high_count})")
            if enable_low_volume:
                logger.info(f"📊 Low-volume: {len(self.low_volume_markets)} markets (was {old_low_count})")

        # Update WebSocket subscriptions (optional - fallback to Data API if fails)
        try:
            await self._update_websocket_subscriptions(websocket_token_ids)
            logger.info(f"🔌 WebSocket subscriptions updated with {len(websocket_token_ids)} token IDs")
        except Exception as e:
            logger.warning(f"WebSocket subscription failed, using Data API only: {e}")
    
    async def _initialize_market_baseline(self, market_id: str, market_data: Dict):
        """Initialize baseline metrics for a new market"""
        try:
            # Get extended historical data for better baselines
            historical_trades = await self.data_api.get_historical_trades(market_id, lookback_hours=TimeConstants.HISTORICAL_DATA_HOURS)
            
            if historical_trades:
                # Calculate baseline using volume detector
                baseline = self.volume_detector.calculate_baseline_metrics(historical_trades)
                
                if baseline and baseline.get('total_volume', 0) > 0:
                    self.market_baselines[market_id] = baseline
                    market_name = market_data.get('question', 'Unknown')[:30]
                    trade_count = len(historical_trades)
                    total_volume = baseline.get('total_volume', 0)
                    logger.info(f"📊 Initialized baseline: {market_name}... ({trade_count} trades, ${total_volume:,.0f} volume)")
                else:
                    logger.warning(f"⚠️ Invalid baseline calculated for {market_id[:10]}... - insufficient data")
            else:
                logger.warning(f"⚠️ No historical data available for {market_id[:10]}... - will use recent trade baselines")
        
        except Exception as e:
            logger.error(f"Failed to initialize baseline for {market_id}: {e}")

    async def _escalate_market(self, market_id: str, market_data: Dict):
        """
        Permanently promote a low-volume market to full monitoring.
        Called when whale activity is detected in a low-volume market.

        Args:
            market_id: Market identifier
            market_data: Market metadata
        """
        try:
            market_name = market_data.get('question', 'Unknown')[:50]
            logger.info(f"🔺 ESCALATING market to full monitoring: {market_name}...")

            # Move from low_volume_markets to monitored_markets
            if market_id in self.low_volume_markets:
                self.monitored_markets[market_id] = self.low_volume_markets[market_id]
                del self.low_volume_markets[market_id]
            else:
                # Market may have been already escalated or is new
                self.monitored_markets[market_id] = market_data

            # Track escalation (permanent)
            self.escalated_markets.add(market_id)

            # Initialize baseline for full analysis if not already present
            if market_id not in self.market_baselines:
                await self._initialize_market_baseline(market_id, market_data)

            logger.info(f"✅ Market escalated: {market_name}... (now has full analysis)")

        except Exception as e:
            logger.error(f"Failed to escalate market {market_id}: {e}", exc_info=True)

    async def _analyze_market_for_whales(self, market_id: str, market_data: Dict) -> int:
        """
        Lightweight analysis for low-volume markets - only whale and fresh wallet detection.
        Escalates market to full monitoring if whales are detected.

        Args:
            market_id: Market identifier
            market_data: Market metadata

        Returns:
            int: Number of alerts successfully sent
        """
        try:
            # Get combined trade data
            trades = await self._get_market_trades(market_id)

            if not trades:
                return 0

            # Run only whale and fresh wallet detectors (lightweight)
            whale_analysis = self.whale_detector.detect_whale_activity(trades)
            fresh_wallet_detections = await self.fresh_wallet_detector.detect_fresh_wallet_activity(trades)

            alerts_sent = 0

            # Handle whale detection
            if whale_analysis.get('anomaly', False):
                logger.info(f"🐋 Whale detected in low-volume market: {market_data.get('question', 'Unknown')[:50]}...")

                # Escalate if enabled
                if self.settings.monitoring.whale_escalation_enabled:
                    await self._escalate_market(market_id, market_data)

                # Create and send whale alert
                severity = self._determine_severity(AlertType.WHALE_ACTIVITY, whale_analysis)
                alert = await self._create_alert(
                    market_id, market_data, AlertType.WHALE_ACTIVITY, whale_analysis, severity.value
                )
                alert['confidence_score'] = self._calculate_anomaly_confidence(AlertType.WHALE_ACTIVITY, whale_analysis)
                alert['multi_metric'] = False
                alert['source'] = 'low_volume_scan'

                if await self.alert_manager.send_alert(alert):
                    alerts_sent += 1
                    await self._track_whales_from_alert(alert, trades)
                    await self._initialize_outcome_tracking(alert, market_id)

            # Handle fresh wallet detections
            for fw_detection in fresh_wallet_detections:
                logger.info(f"💰 Fresh wallet detected in low-volume market: {market_data.get('question', 'Unknown')[:50]}...")

                # Escalate if enabled
                if self.settings.monitoring.whale_escalation_enabled:
                    await self._escalate_market(market_id, market_data)

                # Create and send fresh wallet alert
                fw_alert = await self._create_fresh_wallet_alert(market_id, market_data, fw_detection)
                if fw_alert:
                    fw_alert['source'] = 'low_volume_scan'
                    if await self.alert_manager.send_alert(fw_alert):
                        alerts_sent += 1
                        await self._track_whales_from_alert(fw_alert, trades)
                        await self._initialize_outcome_tracking(fw_alert, market_id)

            return alerts_sent

        except Exception as e:
            logger.error(f"Error analyzing low-volume market {market_id}: {e}", exc_info=True)
            return 0

    async def _update_websocket_subscriptions(self, market_ids: List[str]):
        """Update WebSocket subscriptions for real-time data"""
        # Check if WebSocket is enabled
        websocket_enabled = self.config.get('api', {}).get('websocket_enabled', True)
        
        if not websocket_enabled:
            logger.info("🔌 WebSocket disabled - using Data API only mode")
            return
            
        if not market_ids:
            return
        
        try:
            if not self.websocket_client:
                # Initialize WebSocket client with debug config
                self.websocket_client = WebSocketClient(
                    market_ids=market_ids,
                    on_trade_callback=self._handle_realtime_trade,
                    debug_config=self.debug_config
                )
                self.websocket_client.connect()
                logger.info(f"🔌 WebSocket connected for {len(market_ids)} markets")
            else:
                # Update existing subscriptions
                current_markets = set(self.websocket_client.market_ids)
                new_markets = set(market_ids)
                
                to_add = new_markets - current_markets
                to_remove = current_markets - new_markets
                
                if to_add:
                    self.websocket_client.add_markets(list(to_add))
                
                if to_remove:
                    self.websocket_client.remove_markets(list(to_remove))
        
        except Exception as e:
            logger.error(f"Failed to update WebSocket subscriptions: {e}")
    
    async def _websocket_monitor(self):
        """Monitor WebSocket connection health"""
        consecutive_failures = 0
        while self.running:
            if self.websocket_client and not self.websocket_client.is_connected:
                consecutive_failures += 1
                if consecutive_failures <= 3:  # Only try 3 times
                    logger.debug("🔌 WebSocket disconnected, attempting reconnection...")
                    try:
                        self.websocket_client.connect()
                    except Exception as e:
                        logger.debug(f"WebSocket reconnection failed: {e}")
                elif consecutive_failures == 4:
                    logger.info("🔌 WebSocket repeatedly failing, switching to Data API only mode")
                    self.websocket_client = None  # Disable WebSocket
            else:
                consecutive_failures = 0  # Reset on successful connection

            await asyncio.sleep(30)  # Check every 30 seconds

        # Log if loop exits
        logger.error(f"❌ CRITICAL: websocket_monitor loop exited! self.running={self.running}")
    
    async def _status_reporter(self):
        """Periodically report system status and activity"""
        while self.running:
            try:
                if self.debug_mode or self.show_normal_activity:
                    now = datetime.now(timezone.utc)
                    time_since_last = (now - self.last_status_report).total_seconds()

                    if time_since_last >= self.status_report_interval:
                        await self._generate_status_report()
                        self.last_status_report = now

                await asyncio.sleep(60)  # Check every minute

            except Exception as e:
                logger.error(f"Error in status reporter: {e}")
                await asyncio.sleep(60)

        # Log if loop exits
        logger.error(f"❌ CRITICAL: status_reporter loop exited! self.running={self.running}")
    
    async def _generate_status_report(self):
        """Generate comprehensive status report"""
        print(f"\n{Fore.BLUE}┌{'─' * 58}┐{Style.RESET_ALL}")
        print(f"{Fore.BLUE}│{Fore.CYAN + Style.BRIGHT} 📊 SYSTEM STATUS {datetime.now().strftime('%H:%M:%S'):>39} {Fore.BLUE}│{Style.RESET_ALL}")
        print(f"{Fore.BLUE}├{'─' * 58}┤{Style.RESET_ALL}")
        
        # Format each line to exactly 56 characters + borders
        def format_line(content):
            # Remove ALL ANSI codes to measure actual text length
            import re
            clean_content = re.sub(r'\x1b\[[0-9;]*[mGKHJ]', '', content)
            padding = max(0, 57 - len(clean_content))
            return f"{Fore.BLUE}│{Style.RESET_ALL} {content}{' ' * padding}{Fore.BLUE}│{Style.RESET_ALL}"
        
        # Basic system status
        print(format_line(f"{Fore.CYAN}Markets:{Style.RESET_ALL} {Fore.GREEN}{len(self.monitored_markets)}{Style.RESET_ALL} monitored"))
        print(format_line(f"{Fore.CYAN}Analyses:{Style.RESET_ALL} {Fore.YELLOW}{self.analysis_count}{Style.RESET_ALL} completed"))
        print(format_line(f"{Fore.CYAN}Alerts:{Style.RESET_ALL} {Fore.RED if self.alerts_generated > 0 else Fore.GREEN}{self.alerts_generated}{Style.RESET_ALL} generated"))
        
        # Baseline status
        total_markets = len(self.monitored_markets)
        markets_with_baselines = len(self.market_baselines)
        if total_markets > 0:
            baseline_percentage = (markets_with_baselines / total_markets) * 100
            if markets_with_baselines == total_markets:
                color = Fore.GREEN
                status = f"All {markets_with_baselines} markets"
            elif markets_with_baselines > 0:
                color = Fore.YELLOW
                status = f"{markets_with_baselines}/{total_markets} markets ({baseline_percentage:.0f}%)"
            else:
                color = Fore.RED
                status = "No historical baselines"
            print(format_line(f"{Fore.CYAN}Baselines:{Style.RESET_ALL} {color}{status}{Style.RESET_ALL}"))
        
        # Alert breakdown
        if self.alerts_generated > 0:
            alert_stats = await self.alert_manager.get_statistics()

            # Show by severity using enum for consistency
            severity_counts = alert_stats.get('by_severity', {})
            severity_parts = []
            for severity in AlertSeverity.get_all_severities():
                count = severity_counts.get(severity, 0)
                display_name = AlertSeverity.get_display_name(severity)
                severity_parts.append(f"{display_name}: {count}")
            
            if severity_parts:
                print(format_line(f"  {Fore.WHITE}{', '.join(severity_parts)}{Style.RESET_ALL}"))
        
        # WebSocket status
        if self.websocket_client:
            ws_stats = self.websocket_client.get_activity_stats()
            status_color = Fore.GREEN if ws_stats['is_connected'] else Fore.RED
            status_text = "Connected" if ws_stats['is_connected'] else "Disconnected"
            print(format_line(f"{Fore.CYAN}WebSocket:{Style.RESET_ALL} {status_color}{status_text}{Style.RESET_ALL}"))
        else:
            print(format_line(f"{Fore.CYAN}WebSocket:{Style.RESET_ALL} {Fore.RED}Not initialized{Style.RESET_ALL}"))
        
        # Trade history summary
        total_trades_stored = sum(len(trades) for trades in self.trade_history.values())
        print(format_line(f"{Fore.CYAN}History:{Style.RESET_ALL} {total_trades_stored} trades across {len(self.trade_history)} markets"))
        
        # Data API status
        api_operational = await self.data_api.test_connection()
        api_status_color = Fore.GREEN if api_operational else Fore.RED
        api_status_text = "Operational" if api_operational else "Failed"
        print(format_line(f"{Fore.CYAN}Data API:{Style.RESET_ALL} {api_status_color}{api_status_text}{Style.RESET_ALL}"))

        print(f"{Fore.BLUE}└{'─' * 58}┘{Style.RESET_ALL}\n")
    
    def _handle_realtime_trade(self, trade_data: Dict):
        """Handle incoming real-time trade data"""
        try:
            market_id = trade_data.get('market')
            
            if not market_id or market_id not in self.monitored_markets:
                return
            
            # Store trade in history
            if market_id not in self.trade_history:
                self.trade_history[market_id] = []
            
            self.trade_history[market_id].append(trade_data)
            
            # Keep only recent trades (last 1000 trades per market)
            if len(self.trade_history[market_id]) > 1000:
                self.trade_history[market_id] = self.trade_history[market_id][-1000:]
            
            if self.debug_config.get('show_trade_samples', False):
                market_name = self.monitored_markets.get(market_id, {}).get('question', 'Unknown')[:30]
                side = trade_data.get('side', 'UNKNOWN')
                # Map asset_id to proper outcome using token mapping
                asset_id = trade_data.get('asset_id')
                outcome = self.token_to_outcome.get(asset_id, 'UNKNOWN')
                size = trade_data.get('size', 0)
                price = trade_data.get('price', 0)
                logger.info(f"📈 Trade: {market_name}... {side} {outcome} ${size:.2f} @ {price:.3f}")
            else:
                side = trade_data.get('side', '?')
                asset_id = trade_data.get('asset_id')
                outcome = self.token_to_outcome.get(asset_id, '?')
                size = trade_data.get('size', 0)
                logger.debug(f"📈 Real-time trade: {market_id[:10]}... {side} {outcome} ${size:.2f}")
            
        except Exception as e:
            logger.error(f"Error handling real-time trade: {e}")
    
    async def _trade_polling_loop(self):
        """Poll Data API for recent trades to supplement WebSocket data"""
        last_poll_time = datetime.now(timezone.utc)
        trades_detected_this_period = 0
        poll_count = 0

        if self.debug_mode:
            print(f"{Fore.CYAN}🔄 {Style.BRIGHT}TRADE POLLING STARTED{Style.RESET_ALL}")

        while self.running:
            try:
                if not self.monitored_markets:
                    if self.debug_mode:
                        logger.info("⏳ Trade polling waiting for markets to be discovered...")
                    await asyncio.sleep(30)
                    continue

                # Get market IDs to poll (try all markets first, then limit if needed)
                all_market_ids = list(self.monitored_markets.keys())
                market_ids = all_market_ids  # Start with all markets for better coverage

                # Get recent trades from last poll
                current_time = datetime.now(timezone.utc)
                time_since_last = (current_time - last_poll_time).total_seconds()

                if time_since_last >= 15:  # Poll every 15 seconds
                    poll_count += 1
                    try:
                        # Get recent trades - only for monitored markets (increased limit for better data quality)
                        recent_trades = await self.data_api.get_recent_trades(market_ids, limit=500)

                        # Filter for trades newer than last poll
                        new_trades = []
                        cutoff_timestamp = last_poll_time.timestamp()

                        for trade in recent_trades:
                            trade_timestamp = trade.get('timestamp', 0)
                            if trade_timestamp > cutoff_timestamp:
                                new_trades.append(trade)

                        if self.debug_mode:
                            newest_info = ""
                            if new_trades:
                                newest_trade = max(new_trades, key=lambda t: t.get('timestamp', 0))
                                newest_time = datetime.fromtimestamp(newest_trade.get('timestamp', 0))
                                side = newest_trade.get('side', '?')
                                # Map asset to proper outcome using token mapping
                                asset_id = newest_trade.get('asset')
                                outcome = self.token_to_outcome.get(asset_id, '?')
                                size = newest_trade.get('size', 0)
                                price = newest_trade.get('price', 0)
                                newest_info = f", newest: {side} {outcome} ${size:.0f} @ {price:.3f}"
                            logger.info(f"🔄 Poll #{poll_count}: {len(market_ids)} markets, {len(recent_trades)} API trades, {len(new_trades)} new{newest_info}")

                        # Only show this if we actually found new trades
                        if new_trades and not self.debug_mode:
                            print(f"🔄 TRADE POLLING: Found {len(new_trades)} new trades")

                        # Process new trades
                        for trade in new_trades:
                            # Normalize trade data to match WebSocket format
                            normalized_trade = {
                                'market': trade.get('conditionId'),
                                'asset_id': trade.get('asset'),
                                'price': float(trade.get('price', 0)),
                                'size': float(trade.get('size', 0)),
                                'side': trade.get('side', '').upper(),
                                'maker': trade.get('proxyWallet'),  # Use proxyWallet as maker
                                'taker': None,  # Data API doesn't provide taker
                                'timestamp': trade.get('timestamp'),
                                'tx_hash': trade.get('transactionHash'),
                                'source': 'data_api'
                            }


                            # Process the trade as if it came from WebSocket
                            self._handle_realtime_trade(normalized_trade)
                            trades_detected_this_period += 1

                        if new_trades and (self.debug_mode or self.show_normal_activity):
                            print(f"{Fore.GREEN}🔄 {Style.BRIGHT}TRADE POLLING:{Style.RESET_ALL} Found {len(new_trades)} new trades")

                        last_poll_time = current_time

                    except Exception as e:
                        logger.error(f"Error in trade polling: {e}")
                        if self.debug_mode:
                            import traceback
                            logger.error(f"Trade polling traceback: {traceback.format_exc()}")

                await asyncio.sleep(5)  # Check every 5 seconds, poll every 15

            except Exception as e:
                logger.error(f"Error in trade polling loop: {e}")
                await asyncio.sleep(30)

        # Log if loop exits
        logger.error(f"❌ CRITICAL: trade_polling_loop exited! self.running={self.running}")

    async def _low_volume_scan_loop(self):
        """Scan low-volume markets for whale activity"""
        while self.running:
            try:
                await self._run_low_volume_scan()
                await asyncio.sleep(self.analysis_interval)  # Same frequency as high-volume markets
            except Exception as e:
                logger.error(f"Error in low-volume scan loop: {e}", exc_info=True)
                await asyncio.sleep(30)

        # Log if loop exits
        logger.error(f"❌ CRITICAL: low_volume_scan_loop exited! self.running={self.running}")

    async def _run_low_volume_scan(self):
        """Run whale-only analysis on low-volume markets"""
        if not self.low_volume_markets:
            return

        if self.debug_mode or self.show_normal_activity:
            logger.info(f"🔍 Low-volume scan: Analyzing {len(self.low_volume_markets)} markets for whales...")
        else:
            logger.debug(f"🔍 Scanning {len(self.low_volume_markets)} low-volume markets...")

        alerts_this_round = 0

        for market_id, market_data in list(self.low_volume_markets.items()):  # Use list() to avoid dict modification during iteration
            try:
                alerts_sent_count = await self._analyze_market_for_whales(market_id, market_data)
                if alerts_sent_count > 0:
                    alerts_this_round += alerts_sent_count
                elif self.debug_config.get('verbose_analysis', False):
                    question = market_data.get('question', 'Unknown')[:40]
                    logger.debug(f"   ✅ {question}... - no whales detected")

            except Exception as e:
                logger.error(f"Error scanning low-volume market {market_id}: {e}")

        # Track alerts for system status
        if alerts_this_round > 0:
            self.alerts_generated += alerts_this_round

    async def _analysis_loop(self):
        """Main analysis loop - runs detection algorithms"""
        while self.running:
            try:
                await self._run_market_analysis()
                await asyncio.sleep(self.analysis_interval)
            except Exception as e:
                logger.error(f"Error in analysis loop: {e}")
                await asyncio.sleep(30)

        # Log if loop exits
        logger.error(f"❌ CRITICAL: analysis_loop exited! self.running={self.running}")
    
    async def _run_market_analysis(self):
        """Run analysis on all monitored markets"""
        if not self.monitored_markets:
            return
        
        self.analysis_count += 1
        
        if self.debug_mode or self.show_normal_activity:
            logger.info(f"🔍 Analysis #{self.analysis_count}: Analyzing {len(self.monitored_markets)} markets...")
        else:
            logger.debug(f"🔍 Analyzing {len(self.monitored_markets)} markets...")
        
        alerts_this_round = 0
        markets_with_data = 0
        
        for market_id, market_data in self.monitored_markets.items():
            try:
                alerts_sent_count = await self._analyze_single_market(market_id, market_data)
                if alerts_sent_count > 0:
                    alerts_this_round += alerts_sent_count
                    markets_with_data += 1
                elif self.debug_config.get('verbose_analysis', False):
                    question = market_data.get('question', 'Unknown')[:40]
                    logger.debug(f"   ✅ {question}... - no anomalies detected")
                    
            except Exception as e:
                logger.error(f"Error analyzing market {market_id}: {e}")
        
        # Track alerts for system status
        if alerts_this_round > 0:
            self.alerts_generated += alerts_this_round
    
    async def _analyze_single_market(self, market_id: str, market_data: Dict):
        """Analyze a single market for unusual activity
        
        Returns:
            int: Number of alerts successfully sent
        """
        # Get combined trade data (historical + real-time)
        trades = await self._get_market_trades(market_id)
        
        if not trades:
            return 0
        
        # Run all detection algorithms and collect results
        alerts = []
        
        # Volume detection - use historical baseline if available
        historical_baseline = self.market_baselines.get(market_id)
        volume_analysis = self.volume_detector.analyze_volume_pattern(
            trades, market_id, historical_baseline, self.token_to_outcome
        )
        
        # Log baseline source for monitoring
        if volume_analysis.get('baseline_source') == 'historical':
            logger.debug(f"🎯 Volume analysis using historical baseline for {market_id[:10]}...")
        elif volume_analysis.get('baseline_source') == 'recent_trades':
            logger.warning(f"⚠️ Volume analysis using recent trades baseline for {market_id[:10]}... (no historical data)")
        
        # Whale detection
        whale_analysis = self.whale_detector.detect_whale_activity(trades)

        # Price movement detection
        price_analysis = self.price_detector.detect_price_movement(trades)

        # Coordination detection
        coordination_analysis = self.coordination_detector.detect_coordinated_buying(trades)

        # Fresh wallet detection - returns list of individual detections
        fresh_wallet_detections = await self.fresh_wallet_detector.detect_fresh_wallet_activity(trades)

        # Multi-metric confidence evaluation
        detection_results = {
            AlertType.VOLUME_SPIKE: volume_analysis,
            AlertType.WHALE_ACTIVITY: whale_analysis,
            AlertType.UNUSUAL_PRICE_MOVEMENT: price_analysis,
            AlertType.COORDINATED_TRADING: coordination_analysis
        }

        # Evaluate alerts with multi-metric confidence (excluding fresh wallet for now)
        alerts = await self._evaluate_multi_metric_alerts(
            market_id, market_data, detection_results
        )

        # Handle fresh wallet detections separately (one alert per fresh wallet)
        for fw_detection in fresh_wallet_detections:
            # Create individual fresh wallet alert
            fw_alert = await self._create_fresh_wallet_alert(
                market_id, market_data, fw_detection
            )
            if fw_alert:
                alerts.append(fw_alert)

        # Send alerts and count successful ones
        alerts_sent_successfully = 0
        for alert in alerts:
            if await self.alert_manager.send_alert(alert):
                alerts_sent_successfully += 1

                # Track whales for whale/coordination/fresh_wallet alerts
                await self._track_whales_from_alert(alert, trades)

                # Initialize outcome tracking for the alert
                await self._initialize_outcome_tracking(alert, market_id)

        return alerts_sent_successfully
    
    async def _get_market_trades(self, market_id: str) -> List[Dict]:
        """Get combined trade data for a market"""
        trades = []
        
        # Prioritize Data API since WebSocket is having issues
        try:
            # Get recent trades first (increased limit for better analysis)
            recent_trades = await self.data_api.get_recent_trades([market_id], limit=VolumeConstants.MAX_TRADES_PER_REQUEST)
            trades.extend(recent_trades)
            logger.debug(f"Fetched {len(recent_trades)} recent trades for {market_id[:10]}...")
        except Exception as e:
            logger.debug(f"Could not fetch recent trades for {market_id}: {e}")
        
        # Add any real-time trades from WebSocket if available
        if market_id in self.trade_history:
            realtime_trades = self.trade_history[market_id][-50:]  # Last 50 real-time trades
            trades.extend(realtime_trades)
            logger.debug(f"Added {len(realtime_trades)} real-time trades for {market_id[:10]}...")
        
        # Remove duplicates and sort by timestamp
        unique_trades = {}
        for trade in trades:
            # Use transaction hash or combination of fields as unique key
            key = trade.get('tx_hash') or trade.get('id') or f"{trade.get('timestamp')}_{trade.get('price')}_{trade.get('size')}"
            unique_trades[key] = trade
        
        sorted_trades = sorted(unique_trades.values(),
                             key=lambda t: t.get('timestamp', ''),
                             reverse=True)

        # Debug: Log sample trade structure to identify outcome field
        if sorted_trades and len(sorted_trades) > 0:
            sample = sorted_trades[0]
            logger.debug(f"📋 Sample trade fields for {market_id[:10]}: {list(sample.keys())}")
            # Log relevant fields that might contain outcome info
            relevant_fields = {k: v for k, v in sample.items() if k in ['asset', 'asset_id', 'token_id', 'outcome', 'outcome_id', 'side', 'maker', 'taker']}
            if relevant_fields:
                logger.debug(f"📋 Relevant fields: {relevant_fields}")

        return sorted_trades[:VolumeConstants.MAX_HISTORICAL_TRADES]  # Return most recent trades
    
    async def _evaluate_multi_metric_alerts(self, market_id: str, market_data: Dict, 
                                          detection_results: Dict) -> List[Dict]:
        """
        Evaluate detections with multi-metric confidence requirements
        Only creates alerts when multiple indicators align or single indicators are very strong
        """
        alerts = []
        
        # Count active anomalies and calculate confidence scores
        active_anomalies = []
        total_confidence_score = 0
        
        for alert_type, analysis in detection_results.items():
            if analysis.get('anomaly', False):
                # Calculate confidence score for each anomaly type
                confidence_score = self._calculate_anomaly_confidence(alert_type, analysis)
                
                active_anomalies.append({
                    'type': alert_type,
                    'analysis': analysis,
                    'confidence': confidence_score
                })
                total_confidence_score += confidence_score
        
        # Apply multi-metric logic
        if len(active_anomalies) == 0:
            return []  # No anomalies detected
        
        elif len(active_anomalies) == 1:
            # Single anomaly - require very high confidence
            anomaly = active_anomalies[0]
            if anomaly['confidence'] >= ConfidenceThresholds.SINGLE_ANOMALY_THRESHOLD:
                # Record activity and check cross-market filtering
                severity = self._determine_severity(anomaly['type'], anomaly['analysis'])
                self._record_market_activity(market_id, anomaly['type'], anomaly['analysis'], severity)
                
                should_filter, filter_reason = self._should_filter_cross_market_activity(
                    market_id, anomaly['type'], anomaly['analysis']
                )
                
                if not should_filter:
                    alert = await self._create_alert(
                        market_id, market_data, anomaly['type'], anomaly['analysis'], severity.value
                    )
                    alert['filter_reason'] = filter_reason
                    alert['confidence_score'] = anomaly['confidence']
                    alert['multi_metric'] = False
                    alerts.append(alert)
                    logger.info(f"🔥 HIGH-CONFIDENCE single alert: {anomaly['type']} for {market_id[:10]}... (confidence: {anomaly['confidence']:.1f})")
                else:
                    logger.info(f"🚫 High-confidence alert filtered: {anomaly['type']} for {market_id[:10]}... - {filter_reason}")
        
        elif len(active_anomalies) >= 2:
            # Multiple anomalies - create composite alert with lower individual thresholds
            if total_confidence_score >= ConfidenceThresholds.MULTI_ANOMALY_THRESHOLD:
                # Find primary anomaly (highest confidence)
                primary_anomaly = max(active_anomalies, key=lambda x: x['confidence'])
                
                # Record activity for primary anomaly
                severity = AlertSeverity.CRITICAL if total_confidence_score >= ConfidenceThresholds.CRITICAL_THRESHOLD else AlertSeverity.HIGH
                self._record_market_activity(market_id, primary_anomaly['type'], primary_anomaly['analysis'], severity)
                
                should_filter, filter_reason = self._should_filter_cross_market_activity(
                    market_id, primary_anomaly['type'], primary_anomaly['analysis']
                )
                
                if not should_filter:
                    # Create composite alert with all anomaly information
                    alert = await self._create_alert(
                        market_id, market_data, primary_anomaly['type'], primary_anomaly['analysis'], severity.value
                    )
                    alert['filter_reason'] = filter_reason
                    alert['confidence_score'] = total_confidence_score
                    alert['multi_metric'] = True
                    alert['supporting_anomalies'] = [
                        {'type': a['type'], 'confidence': a['confidence']} 
                        for a in active_anomalies if a != primary_anomaly
                    ]
                    alerts.append(alert)
                    logger.info(f"🎯 MULTI-METRIC alert: {primary_anomaly['type']} + {len(active_anomalies)-1} others for {market_id[:10]}... (total confidence: {total_confidence_score:.1f})")
                else:
                    logger.info(f"🚫 Multi-metric alert filtered: {primary_anomaly['type']} for {market_id[:10]}... - {filter_reason}")
        
        return alerts
    
    def _calculate_anomaly_confidence(self, alert_type: AlertType, analysis: Dict) -> float:
        """Calculate confidence score for a specific anomaly (0-10 scale)"""
        confidence = 0.0
        
        if alert_type == AlertType.VOLUME_SPIKE:
            # Base confidence on anomaly score and baseline quality
            confidence += min(analysis.get('max_anomaly_score', 0) * 1.5, 8.0)
            if analysis.get('baseline_source') == BaselineType.HISTORICAL.value:
                confidence += ConfidenceThresholds.HISTORICAL_BASELINE_BONUS
            # Add bonus for strong directional bias (similar to whale activity)
            outcome_imbalance = analysis.get('outcome_imbalance', 0)
            side_imbalance = analysis.get('side_imbalance', 0)
            # Use the stronger of the two imbalances
            max_imbalance = max(outcome_imbalance, side_imbalance)
            if max_imbalance > 0.7:
                confidence += ConfidenceThresholds.DIRECTIONAL_BIAS_BONUS
        
        elif alert_type == AlertType.WHALE_ACTIVITY:
            # Base confidence on whale volume and coordination
            whale_volume = analysis.get('total_whale_volume', 0)
            coordination = analysis.get('coordination', {})
            
            confidence += min(whale_volume / 10000, 6.0)  # Up to 6 points for volume
            if coordination.get('coordinated', False):
                confidence += ConfidenceThresholds.COORDINATION_BONUS
            if analysis.get('direction_imbalance', 0) > 0.8:
                confidence += ConfidenceThresholds.DIRECTIONAL_BIAS_BONUS
        
        elif alert_type == AlertType.UNUSUAL_PRICE_MOVEMENT:
            # Base confidence on trigger intensity
            triggers = analysis.get('triggers', {})
            confidence += sum(2.0 for trigger in triggers.values() if trigger)
            
            # Bonus for multiple simultaneous triggers  
            active_triggers = sum(1 for t in triggers.values() if t)
            if active_triggers >= 3:
                confidence += ConfidenceThresholds.MULTI_TRIGGER_BONUS
        
        elif alert_type == AlertType.COORDINATED_TRADING:
            # Base confidence on coordination score
            coord_score = analysis.get('coordination_score', 0)
            confidence += coord_score * 8.0  # Scale 0-1 to 0-8

            # Bonus for wash trading detection
            if analysis.get('wash_trading_detected', False):
                confidence += ConfidenceThresholds.WASH_TRADING_BONUS

        elif alert_type == AlertType.FRESH_WALLET_LARGE_BET:
            # Fresh wallet is high-confidence insider signal
            base_confidence = 7.0

            bet_size = analysis.get('bet_size', 0)

            # Bonus for large bet sizes
            if bet_size >= 10000:
                base_confidence += 1.5  # $10k+ bet
            elif bet_size >= 5000:
                base_confidence += 1.0  # $5k+ bet

            # Bonus for truly first trade ever
            previous_trades = analysis.get('previous_trade_count', 0)
            if previous_trades == 0:
                base_confidence += 1.0  # First-ever trade

            confidence = base_confidence

        return min(confidence, ConfidenceThresholds.MAX_CONFIDENCE_SCORE)
    
    def _determine_severity(self, alert_type: AlertType, analysis: Dict) -> AlertSeverity:
        """Determine alert severity based on alert type and analysis"""
        if alert_type == AlertType.VOLUME_SPIKE:
            return AlertSeverity.HIGH if analysis.get('max_anomaly_score', 0) > 5 else AlertSeverity.MEDIUM
        elif alert_type == AlertType.WHALE_ACTIVITY:
            return AlertSeverity.HIGH if analysis.get('total_whale_volume', 0) > 50000 else AlertSeverity.MEDIUM
        elif alert_type == AlertType.UNUSUAL_PRICE_MOVEMENT:
            return AlertSeverity.CRITICAL if any(analysis.get('triggers', {}).values()) else AlertSeverity.MEDIUM
        elif alert_type == AlertType.COORDINATED_TRADING:
            return AlertSeverity.CRITICAL if analysis.get('coordination_score', 0) > 0.8 else AlertSeverity.HIGH
        elif alert_type == AlertType.FRESH_WALLET_LARGE_BET:
            bet_size = analysis.get('bet_size', 0)
            if bet_size >= 10000:
                return AlertSeverity.CRITICAL  # $10k+ first bet
            elif bet_size >= 5000:
                return AlertSeverity.HIGH  # $5k+ first bet
            else:
                return AlertSeverity.MEDIUM  # $2k+ first bet
        return AlertSeverity.MEDIUM
    
    def _record_market_activity(self, market_id: str, alert_type: AlertType, analysis: Dict, severity: AlertSeverity):
        """Record market activity for cross-market analysis"""
        current_time = datetime.now(timezone.utc)
        
        # Clean old activities outside the time window
        cutoff_time = current_time - timedelta(minutes=self.cross_market_window_minutes)
        for mid in list(self.recent_market_activities.keys()):
            self.recent_market_activities[mid] = [
                activity for activity in self.recent_market_activities[mid]
                if activity['timestamp'] > cutoff_time
            ]
            if not self.recent_market_activities[mid]:
                del self.recent_market_activities[mid]
        
        # Record new activity
        if market_id not in self.recent_market_activities:
            self.recent_market_activities[market_id] = []
        
        activity = {
            'timestamp': current_time,
            'alert_type': alert_type.value,  # Store as string for JSON serialization
            'severity': severity.value,      # Store as string for JSON serialization
            'analysis': analysis
        }
        
        self.recent_market_activities[market_id].append(activity)
    
    def _should_filter_cross_market_activity(self, market_id: str, alert_type: AlertType, analysis: Dict) -> Tuple[bool, str]:
        """
        Check if this alert should be filtered due to cross-market activity
        
        Returns:
            - should_filter: bool - True if alert should be filtered
            - reason: str - Reason for filtering decision
        """
        # Count similar activities across markets in recent time window
        similar_activities = 0
        total_markets_with_activity = len(self.recent_market_activities)
        
        if total_markets_with_activity < ConfidenceThresholds.MIN_SIMILAR_MARKETS:
            # Need at least 3 markets with activity to consider platform-wide
            return False, f"Only {total_markets_with_activity} markets active"
        
        # Count markets with similar alert types
        markets_with_similar_alerts = 0
        for mid, activities in self.recent_market_activities.items():
            if mid == market_id:
                continue  # Don't count self
            
            # Check for similar alert types in recent activities
            for activity in activities[-3:]:  # Check last 3 activities per market
                if activity['alert_type'] == alert_type.value:
                    markets_with_similar_alerts += 1
                    break  # Count each market only once
        
        # Filter if 3+ other markets show similar anomalous activity
        if markets_with_similar_alerts >= ConfidenceThresholds.MIN_SIMILAR_MARKETS:
            return True, f"Platform-wide activity: {markets_with_similar_alerts + 1} markets show {alert_type}"
        
        # Special case for volume spikes - check if overall platform volume is high
        if alert_type == AlertType.VOLUME_SPIKE:
            volume_spike_markets = 0
            for activities in self.recent_market_activities.values():
                for activity in activities[-2:]:  # Check last 2 activities per market
                    if (activity['alert_type'] == AlertType.VOLUME_SPIKE.value and 
                        activity.get('analysis', {}).get('max_anomaly_score', 0) > 3):
                        volume_spike_markets += 1
                        break
            
            if volume_spike_markets >= ConfidenceThresholds.VOLUME_SURGE_MARKETS:
                return True, f"Platform volume surge: {volume_spike_markets} markets with volume spikes"
        
        # Allow the alert - not platform-wide activity
        return False, f"Isolated activity (only {markets_with_similar_alerts} similar markets)"

    async def _create_fresh_wallet_alert(self, market_id: str, market_data: Dict,
                                         fw_detection: Dict) -> Optional[Dict]:
        """
        Create alert for a fresh wallet detection.

        Args:
            market_id: Market identifier
            market_data: Market metadata
            fw_detection: Fresh wallet detection dict with wallet details

        Returns:
            Alert dict or None if creation fails
        """
        try:
            alert_type = AlertType.FRESH_WALLET_LARGE_BET

            # Determine severity based on bet size
            severity = self._determine_severity(alert_type, fw_detection)

            # Calculate confidence score
            confidence_score = self._calculate_anomaly_confidence(alert_type, fw_detection)

            # Create alert using standard method
            alert = await self._create_alert(
                market_id,
                market_data,
                alert_type,
                fw_detection,
                severity.value
            )

            if alert:
                alert['confidence_score'] = confidence_score
                alert['multi_metric'] = False  # Fresh wallet alerts are standalone

            return alert

        except Exception as e:
            logger.error(f"Failed to create fresh wallet alert: {e}")
            return None

    async def _create_alert(self, market_id: str, market_data: Dict, alert_type,
                          analysis: Dict, severity: str) -> Dict:
        """Create an alert from detection results"""
        # Convert AlertType enum to string if needed
        alert_type_str = alert_type.value if hasattr(alert_type, 'value') else str(alert_type)

        # Extract price with fallbacks
        last_price = self._extract_market_price(market_data, market_id)

        # Extract outcomePrices for YES/NO display
        outcome_prices_raw = market_data.get('outcomePrices')
        outcome_prices = None
        if outcome_prices_raw:
            try:
                if isinstance(outcome_prices_raw, str):
                    import json
                    outcome_prices = json.loads(outcome_prices_raw)
                elif isinstance(outcome_prices_raw, list):
                    outcome_prices = outcome_prices_raw
            except (ValueError, json.JSONDecodeError):
                pass

        # Extract slug - prefer event slug over market slug
        slug = None
        related_markets = []
        events = market_data.get('events', [])
        if events and len(events) > 0:
            event_slug = events[0].get('slug')
            slug = event_slug  # Use event slug (shorter, correct URL)

            # Fetch related markets in the same group
            related_markets = await self._get_related_markets(event_slug, market_id)
        if not slug:
            slug = market_data.get('slug')  # Fallback to market slug for older markets

        return {
            'market_id': market_id,
            'market_question': market_data.get('question', 'Unknown Market'),
            'alert_type': alert_type_str,
            'severity': severity,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'analysis': analysis,
            'market_data': {
                'volume24hr': market_data.get('volume24hr', 0),
                'lastTradePrice': last_price,
                'outcomePrices': outcome_prices,  # Include full price array for YES/NO display
                'slug': slug  # Include event slug for market URL generation
            },
            'related_markets': related_markets,  # Include related outcomes for grouped markets
            'recommended_action': self._get_recommended_action(alert_type_str, severity, analysis)
        }

    def _extract_market_price(self, market_data: Dict, market_id: str = None) -> float:
        """Extract current market price with multiple fallbacks

        Args:
            market_data: Market data from Gamma API
            market_id: Market ID for trade history fallback

        Returns:
            Current price as float (0.0-1.0 range)
        """
        # Try outcomePrices (Gamma API field for YES/NO prices)
        outcome_prices = market_data.get('outcomePrices')
        if outcome_prices:
            try:
                # Handle both array and JSON string formats
                if isinstance(outcome_prices, str):
                    import json
                    outcome_prices = json.loads(outcome_prices)

                # Get YES price (first outcome)
                if isinstance(outcome_prices, list) and len(outcome_prices) > 0:
                    price = float(outcome_prices[0])
                    if 0 <= price <= 1:
                        return price
            except (ValueError, TypeError, json.JSONDecodeError) as e:
                logger.debug(f"Failed to parse outcomePrices: {e}")

        # Fallback: Try to get from recent trades
        if market_id and market_id in self.trade_history:
            trades = self.trade_history[market_id]
            if trades:
                try:
                    # Get most recent trade price
                    last_trade = trades[-1]
                    price = float(last_trade.get('price', 0))
                    if 0 < price <= 1:
                        return price
                except (ValueError, TypeError, KeyError):
                    pass

        # Final fallback: return 0
        return 0.0

    async def _get_related_markets(self, event_slug: str, current_market_id: str) -> List[Dict]:
        """
        Find other markets in the same event group

        Args:
            event_slug: The event slug shared by grouped markets
            current_market_id: ID of the current market to exclude

        Returns:
            List of dicts with 'question', 'yes_price', and 'no_price' for related markets
        """
        related = []

        # First, check monitored markets (fast path)
        for market_id, market_data in self.monitored_markets.items():
            if market_id == current_market_id:
                continue  # Skip the current market

            # Check if this market shares the same event slug
            events = market_data.get('events', [])
            if events and len(events) > 0:
                other_slug = events[0].get('slug')
                if other_slug == event_slug:
                    # Extract question and price
                    question = market_data.get('question', '')
                    outcome_prices = market_data.get('outcomePrices')

                    if outcome_prices and isinstance(outcome_prices, list) and len(outcome_prices) >= 2:
                        try:
                            yes_price = float(outcome_prices[0])
                            no_price = float(outcome_prices[1])
                            related.append({
                                'question': question,
                                'yes_price': yes_price,
                                'no_price': no_price
                            })
                        except (ValueError, TypeError):
                            pass  # Skip if price parsing fails

        # If we found related markets in monitored list, use them
        if len(related) > 0:
            related.sort(key=lambda x: x['yes_price'], reverse=True)
            return related[:6]

        # Otherwise, fetch from Gamma API (markets may not meet volume threshold)
        try:
            gamma_api = "https://gamma-api.polymarket.com"
            async with aiohttp.ClientSession() as session:
                # Query API for markets filtered by event slug
                # Note: Gamma API doesn't have a direct event slug filter, so we fetch by limit and filter client-side
                url = f"{gamma_api}/markets"
                params = {
                    'limit': 100,  # Fetch enough to find related markets
                    '_lt': 'true'   # Include active markets
                }

                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        data = await resp.json()

                        for market in data:
                            # Skip current market
                            if market.get('id') == current_market_id:
                                continue

                            # Check if this market has the same event slug
                            events = market.get('events', [])
                            if events and len(events) > 0:
                                market_event_slug = events[0].get('slug')
                                if market_event_slug == event_slug:
                                    # Extract question and prices
                                    question = market.get('question', '')
                                    outcome_prices = market.get('outcomePrices')

                                    if outcome_prices and isinstance(outcome_prices, list) and len(outcome_prices) >= 2:
                                        try:
                                            yes_price = float(outcome_prices[0])
                                            no_price = float(outcome_prices[1])
                                            related.append({
                                                'question': question,
                                                'yes_price': yes_price,
                                                'no_price': no_price
                                            })
                                        except (ValueError, TypeError):
                                            pass
        except Exception as e:
            logger.debug(f"Failed to fetch related markets from API for event '{event_slug}': {e}")

        # Sort by probability descending (most likely outcomes first)
        related.sort(key=lambda x: x['yes_price'], reverse=True)

        # Return max 6 related outcomes
        return related[:6]

    def _get_recommended_action(self, alert_type: str, severity: str, analysis: Dict) -> str:
        """Get recommended action based on alert type and severity"""
        if severity == 'CRITICAL':
            return "🚨 IMMEDIATE: Strong insider signal - consider following the trend"
        elif severity == 'HIGH':
            if alert_type == 'WHALE_ACTIVITY':
                direction = analysis.get('dominant_side', 'BUY')
                return f"🐋 Consider {direction} position - whale accumulation detected"
            elif alert_type == 'COORDINATED_TRADING':
                return "🤝 Coordinated activity detected - monitor for entry opportunity"
            else:
                return "📈 High confidence unusual activity - investigate immediately"
        elif severity == 'MEDIUM':
            return "👀 Monitor closely - potential early signal"
        else:
            return "📝 Note activity - wait for confirmation"

    async def _track_whales_from_alert(self, alert: Dict, trades: List[Dict]) -> None:
        """Track whale addresses from whale/coordination alerts"""
        try:
            alert_type_str = alert.get('alert_type', '')

            # Only track whales for whale and coordination alerts
            if alert_type_str not in ['WHALE_ACTIVITY', 'COORDINATED_TRADING']:
                return

            analysis = alert.get('analysis', {})

            # Get alert ID from the recently saved alert in database
            # We need to query the most recent alert for this market
            market_id = alert.get('market_id')
            from database import AlertRepository
            async with self.db_manager.session() as session:
                alert_repo = AlertRepository(session)
                recent_alerts = await alert_repo.get_recent_alerts(
                    hours=0.1,  # Last 6 minutes
                    market_id=market_id,
                    alert_type=alert_type_str,
                    limit=1
                )

                if not recent_alerts:
                    logger.warning(f"Could not find alert ID for whale tracking")
                    return

                alert_id = recent_alerts[0].id

            # Track whales based on alert type
            if alert_type_str == 'WHALE_ACTIVITY':
                # Get whale breakdown from analysis (dict with addresses as keys)
                whale_breakdown = analysis.get('whale_breakdown', {})

                if not whale_breakdown:
                    logger.debug(f"No whale breakdown found in analysis for {market_id[:10]}...")
                    return

                for address, whale_data in whale_breakdown.items():
                    # Skip invalid addresses
                    if not address or address == 'unknown':
                        continue

                    trade_data = {
                        'volume_usd': whale_data.get('total_volume', 0),
                        'side': whale_data.get('dominant_side', 'BUY'),
                        'market_id': market_id,
                        'metrics': {
                            'trade_price': whale_data.get('avg_price', 0),
                            'trade_count': whale_data.get('trade_count', 1),
                            'avg_trade_size': whale_data.get('avg_trade_size', 0)
                        }
                    }

                    from common import WhaleRole
                    # Primary actor if largest whale, otherwise participant
                    role = WhaleRole.PRIMARY_ACTOR if whale_data.get('total_volume', 0) == analysis.get('largest_whale_volume', 0) else WhaleRole.PARTICIPANT

                    await self.whale_tracker.track_whale(
                        address=address,
                        trade_data=trade_data,
                        alert_id=alert_id,
                        tags=['whale_activity'],
                        whale_role=role
                    )

                logger.debug(f"Tracked {len(whale_breakdown)} whale addresses from alert")

            elif alert_type_str == 'COORDINATED_TRADING':
                # Get coordinated wallets from analysis
                cluster_wallets = analysis.get('cluster_wallets', [])

                for wallet_info in cluster_wallets:
                    address = wallet_info.get('address')
                    if not address:
                        continue

                    trade_data = {
                        'volume_usd': wallet_info.get('total_volume', 0),
                        'side': wallet_info.get('side', 'BUY'),
                        'market_id': market_id,
                        'metrics': {
                            'trade_count': wallet_info.get('trade_count', 1),
                            'avg_trade_size': wallet_info.get('avg_size', 0)
                        }
                    }

                    from common import WhaleRole
                    await self.whale_tracker.track_whale(
                        address=address,
                        trade_data=trade_data,
                        alert_id=alert_id,
                        tags=['coordination', 'cluster'],
                        whale_role=WhaleRole.COORDINATOR
                    )

                logger.debug(f"Tracked {len(cluster_wallets)} coordinated wallets from alert")

        except Exception as e:
            logger.error(f"Failed to track whales from alert: {e}", exc_info=True)

    async def _initialize_outcome_tracking(self, alert: Dict, market_id: str) -> None:
        """Initialize outcome tracking for an alert"""
        try:
            # Get alert ID from database
            alert_type_str = alert.get('alert_type', '')
            from database import AlertRepository
            async with self.db_manager.session() as session:
                alert_repo = AlertRepository(session)
                recent_alerts = await alert_repo.get_recent_alerts(
                    hours=0.1,  # Last 6 minutes
                    market_id=market_id,
                    alert_type=alert_type_str,
                    limit=1
                )

                if not recent_alerts:
                    logger.warning(f"Could not find alert ID for outcome tracking")
                    return

                alert_id = recent_alerts[0].id

            # Get current market price
            market_data = alert.get('market_data', {})
            current_price = float(market_data.get('lastTradePrice', 0.5))

            # Determine predicted direction based on alert type and analysis
            analysis = alert.get('analysis', {})
            predicted_direction = 'BUY'  # Default

            if alert_type_str == 'WHALE_ACTIVITY':
                dominant_side = analysis.get('dominant_side', 'BUY')
                predicted_direction = dominant_side
            elif alert_type_str == 'COORDINATED_TRADING':
                # For coordination, use the side with more activity
                predicted_direction = analysis.get('dominant_side', 'BUY')
            elif alert_type_str == 'VOLUME_SPIKE':
                # For volume spikes, use the dominant side (BUY/SELL), not outcome (YES/NO)
                predicted_direction = analysis.get('dominant_side', 'BUY')
            elif alert_type_str == 'FRESH_WALLET_LARGE_BET':
                # For fresh wallet bets, use the trade side
                predicted_direction = analysis.get('side', 'BUY')

            # Create outcome record
            await self.outcome_tracker.create_outcome_record(
                alert_id=alert_id,
                market_id=market_id,
                current_price=current_price,
                predicted_direction=predicted_direction
            )

            logger.debug(f"Initialized outcome tracking for alert {alert_id} (price: ${current_price:.3f}, direction: {predicted_direction})")

        except Exception as e:
            logger.error(f"Failed to initialize outcome tracking: {e}", exc_info=True)

    async def _outcome_update_loop(self):
        """Background task to update alert outcomes periodically"""
        # Wait a bit before starting to allow alerts to be created
        await asyncio.sleep(300)  # 5 minutes

        while self.running:
            try:
                logger.debug("🔄 Updating alert outcomes...")
                updated_count = await self.outcome_tracker.update_price_outcomes(batch_size=50)

                if updated_count > 0:
                    logger.info(f"📊 Updated {updated_count} alert outcomes")

                # Update every 15 minutes
                await asyncio.sleep(900)

            except Exception as e:
                logger.error(f"Error in outcome update loop: {e}", exc_info=True)
                await asyncio.sleep(300)  # Wait 5 minutes before retrying

        # Log if loop exits
        logger.error(f"❌ CRITICAL: outcome_update_loop exited! self.running={self.running}")
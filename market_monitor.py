"""
Market Monitor Orchestrator
Coordinates data sources and detection algorithms for insider trading detection
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
import json
from pathlib import Path
from colorama import init, Fore, Back, Style

# Initialize colorama
init(autoreset=True)

from data_sources.data_api_client import DataAPIClient
from data_sources.websocket_client import WebSocketClient
from detection import VolumeDetector, WhaleDetector, PriceDetector, CoordinationDetector
from alerts.alert_manager import AlertManager
from config.settings import Settings
from common import (
    AlertType, AlertSeverity, BaselineType, MarketStatus, DetectorStatus,
    AlertMetadata, Alert, MarketBaseline, DetectionResult,
    ConfidenceThresholds, TimeConstants, VolumeConstants
)

logger = logging.getLogger(__name__)

class MarketMonitor:
    """Main orchestrator for market monitoring and insider detection"""
    
    def __init__(self, config_path: str = "insider_config.json"):
        # Load configuration
        self.config = self._load_config(config_path)
        self.settings = Settings(self.config)
        
        # Debug configuration
        self.debug_config = self.config.get('debug', {})
        self.debug_mode = self.debug_config.get('debug_mode', False)
        self.show_normal_activity = self.debug_config.get('show_normal_activity', False)
        
        # Initialize data sources
        self.data_api = DataAPIClient()
        self.websocket_client = None
        
        # Initialize detection algorithms
        self.volume_detector = VolumeDetector(self.config)
        self.whale_detector = WhaleDetector(self.config)
        self.price_detector = PriceDetector(self.config)
        self.coordination_detector = CoordinationDetector(self.config)
        
        # Initialize alert manager
        self.alert_manager = AlertManager(self.settings)
        
        # Market data storage
        self.monitored_markets = {}
        self.market_baselines = {}
        self.trade_history = {}
        self.token_to_outcome = {}  # Maps token ID to "Yes" or "No"
        
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
            if config_file.exists():
                with open(config_file) as f:
                    config = json.load(f)
                logger.info(f"Loaded configuration from {config_path}")
                return config
        except Exception as e:
            logger.warning(f"Failed to load config from {config_path}: {e}")
        
        # Return default configuration
        return self._get_default_config()
    
    def _get_default_config(self) -> Dict:
        """Get default configuration"""
        return {
            "monitoring": {
                "volume_threshold": 1000,
                "max_markets": 50,
                "check_interval": 60,
                "sort_by_volume": True
            },
            "detection": {
                "volume_thresholds": {
                    "volume_spike_multiplier": 3.0,
                    "z_score_threshold": 3.0
                },
                "whale_thresholds": {
                    "whale_threshold_usd": 10000,
                    "coordination_threshold": 0.7,
                    "min_whales_for_coordination": 3
                },
                "price_thresholds": {
                    "rapid_movement_pct": 15,
                    "price_movement_std": 2.5,
                    "volatility_spike_multiplier": 3.0,
                    "momentum_threshold": 0.8
                },
                "coordination_thresholds": {
                    "min_coordinated_wallets": 5,
                    "coordination_time_window": 30,
                    "directional_bias_threshold": 0.8,
                    "burst_intensity_threshold": 3.0
                }
            },
            "alerts": {
                "discord_webhook": "",
                "min_severity": "MEDIUM"
            }
        }
    
    async def start_monitoring(self):
        """Start the market monitoring system"""
        logger.info("🚀 Starting Market Monitor")
        
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
            asyncio.create_task(self._trade_polling_loop(), name="trade_polling")  # NEW: Real-time trade polling
        ]
        
        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            logger.error(f"Error in monitoring tasks: {e}")
        finally:
            await self.stop_monitoring()
    
    async def stop_monitoring(self):
        """Stop the monitoring system"""
        logger.info("🛑 Stopping Market Monitor")
        self.running = False
        
        if self.websocket_client:
            self.websocket_client.disconnect()
    
    async def _test_connections(self) -> bool:
        """Test all external connections"""
        logger.info("🔍 Testing connections...")
        
        # Test Data API
        if not self.data_api.test_connection():
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
    
    async def _discover_markets(self):
        """Discover high-volume markets to monitor"""
        logger.info("🔍 Discovering markets...")
        
        # Use the existing gamma API logic from insider_bot.py
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            gamma_api = "https://gamma-api.polymarket.com"
            volume_threshold = self.config.get('monitoring', {}).get('volume_threshold', 1000)
            max_markets = self.config.get('monitoring', {}).get('max_markets', 50)
            sort_by_volume = self.config.get('monitoring', {}).get('sort_by_volume', True)
            
            async with session.get(f"{gamma_api}/markets?active=true&closed=false&limit={max_markets}") as resp:
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
                
                # Filter and update monitored markets
                new_market_ids = []
                updated_markets = {}
                websocket_token_ids = []
                
                for market in markets:
                    try:
                        condition_id = market.get('conditionId', '')
                        volume = float(market.get('volume24hr', 0))
                        
                        if condition_id and volume >= volume_threshold:
                            new_market_ids.append(condition_id)
                            updated_markets[condition_id] = market
                            
                            # Collect token IDs for WebSocket subscription and outcome mapping
                            token_ids_raw = market.get('clobTokenIds', [])
                            if token_ids_raw:
                                try:
                                    # Parse JSON string if needed
                                    if isinstance(token_ids_raw, str):
                                        token_ids = json.loads(token_ids_raw)
                                    else:
                                        token_ids = token_ids_raw
                                    
                                    if isinstance(token_ids, list):
                                        websocket_token_ids.extend(token_ids[:2])  # Take first 2 from each market
                                        
                                        # Map token IDs to outcomes (assuming first token is "Yes", second is "No")
                                        if len(token_ids) >= 2:
                                            self.token_to_outcome[token_ids[0]] = "Yes"
                                            self.token_to_outcome[token_ids[1]] = "No"
                                except (json.JSONDecodeError, TypeError) as e:
                                    logger.debug(f"Could not parse token IDs for {condition_id}: {e}")
                            
                            # Initialize baseline if new market
                            if condition_id not in self.monitored_markets:
                                await self._initialize_market_baseline(condition_id, market)
                    
                    except (KeyError, ValueError, TypeError) as e:
                        continue
                
                # Update monitored markets
                old_count = len(self.monitored_markets)
                self.monitored_markets = updated_markets
                new_count = len(self.monitored_markets)
                
                logger.info(f"📊 Monitoring {new_count} markets (was {old_count})")
                
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
            historical_trades = self.data_api.get_historical_trades(market_id, lookback_hours=TimeConstants.HISTORICAL_DATA_HOURS)
            
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
            alert_stats = self.alert_manager.get_statistics()
            
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
        api_operational = self.data_api.test_connection()
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
                        recent_trades = self.data_api.get_recent_trades(market_ids, limit=500)
                        
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
    
    async def _analysis_loop(self):
        """Main analysis loop - runs detection algorithms"""
        while self.running:
            try:
                await self._run_market_analysis()
                await asyncio.sleep(self.analysis_interval)
            except Exception as e:
                logger.error(f"Error in analysis loop: {e}")
                await asyncio.sleep(30)
    
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
        volume_analysis = self.volume_detector.analyze_volume_pattern(trades, market_id, historical_baseline)
        
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
        
        # Multi-metric confidence evaluation
        detection_results = {
            AlertType.VOLUME_SPIKE: volume_analysis,
            AlertType.WHALE_ACTIVITY: whale_analysis,
            AlertType.UNUSUAL_PRICE_MOVEMENT: price_analysis,
            AlertType.COORDINATED_TRADING: coordination_analysis
        }
        
        # Evaluate alerts with multi-metric confidence
        alerts = await self._evaluate_multi_metric_alerts(
            market_id, market_data, detection_results
        )
        
        # Send alerts and count successful ones
        alerts_sent_successfully = 0
        for alert in alerts:
            if await self.alert_manager.send_alert(alert):
                alerts_sent_successfully += 1
        
        return alerts_sent_successfully
    
    async def _get_market_trades(self, market_id: str) -> List[Dict]:
        """Get combined trade data for a market"""
        trades = []
        
        # Prioritize Data API since WebSocket is having issues
        try:
            # Get recent trades first (increased limit for better analysis)
            recent_trades = self.data_api.get_recent_trades([market_id], limit=VolumeConstants.MAX_TRADES_PER_REQUEST)
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
    
    async def _create_alert(self, market_id: str, market_data: Dict, alert_type, 
                          analysis: Dict, severity: str) -> Dict:
        """Create an alert from detection results"""
        # Convert AlertType enum to string if needed
        alert_type_str = alert_type.value if hasattr(alert_type, 'value') else str(alert_type)
        
        return {
            'market_id': market_id,
            'market_question': market_data.get('question', 'Unknown Market'),
            'alert_type': alert_type_str,
            'severity': severity,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'analysis': analysis,
            'market_data': {
                'volume24hr': market_data.get('volume24hr', 0),
                'lastTradePrice': market_data.get('lastTradePrice', 0)
            },
            'recommended_action': self._get_recommended_action(alert_type_str, severity, analysis)
        }
    
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
"""
Market Monitor Orchestrator
Coordinates data sources and detection algorithms for insider trading detection
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
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
        self.alert_manager = AlertManager(self.config)
        
        # Market data storage
        self.monitored_markets = {}
        self.market_baselines = {}
        self.trade_history = {}
        
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
            asyncio.create_task(self._status_reporter(), name="status_reporter")
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
                            
                            # Collect token IDs for WebSocket subscription
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
            # Get historical data
            historical_trades = self.data_api.get_historical_trades(market_id, lookback_hours=24)
            
            if historical_trades:
                # Calculate baseline using volume detector
                baseline = self.volume_detector.calculate_baseline_metrics(historical_trades)
                self.market_baselines[market_id] = baseline
                
                logger.debug(f"Initialized baseline for {market_data.get('question', 'Unknown')[:30]}...")
            else:
                logger.debug(f"No historical data available for {market_id[:10]}...")
        
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
            padding = max(0, 56 - len(clean_content))
            return f"{Fore.BLUE}│{Style.RESET_ALL} {content}{' ' * padding}{Fore.BLUE}│{Style.RESET_ALL}"
        
        # Basic system status
        print(format_line(f"{Fore.CYAN}Markets:{Style.RESET_ALL} {Fore.GREEN}{len(self.monitored_markets)}{Style.RESET_ALL} monitored"))
        print(format_line(f"{Fore.CYAN}Analyses:{Style.RESET_ALL} {Fore.YELLOW}{self.analysis_count}{Style.RESET_ALL} completed"))
        print(format_line(f"{Fore.CYAN}Alerts:{Style.RESET_ALL} {Fore.RED if self.alerts_generated > 0 else Fore.GREEN}{self.alerts_generated}{Style.RESET_ALL} generated"))
        
        # WebSocket status
        if self.websocket_client:
            ws_stats = self.websocket_client.get_activity_stats()
            status_color = Fore.GREEN if ws_stats['is_connected'] else Fore.RED
            status_text = "Connected" if ws_stats['is_connected'] else "Disconnected"
            print(format_line(f"{Fore.CYAN}WebSocket:{Style.RESET_ALL} {status_color}{status_text}{Style.RESET_ALL}"))
            print(format_line(f"  {Fore.WHITE}Activity:{Style.RESET_ALL} {ws_stats['messages_received']} msgs, {ws_stats['trades_processed']} trades"))
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
                logger.info(f"📈 Trade: {market_name}... ${trade_data.get('size', 0):.2f} @ {trade_data.get('price', 0):.3f}")
            else:
                logger.debug(f"📈 Real-time trade: {market_id[:10]}... ${trade_data.get('size', 0):.2f}")
            
        except Exception as e:
            logger.error(f"Error handling real-time trade: {e}")
    
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
                alerts = await self._analyze_single_market(market_id, market_data)
                if alerts:
                    alerts_this_round += len(alerts)
                    markets_with_data += 1
                elif self.debug_config.get('verbose_analysis', False):
                    question = market_data.get('question', 'Unknown')[:40]
                    logger.debug(f"   ✅ {question}... - no anomalies detected")
                    
            except Exception as e:
                logger.error(f"Error analyzing market {market_id}: {e}")
        
        # Summary log for this analysis round
        if self.debug_mode or self.show_normal_activity or alerts_this_round > 0:
            alert_color = Fore.RED if alerts_this_round > 0 else Fore.GREEN
            status_emoji = "🚨" if alerts_this_round > 0 else "✅"
            print(f"{Fore.CYAN}{status_emoji} {Style.BRIGHT}Analysis #{self.analysis_count} Complete{Style.RESET_ALL}")
            print(f"   {alert_color}{alerts_this_round}{Style.RESET_ALL} alerts from {Fore.BLUE}{markets_with_data}{Style.RESET_ALL} markets with data")
            
        if alerts_this_round > 0:
            self.alerts_generated += alerts_this_round
    
    async def _analyze_single_market(self, market_id: str, market_data: Dict):
        """Analyze a single market for unusual activity"""
        # Get combined trade data (historical + real-time)
        trades = await self._get_market_trades(market_id)
        
        if not trades:
            return []
        
        # Run all detection algorithms
        alerts = []
        
        # Volume detection
        volume_analysis = self.volume_detector.analyze_volume_pattern(trades)
        if volume_analysis['anomaly']:
            alert = await self._create_alert(
                market_id, market_data, 'VOLUME_SPIKE', 
                volume_analysis, 'HIGH' if volume_analysis['max_anomaly_score'] > 5 else 'MEDIUM'
            )
            alerts.append(alert)
        
        # Whale detection
        whale_analysis = self.whale_detector.detect_whale_activity(trades)
        if whale_analysis['anomaly']:
            alert = await self._create_alert(
                market_id, market_data, 'WHALE_ACTIVITY', 
                whale_analysis, 'HIGH' if whale_analysis['total_whale_volume'] > 50000 else 'MEDIUM'
            )
            alerts.append(alert)
        
        # Price movement detection
        price_analysis = self.price_detector.detect_price_movement(trades)
        if price_analysis['anomaly']:
            severity = 'CRITICAL' if any(price_analysis['triggers'].values()) else 'MEDIUM'
            alert = await self._create_alert(
                market_id, market_data, 'UNUSUAL_PRICE_MOVEMENT', 
                price_analysis, severity
            )
            alerts.append(alert)
        
        # Coordination detection
        coordination_analysis = self.coordination_detector.detect_coordinated_buying(trades)
        if coordination_analysis['anomaly']:
            severity = 'CRITICAL' if coordination_analysis['coordination_score'] > 0.8 else 'HIGH'
            alert = await self._create_alert(
                market_id, market_data, 'COORDINATED_TRADING', 
                coordination_analysis, severity
            )
            alerts.append(alert)
        
        # Send alerts
        for alert in alerts:
            await self.alert_manager.send_alert(alert)
        
        return alerts
    
    async def _get_market_trades(self, market_id: str) -> List[Dict]:
        """Get combined trade data for a market"""
        trades = []
        
        # Prioritize Data API since WebSocket is having issues
        try:
            # Get recent trades first
            recent_trades = self.data_api.get_recent_trades([market_id], limit=200)
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
        
        return sorted_trades[:200]  # Return most recent 200 trades
    
    async def _create_alert(self, market_id: str, market_data: Dict, alert_type: str, 
                          analysis: Dict, severity: str) -> Dict:
        """Create an alert from detection results"""
        return {
            'market_id': market_id,
            'market_question': market_data.get('question', 'Unknown Market'),
            'alert_type': alert_type,
            'severity': severity,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'analysis': analysis,
            'market_data': {
                'volume24hr': market_data.get('volume24hr', 0),
                'lastTradePrice': market_data.get('lastTradePrice', 0)
            },
            'recommended_action': self._get_recommended_action(alert_type, severity, analysis)
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
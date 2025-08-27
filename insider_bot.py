#!/usr/bin/env python3
"""
Unusual Activity Detection Bot for Polymarket
Detects potential insider trading and information leakage
"""

import asyncio
import aiohttp
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from scipy import stats
import warnings
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.constants import POLYGON
from py_clob_client.clob_types import ApiCreds

# Load environment variables
load_dotenv()

warnings.filterwarnings('ignore')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class AnomalyAlert:
    market_id: str
    market_question: str
    alert_type: str
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    details: Dict
    timestamp: datetime
    price_before: float
    price_after: float
    volume_spike: float
    whale_wallets: List[str]
    recommended_action: str

class UnusualActivityDetector:
    def __init__(self, config: Dict = None):
        self.gamma_api = "https://gamma-api.polymarket.com"
        self.historical_data = {}
        self.alerts = []
        self.config = config or {}
        
        # API configuration - load from environment variables with config fallback
        self.clob_api_key = os.getenv('CLOB_API_KEY', '')
        self.clob_api_secret = os.getenv('CLOB_API_SECRET', '')
        self.clob_api_passphrase = os.getenv('CLOB_API_PASSPHRASE', '')
        self.simulation_mode = os.getenv('SIMULATION_MODE', '').lower() == 'true' if os.getenv('SIMULATION_MODE') else self.config.get('api', {}).get('simulation_mode', True)
        
        # Initialize CLOB client for real data mode
        self.clob_client = None
        self.private_key = os.getenv('POLYGON_PRIVATE_KEY', '')
        self.funder_address = os.getenv('FUNDER_ADDRESS', '')
        
        if not self.simulation_mode:
            try:
                if self.private_key and self.clob_api_key and self.clob_api_secret and self.clob_api_passphrase:
                    # Full Level 2 authentication with Email/Magic wallet setup
                    self.clob_client = ClobClient(
                        host="https://clob.polymarket.com",
                        key=self.private_key,
                        chain_id=POLYGON,
                        signature_type=1,  # Email/Magic wallet
                        funder=self.funder_address
                    )
                    
                    # Set L2 API credentials
                    creds = ApiCreds(
                        api_key=self.clob_api_key,
                        api_secret=self.clob_api_secret,
                        api_passphrase=self.clob_api_passphrase
                    )
                    self.clob_client.set_api_creds(creds)
                    logger.info("📊 Running in REAL DATA mode - Level 2 authenticated (Email/Magic wallet)")
                    
                elif self.private_key:
                    # Level 1 authentication with private key and funder
                    self.clob_client = ClobClient(
                        host="https://clob.polymarket.com",
                        key=self.private_key,
                        chain_id=POLYGON,
                        signature_type=1,
                        funder=self.funder_address
                    )
                    logger.info("📊 Running in REAL DATA mode - Level 1 authenticated (Email/Magic wallet)")
                    
                else:
                    # Level 0 - read-only access
                    self.clob_client = ClobClient(
                        host="https://clob.polymarket.com",
                        chain_id=POLYGON
                    )
                    logger.info("📊 Running in REAL DATA mode - Level 0 (read-only)")
                    
            except Exception as e:
                logger.error(f"Failed to initialize CLOB client: {e}")
                logger.info("Falling back to Level 0 (read-only) mode")
                try:
                    self.clob_client = ClobClient(
                        host="https://clob.polymarket.com",
                        chain_id=POLYGON
                    )
                except Exception as e2:
                    logger.error(f"Even Level 0 failed: {e2}")
                    self.clob_client = None
        else:
            logger.info("🧪 Running in SIMULATION mode - using simulated trade data")
        
        # Detection thresholds
        self.thresholds = {
            'volume_spike_multiplier': 3.0,  # 3x average volume
            'price_movement_std': 2.5,  # 2.5 standard deviations
            'whale_threshold_usd': 10000,  # Orders >$10k
            'rapid_accumulation_pct': 15,  # 15% price move in 1 hour
            'new_wallet_threshold': 5,  # Less than 5 previous trades
        }
    
    def _get_last_price(self, trades: List[Dict]) -> float:
        """Helper to get the last trade price from normalized data"""
        if not trades:
            return 0
        try:
            # Try to get price from last trade
            last_trade = trades[-1]
            return float(last_trade.get('price', last_trade.get('feeRate', last_trade.get('outcome_price', 0))))
        except (ValueError, TypeError, KeyError):
            return 0
    
        
    async def prepare_market_data(self, session: aiohttp.ClientSession, condition_id: str, market: Dict) -> Dict:
        """Prepare market data using stored market info (avoids re-fetching)"""
        try:
            # Ensure market has required fields
            market['condition_id'] = condition_id
            market['question'] = market.get('question', 'Unknown Market')
            
            # Get trade data based on mode
            if self.simulation_mode:
                # Simulation mode: use simulated data
                trades = self._generate_simulated_trades(market)
            else:
                # Real data mode: use CLOB client
                if not self.clob_client:
                    logger.error(f"Cannot fetch real data for {condition_id}: CLOB client not initialized")
                    return None
                
                trades = self._fetch_real_trades(condition_id, market)
                
                # If we get an empty list, we can still analyze the market (just won't have trade-based detection)
                # Only skip if we get None (API completely failed)
                if trades is None:
                    logger.warning(f"Failed to fetch real data for {condition_id}, skipping market")
                    return None
                elif len(trades) == 0:
                    market_name = market.get('question', 'Unknown Market')[:50]
                    logger.info(f"No recent trades found for '{market_name}...' (ID: {condition_id[:10]}...)")
                    logger.debug(f"Full condition_id: {condition_id}")
            
            return {
                'market': market,
                'trades': trades,
                'timestamp': datetime.now()
            }
        except Exception as e:
            logger.error(f"Error preparing market data for {condition_id}: {e}")
            return None

    async def fetch_market_data(self, session: aiohttp.ClientSession, condition_id: str) -> Dict:
        """Fetch current market data with hybrid real/simulated approach (fallback method)"""
        try:
            # Find the market with this conditionId from gamma API
            async with session.get(f"{self.gamma_api}/markets?conditionId={condition_id}") as resp:
                if resp.status != 200:
                    logger.warning(f"Failed to fetch market {condition_id}: HTTP {resp.status}")
                    return None
                
                markets = await resp.json()
                if not markets or not isinstance(markets, list) or len(markets) == 0:
                    logger.warning(f"No market found for conditionId {condition_id}")
                    return None
                
                market = markets[0]  # Take the first match
                return await self.prepare_market_data(session, condition_id, market)
        except Exception as e:
            logger.error(f"Error fetching market {condition_id}: {e}")
            return None
    
    def _generate_simulated_trades(self, market: Dict) -> List[Dict]:
        """Generate simulated trade data for testing detection algorithms"""
        import random
        from datetime import datetime, timedelta
        
        trades = []
        base_price = float(market.get('lastTradePrice', 0.5))
        volume_24hr = float(market.get('volume24hr', 1000))
        
        # Generate ~20 trades over last 24 hours
        for i in range(20):
            hours_ago = random.uniform(0, 24)
            timestamp = datetime.now() - timedelta(hours=hours_ago)
            
            # Add some price volatility
            price_variation = random.uniform(-0.05, 0.05)
            price = max(0.01, min(0.99, base_price + price_variation))
            
            # Random trade size based on market volume
            size = random.uniform(10, volume_24hr / 50)
            
            trades.append({
                'timestamp': timestamp.isoformat(),
                'price': price,
                'size': size,
                'side': random.choice(['BUY', 'SELL']),
                'maker': f"0x{random.randint(1000000000000000, 9999999999999999):016x}",
                'volume_usd': price * size
            })
        
        # Sort by timestamp (oldest first)
        trades.sort(key=lambda x: x['timestamp'])
        return trades
    
    def _fetch_real_trades(self, condition_id: str, market: Dict = None) -> List[Dict]:
        """Fetch real trade data using CLOB client"""
        try:
            # Get recent trades and filter by condition_id
            # py-clob-client get_trades() doesn't take a market parameter
            recent_trades = self.clob_client.get_trades()
            
            if recent_trades and isinstance(recent_trades, list):
                # Get token IDs from market for matching
                token_ids = []
                if market and 'clobTokenIds' in market:
                    token_ids = market['clobTokenIds']
                
                # Filter for our specific market/condition
                market_trades = []
                for trade in recent_trades:
                    # Check various possible field names for market identification
                    if (trade.get('market') == condition_id or 
                        trade.get('condition_id') == condition_id or
                        trade.get('conditionId') == condition_id or
                        trade.get('market_id') == condition_id or
                        trade.get('asset_id') in token_ids):
                        market_trades.append(trade)
                
                if market_trades:
                    logger.info(f"✅ Found {len(market_trades)} trades for {condition_id[:10]}...")
                else:
                    # Debug: Show what trades are available and why they don't match
                    logger.debug(f"No trades match condition_id {condition_id[:10]}... from {len(recent_trades)} total trades")
                    if recent_trades and logger.isEnabledFor(logging.DEBUG):
                        logger.debug("Available trade markets:")
                        for i, trade in enumerate(recent_trades[:3]):  # Show first 3
                            trade_market = trade.get('market', 'NO_MARKET')
                            trade_asset = trade.get('asset_id', 'NO_ASSET')
                            logger.debug(f"  Trade {i+1}: market={trade_market[:15]}..., asset_id={str(trade_asset)[:15]}...")
                        logger.debug(f"Looking for: condition_id={condition_id[:15]}...")
                        if token_ids:
                            logger.debug(f"Or token_ids: {[str(t)[:15] + '...' for t in token_ids[:2]]}")
                    
                return market_trades
            else:
                logger.warning(f"No trades returned from CLOB API")
                return []
                
        except Exception as e:
            logger.info(f"CLOB trades not available: {e}")
            return []
    
    def calculate_baseline_metrics(self, trades: List[Dict]) -> Dict:
        """Calculate baseline trading metrics for comparison"""
        if not trades:
            return {}
        
        # Normalize trade data to handle different field names
        normalized_trades = []
        for trade in trades:
            normalized = {
                'timestamp': trade.get('timestamp', trade.get('createdAt', trade.get('created_at', ''))),
                'price': float(trade.get('price', trade.get('feeRate', trade.get('outcome_price', 0)))),
                'size': float(trade.get('size', trade.get('amount', trade.get('shares', 1)))),
                'side': trade.get('side', trade.get('type', 'BUY')),
                'maker': trade.get('maker', trade.get('trader', trade.get('user', 'unknown')))
            }
            if normalized['timestamp'] and normalized['price'] > 0:
                normalized_trades.append(normalized)
        
        if not normalized_trades:
            return {}
        
        df = pd.DataFrame(normalized_trades)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['volume_usd'] = df['price'] * df['size']
        
        # Calculate hourly metrics
        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
        df.set_index('timestamp', inplace=True)
        hourly = df.resample('1H').agg({
            'volume_usd': 'sum',
            'price': ['mean', 'std'],
            'size': 'count'  # Number of trades
        })
        
        return {
            'avg_hourly_volume': hourly['volume_usd']['sum'].mean(),
            'std_hourly_volume': hourly['volume_usd']['sum'].std(),
            'avg_price': df['price'].mean(),
            'price_volatility': df['price'].std(),
            'avg_trades_per_hour': hourly['size']['count'].mean(),
            'recent_price': df['price'].iloc[-1] if len(df) > 0 else 0
        }
    
    def detect_volume_spike(self, current_volume: float, baseline: Dict) -> Tuple[bool, float]:
        """Detect unusual volume spikes"""
        if not baseline or 'avg_hourly_volume' not in baseline:
            return False, 0
        
        avg_volume = baseline['avg_hourly_volume']
        std_volume = baseline['std_hourly_volume']
        
        if avg_volume == 0:
            return False, 0
        
        # Calculate z-score
        z_score = (current_volume - avg_volume) / (std_volume + 1e-8)
        
        # Check if volume spike exceeds threshold
        spike_multiplier = current_volume / (avg_volume + 1e-8)
        
        is_anomaly = (
            spike_multiplier > self.thresholds['volume_spike_multiplier'] or
            z_score > 3
        )
        
        return is_anomaly, spike_multiplier
    
    def detect_price_movement(self, trades: List[Dict], window_minutes: int = 60) -> Dict:
        """Detect unusual price movements"""
        if not trades or len(trades) < 2:
            return {'anomaly': False}
        
        # Normalize trade data
        normalized_trades = []
        for trade in trades:
            try:
                normalized = {
                    'timestamp': trade.get('timestamp', trade.get('createdAt', trade.get('created_at', ''))),
                    'price': float(trade.get('price', trade.get('feeRate', trade.get('outcome_price', 0))))
                }
                if normalized['timestamp'] and normalized['price'] > 0:
                    normalized_trades.append(normalized)
            except (ValueError, TypeError):
                continue
        
        if len(normalized_trades) < 2:
            return {'anomaly': False}
        
        df = pd.DataFrame(normalized_trades)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['price'] = df['price'].astype(float)
        
        # Get trades from last window
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
        # Ensure timestamps are timezone aware for comparison
        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
        recent = df[df['timestamp'] > cutoff]
        
        if len(recent) < 2:
            return {'anomaly': False}
        
        # Calculate price movement
        price_start = recent['price'].iloc[0]
        price_end = recent['price'].iloc[-1]
        price_change_pct = ((price_end - price_start) / price_start) * 100
        
        # Check for rapid movement
        is_rapid = abs(price_change_pct) > self.thresholds['rapid_accumulation_pct']
        
        # Calculate if movement is unusual based on historical volatility
        historical_std = df['price'].std()
        price_change_std = abs(price_end - price_start) / (historical_std + 1e-8)
        is_unusual = price_change_std > self.thresholds['price_movement_std']
        
        return {
            'anomaly': is_rapid or is_unusual,
            'price_change_pct': price_change_pct,
            'price_change_std': price_change_std,
            'price_start': price_start,
            'price_end': price_end,
            'is_rapid': is_rapid,
            'is_unusual': is_unusual
        }
    
    def detect_whale_activity(self, trades: List[Dict]) -> Dict:
        """Detect large orders from single or coordinated wallets"""
        if not trades:
            return {'anomaly': False}
        
        # Normalize trade data
        normalized_trades = []
        for trade in trades:
            try:
                normalized = {
                    'price': float(trade.get('price', trade.get('feeRate', trade.get('outcome_price', 0)))),
                    'size': float(trade.get('size', trade.get('amount', trade.get('shares', 1)))),
                    'side': trade.get('side', trade.get('type', 'BUY')),
                    'maker': trade.get('maker', trade.get('trader', trade.get('user', 'unknown')))
                }
                if normalized['price'] > 0:
                    normalized_trades.append(normalized)
            except (ValueError, TypeError):
                continue
        
        if not normalized_trades:
            return {'anomaly': False}
        
        df = pd.DataFrame(normalized_trades)
        df['volume_usd'] = df['price'] * df['size']
        
        # Find whale trades
        whale_trades = df[df['volume_usd'] > self.thresholds['whale_threshold_usd']]
        
        if len(whale_trades) == 0:
            return {'anomaly': False}
        
        # Group by wallet address
        wallet_volumes = whale_trades.groupby('maker')['volume_usd'].agg(['sum', 'count'])
        top_whales = wallet_volumes.nlargest(5, 'sum')
        
        # Check if whales are accumulating in same direction
        whale_sides = whale_trades.groupby('side')['volume_usd'].sum()
        
        imbalance = 0
        if 'BUY' in whale_sides and 'SELL' in whale_sides:
            total = whale_sides['BUY'] + whale_sides['SELL']
            imbalance = abs(whale_sides['BUY'] - whale_sides['SELL']) / total
        elif 'BUY' in whale_sides:
            imbalance = 1.0  # All buying
        elif 'SELL' in whale_sides:
            imbalance = 1.0  # All selling
        
        return {
            'anomaly': imbalance > 0.7,  # 70% imbalance
            'whale_count': len(top_whales),
            'total_whale_volume': whale_trades['volume_usd'].sum(),
            'top_whales': top_whales.to_dict() if len(top_whales) > 0 else {},
            'direction_imbalance': imbalance,
            'dominant_side': 'BUY' if whale_sides.get('BUY', 0) > whale_sides.get('SELL', 0) else 'SELL'
        }
    
    def detect_coordinated_buying(self, trades: List[Dict]) -> Dict:
        """Detect multiple wallets buying in coordination"""
        if not trades or len(trades) < 10:
            return {'anomaly': False}
        
        # Normalize trade data
        normalized_trades = []
        for trade in trades:
            try:
                normalized = {
                    'timestamp': trade.get('timestamp', trade.get('createdAt', trade.get('created_at', ''))),
                    'size': float(trade.get('size', trade.get('amount', trade.get('shares', 1)))),
                    'side': trade.get('side', trade.get('type', 'BUY')),
                    'maker': trade.get('maker', trade.get('trader', trade.get('user', 'unknown')))
                }
                if normalized['timestamp']:
                    normalized_trades.append(normalized)
            except (ValueError, TypeError):
                continue
        
        if len(normalized_trades) < 10:
            return {'anomaly': False}
        
        df = pd.DataFrame(normalized_trades)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Look for bursts of similar-sized orders
        recent_window = datetime.now(timezone.utc) - timedelta(minutes=30)
        # Ensure timestamps are timezone aware for comparison
        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
        recent = df[df['timestamp'] > recent_window]
        
        if len(recent) < 5:
            return {'anomaly': False}
        
        # Group by wallet and side
        wallet_activity = recent.groupby(['maker', 'side']).agg({
            'size': ['sum', 'count'],
            'timestamp': 'min'
        })
        
        # Find new wallets (would need historical data in production)
        unique_wallets = recent['maker'].nunique()
        
        # Check for suspicious patterns
        buy_wallets = recent[recent['side'] == 'BUY']['maker'].nunique()
        sell_wallets = recent[recent['side'] == 'SELL']['maker'].nunique()
        
        buy_ratio = buy_wallets / (buy_wallets + sell_wallets + 1e-8)
        
        # Multiple wallets all buying = suspicious
        is_coordinated = (
            buy_ratio > 0.8 and  # 80% of wallets are buying
            unique_wallets > 5 and  # Multiple wallets involved
            len(recent) > 20  # Significant activity
        )
        
        return {
            'anomaly': is_coordinated,
            'unique_wallets': unique_wallets,
            'buy_wallets': buy_wallets,
            'sell_wallets': sell_wallets,
            'buy_ratio': buy_ratio,
            'trade_count': len(recent)
        }
    
    def analyze_market(self, market_data: Dict) -> List[AnomalyAlert]:
        """Run all detection algorithms on a market"""
        alerts = []
        
        if not market_data or 'trades' not in market_data:
            return alerts
        
        trades = market_data['trades']
        market = market_data['market']
        
        # Calculate baseline metrics
        baseline = self.calculate_baseline_metrics(trades)
        
        # Get current hour volume
        recent_trades = []
        for t in trades:
            try:
                # Handle different timestamp formats
                ts = t.get('timestamp', t.get('createdAt', t.get('created_at', '')))
                if ts:
                    # Parse timestamp handling different formats
                    if 'Z' in ts:
                        ts = ts.replace('Z', '+00:00')
                    
                    # Parse datetime with timezone awareness
                    if 'T' in ts:
                        trade_time = datetime.fromisoformat(ts)
                    else:
                        trade_time = datetime.strptime(ts, '%Y-%m-%d %H:%M:%S')
                        # Assume UTC if no timezone
                        trade_time = trade_time.replace(tzinfo=timezone.utc)
                    
                    # Make now timezone aware
                    now_utc = datetime.now(timezone.utc)
                    
                    # Check if within last hour
                    if trade_time > now_utc - timedelta(hours=1):
                        recent_trades.append(t)
            except (ValueError, TypeError, AttributeError):
                continue
        
        # Calculate volume with normalized fields
        current_volume = 0
        for t in recent_trades:
            try:
                price = float(t.get('price', t.get('feeRate', t.get('outcome_price', 0))))
                size = float(t.get('size', t.get('amount', t.get('shares', 1))))
                current_volume += price * size
            except (ValueError, TypeError):
                continue
        
        # Run detections
        volume_anomaly, volume_spike = self.detect_volume_spike(current_volume, baseline)
        price_movement = self.detect_price_movement(trades)
        whale_activity = self.detect_whale_activity(recent_trades)
        coordinated = self.detect_coordinated_buying(recent_trades)
        
        # Create alerts based on findings
        severity_score = 0
        alert_details = {}
        
        if volume_anomaly:
            severity_score += 2
            alert_details['volume_spike'] = f"{volume_spike:.1f}x normal"
        
        if price_movement['anomaly']:
            severity_score += 3
            alert_details['price_change'] = f"{price_movement['price_change_pct']:.1f}%"
            
        if whale_activity['anomaly']:
            severity_score += 3
            alert_details['whale_volume'] = f"${whale_activity['total_whale_volume']:.0f}"
            alert_details['whale_direction'] = whale_activity['dominant_side']
            
        if coordinated['anomaly']:
            severity_score += 4
            alert_details['coordinated_wallets'] = coordinated['unique_wallets']
        
        # Determine severity level
        if severity_score >= 8:
            severity = "CRITICAL"
            action = "IMMEDIATE: Follow the whale trades - potential insider activity!"
        elif severity_score >= 5:
            severity = "HIGH"
            action = "Consider taking position in same direction as unusual activity"
        elif severity_score >= 3:
            severity = "MEDIUM"
            action = "Monitor closely - could be early signal"
        elif severity_score > 0:
            severity = "LOW"
            action = "Note unusual activity but wait for confirmation"
        else:
            return []  # No alert
        
        # Create alert
        alert = AnomalyAlert(
            market_id=market['condition_id'],
            market_question=market['question'],
            alert_type="UNUSUAL_ACTIVITY",
            severity=severity,
            details=alert_details,
            timestamp=datetime.now(),
            price_before=baseline.get('recent_price', 0),
            price_after=self._get_last_price(trades),
            volume_spike=volume_spike,
            whale_wallets=list(whale_activity.get('top_whales', {}).keys()) if whale_activity['anomaly'] else [],
            recommended_action=action
        )
        
        return [alert]
    
    async def monitor_markets(self, market_ids: List[str] = None):
        """Monitor markets for unusual activity"""
        async with aiohttp.ClientSession() as session:
            while True:
                try:
                    # Get list of markets to monitor
                    if not market_ids:
                        # Get top markets by volume - using gamma API which has market data
                        volume_threshold = self.config.get('monitoring', {}).get('volume_threshold', 1000)
                        max_markets = self.config.get('monitoring', {}).get('max_markets', 50)
                        sort_by_volume = self.config.get('monitoring', {}).get('sort_by_volume', True)
                        
                        logger.info(f"🔍 Discovering top {max_markets} markets (min vol: ${volume_threshold}, sorted: {sort_by_volume})")
                        async with session.get(f"{self.gamma_api}/markets?active=true&closed=false&limit={max_markets}") as resp:
                            if resp.status != 200:
                                logger.error(f"Failed to fetch markets: HTTP {resp.status}")
                                await asyncio.sleep(60)
                                continue
                            
                            response_text = await resp.text()
                            try:
                                markets = json.loads(response_text)
                            except json.JSONDecodeError:
                                logger.error(f"Invalid JSON response: {response_text[:200]}")
                                await asyncio.sleep(60)
                                continue
                            
                            # Handle different response formats
                            if isinstance(markets, dict):
                                # If the response is wrapped in an object
                                if 'data' in markets:
                                    markets = markets['data']
                                elif 'markets' in markets:
                                    markets = markets['markets']
                                else:
                                    logger.error(f"Unexpected response structure: {list(markets.keys())[:5]}")
                                    await asyncio.sleep(60)
                                    continue
                            
                            if not isinstance(markets, list):
                                logger.error(f"Expected list of markets, got {type(markets)}")
                                await asyncio.sleep(60)
                                continue
                            
                            # Sort markets by volume (highest first) if configured
                            if sort_by_volume:
                                try:
                                    markets.sort(key=lambda m: float(m.get('volume24hr', 0)), reverse=True)
                                    logger.debug(f"Sorted {len(markets)} markets by 24hr volume")
                                except (ValueError, TypeError):
                                    logger.warning("Could not sort markets by volume, proceeding without sorting")
                            
                            # Filter markets with sufficient volume and store complete market data
                            markets_data = {}  # condition_id -> market_data
                            market_ids = []
                            volume_threshold = self.config.get('monitoring', {}).get('volume_threshold', 1000)
                            max_markets_to_process = self.config.get('monitoring', {}).get('max_markets', 50)
                            
                            processed_count = 0
                            for m in markets:
                                if processed_count >= max_markets_to_process:
                                    break
                                    
                                try:
                                    # Get condition ID (this is the correct field)
                                    condition_id = m.get('conditionId', '')
                                    volume = float(m.get('volume24hr', 0))
                                    question = m.get('question', 'Unknown')
                                    
                                    # Skip if no condition ID or below volume threshold
                                    if condition_id and volume >= volume_threshold:
                                        market_ids.append(condition_id)
                                        markets_data[condition_id] = m  # Store complete market data
                                        logger.info(f"Added market: {question[:50]}... (Vol: ${volume:.0f})")
                                        processed_count += 1
                                except (KeyError, ValueError, TypeError) as e:
                                    logger.warning(f"Error processing market: {e}")
                                    continue
                    
                    if not market_ids:
                        logger.info(f"No active markets found above ${volume_threshold} volume threshold. Skipping this round.")
                        await asyncio.sleep(60)  # Wait and try again later
                        continue
                    
                    logger.info(f"📊 Monitoring {len(market_ids)} volume-filtered markets for unusual activity...")
                    
                    for market_id in market_ids:
                        # Use stored market data instead of re-fetching
                        if market_id in markets_data:
                            market_data = await self.prepare_market_data(session, market_id, markets_data[market_id])
                        else:
                            # Fallback to fetch if not in stored data
                            market_data = await self.fetch_market_data(session, market_id)
                        
                        if market_data:
                            alerts = self.analyze_market(market_data)
                            
                            for alert in alerts:
                                if alert.severity in ["CRITICAL", "HIGH"]:
                                    logger.warning(f"🚨 {alert.severity} ALERT: {alert.market_question[:50]}...")
                                    logger.warning(f"   Details: {alert.details}")
                                    logger.warning(f"   Action: {alert.recommended_action}")
                                    
                                    # Send notifications
                                    await self.send_alert(alert)
                                
                                self.alerts.append(alert)
                        
                        await asyncio.sleep(2)  # Rate limiting
                    
                    # Wait before next scan
                    await asyncio.sleep(60)  # Check every minute
                    
                except Exception as e:
                    logger.error(f"Error in monitoring loop: {e}")
                    await asyncio.sleep(30)
    
    async def send_alert(self, alert: AnomalyAlert):
        """Send alert notifications"""
        # Discord webhook
        webhook_url = os.getenv('DISCORD_WEBHOOK', '')
        if webhook_url and alert.severity in ["CRITICAL", "HIGH"]:
            
            color = 0xFF0000 if alert.severity == "CRITICAL" else 0xFFA500
            
            embed = {
                "title": f"🚨 {alert.severity}: Unusual Activity Detected",
                "description": alert.market_question,
                "color": color,
                "fields": [
                    {"name": "Price Movement", "value": f"{alert.price_before:.2f} → {alert.price_after:.2f}", "inline": True},
                    {"name": "Volume Spike", "value": f"{alert.volume_spike:.1f}x normal", "inline": True},
                    {"name": "Details", "value": str(alert.details), "inline": False},
                    {"name": "Recommended Action", "value": alert.recommended_action, "inline": False}
                ],
                "timestamp": alert.timestamp.isoformat()
            }
            
            try:
                async with aiohttp.ClientSession() as session:
                    await session.post(webhook_url, json={"embeds": [embed]})
            except:
                pass
    
    def backtest_detection(self, historical_data: pd.DataFrame) -> Dict:
        """Backtest the detection on historical data to find patterns"""
        # This would analyze past "insider" events to tune parameters
        results = {
            'true_positives': 0,
            'false_positives': 0,
            'average_lead_time': 0,
            'best_indicators': []
        }
        
        # Implementation would check which patterns preceded major news
        # and optimize thresholds
        
        return results

async def main():
    """Main execution"""
    # Load configuration (if running standalone)
    try:
        config_path = Path("insider_config.json")
        if config_path.exists():
            with open(config_path) as f:
                config = json.load(f)
        else:
            config = {}
    except Exception:
        config = {}
    
    detector = UnusualActivityDetector(config)
    
    # Monitor specific markets or all top markets
    specific_markets = [
        # Add specific market IDs you want to monitor
        # "0x123...",  # Example: "Will Company X announce acquisition?"
    ]
    
    await detector.monitor_markets(specific_markets or None)

if __name__ == "__main__":
    logger.info("Starting Unusual Activity Detection Bot...")
    logger.info("Monitoring for potential insider trading patterns...")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")

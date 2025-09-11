"""
Polymarket Data API Client
Fetches historical and current trade data from public API
"""

import requests
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import time

logger = logging.getLogger(__name__)

class DataAPIClient:
    """Client for Polymarket Data API - provides historical trade data"""
    
    def __init__(self, base_url: str = "https://data-api.polymarket.com"):
        self.base_url = base_url.rstrip('/')
        self.trades_endpoint = f"{self.base_url}/trades"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'PolymarketInsiderBot/1.0',
            'Accept': 'application/json'
        })
        
    def get_market_trades(self, market_id: str, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Get trades for a specific market"""
        params = {
            'market': market_id,
            'limit': min(limit, 500),  # API max is 500
            'offset': offset
        }
        
        try:
            response = self.session.get(self.trades_endpoint, params=params, timeout=10)
            response.raise_for_status()
            
            trades = response.json()
            logger.debug(f"Fetched {len(trades)} trades for market {market_id[:10]}...")
            return trades
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching trades for market {market_id[:10]}...: {e}")
            return []
    
    def get_recent_trades(self, market_ids: List[str], limit: int = 100) -> List[Dict]:
        """Get recent trades across multiple markets"""
        params = {
            'limit': min(limit, 500)
        }
        
        # Only add market filter if market_ids provided
        if market_ids:
            market_param = ",".join(market_ids)
            params['market'] = market_param
        
        try:
            response = self.session.get(self.trades_endpoint, params=params, timeout=10)
            response.raise_for_status()
            
            trades = response.json()
            market_info = f" across {len(market_ids)} markets" if market_ids else " (all markets)"
            logger.debug(f"Fetched {len(trades)} recent trades{market_info}")
            return trades
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching recent trades: {e}")
            return []
    
    def get_historical_trades(self, market_id: str, lookback_hours: int = 24) -> List[Dict]:
        """Get historical trades within a time window for baseline analysis"""
        all_trades = []
        offset = 0
        cutoff_time = datetime.now() - timedelta(hours=lookback_hours)
        
        while True:
            trades = self.get_market_trades(market_id, limit=500, offset=offset)
            
            if not trades:
                break
            
            # Filter by timestamp and add to results
            time_filtered = []
            for trade in trades:
                try:
                    # Handle different timestamp formats
                    timestamp = trade.get('timestamp')
                    if timestamp:
                        if isinstance(timestamp, (int, float)):
                            trade_time = datetime.fromtimestamp(timestamp)
                        else:
                            # ISO format
                            trade_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        
                        if trade_time > cutoff_time:
                            time_filtered.append(trade)
                        else:
                            # Reached cutoff, return what we have
                            all_trades.extend(time_filtered)
                            return all_trades
                except (ValueError, TypeError) as e:
                    logger.warning(f"Error parsing timestamp for trade: {e}")
                    continue
            
            all_trades.extend(time_filtered)
            
            # If we got fewer than requested, we've hit the end
            if len(trades) < 500:
                break
                
            offset += 500
            
            # Rate limiting
            time.sleep(0.1)
        
        logger.info(f"Fetched {len(all_trades)} historical trades for {market_id[:10]}... (last {lookback_hours}h)")
        return all_trades
    
    def get_all_recent_trades(self, limit: int = 100) -> List[Dict]:
        """Get recent trades across all markets (no market filter)"""
        params = {'limit': min(limit, 500)}
        
        try:
            response = self.session.get(self.trades_endpoint, params=params, timeout=10)
            response.raise_for_status()
            
            trades = response.json()
            logger.debug(f"Fetched {len(trades)} recent trades across all markets")
            return trades
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching all recent trades: {e}")
            return []
    
    def test_connection(self) -> bool:
        """Test API connectivity"""
        try:
            response = self.session.get(self.trades_endpoint, params={'limit': 1}, timeout=5)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Data API connection test failed: {e}")
            return False
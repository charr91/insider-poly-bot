"""
Mock data generators for testing insider trading detection algorithms.
"""
import random
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np
from dataclasses import dataclass


@dataclass
class TradePattern:
    """Configuration for generating specific trade patterns."""
    volume_multiplier: float = 1.0
    price_trend: str = "random"  # "up", "down", "random", "pump", "dump"
    coordination_window: int = 300  # seconds
    whale_probability: float = 0.1  # probability of whale trades
    manipulation_probability: float = 0.05  # probability of manipulation patterns


class MockDataGenerator:
    """Generates realistic mock data for testing detection algorithms."""
    
    def __init__(self, seed: int = 42):
        """Initialize generator with random seed for reproducible tests."""
        random.seed(seed)
        np.random.seed(seed)
        self.base_timestamp = int(time.time()) - 86400  # 24 hours ago
        
    def generate_wallet_address(self, prefix: str = "0x") -> str:
        """Generate a mock wallet address."""
        return prefix + ''.join(random.choices('0123456789abcdef', k=40))
    
    def generate_market_id(self) -> str:
        """Generate a mock market ID."""
        return f"market_{random.randint(100000, 999999)}"
    
    def generate_trade_id(self) -> str:
        """Generate a mock trade ID."""
        return f"trade_{random.randint(1000000, 9999999)}"
    
    def generate_single_trade(
        self,
        market_id: Optional[str] = None,
        timestamp: Optional[int] = None,
        size_usd: Optional[float] = None,
        price: Optional[float] = None,
        side: Optional[str] = None,
        maker: Optional[str] = None,
        taker: Optional[str] = None,
        is_whale: bool = False
    ) -> Dict[str, Any]:
        """Generate a single trade with optional specific parameters."""
        if market_id is None:
            market_id = self.generate_market_id()
        if timestamp is None:
            timestamp = self.base_timestamp + random.randint(0, 86400)
        if size_usd is None:
            if is_whale:
                size_usd = random.uniform(10000, 100000)  # Whale size
            else:
                size_usd = random.uniform(10, 5000)  # Normal size
        if price is None:
            price = random.uniform(0.01, 0.99)
        if side is None:
            side = random.choice(["BUY", "SELL"])
        if maker is None:
            maker = self.generate_wallet_address()
        if taker is None:
            taker = self.generate_wallet_address()
            
        return {
            "market_id": market_id,
            "trade_id": self.generate_trade_id(),
            "maker": maker,
            "taker": taker,
            "size": str(size_usd),
            "price": str(price),
            "side": side,
            "timestamp": timestamp,
            "outcome": random.choice(["YES", "NO"]),
            "asset_id": f"asset_{random.randint(1000, 9999)}"
        }
    
    def generate_normal_trades(
        self,
        count: int = 100,
        market_id: Optional[str] = None,
        time_span_hours: int = 24
    ) -> List[Dict[str, Any]]:
        """Generate normal trading activity."""
        trades = []
        if market_id is None:
            market_id = self.generate_market_id()
            
        start_time = self.base_timestamp
        end_time = start_time + (time_span_hours * 3600)
        
        for _ in range(count):
            timestamp = random.randint(start_time, end_time)
            trade = self.generate_single_trade(
                market_id=market_id,
                timestamp=timestamp,
                size_usd=random.uniform(10, 1000)
            )
            trades.append(trade)
            
        return sorted(trades, key=lambda x: x["timestamp"])
    
    def generate_volume_spike_pattern(
        self,
        base_trades: int = 50,
        spike_multiplier: float = 10.0,
        spike_duration_minutes: int = 15,
        market_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Generate trades with a volume spike pattern."""
        if market_id is None:
            market_id = self.generate_market_id()
            
        trades = []
        
        # Generate normal trades before spike
        normal_trades = self.generate_normal_trades(
            count=base_trades,
            market_id=market_id,
            time_span_hours=2
        )
        trades.extend(normal_trades)
        
        # Generate spike period
        spike_start = max(trade["timestamp"] for trade in normal_trades) + 300
        spike_end = spike_start + (spike_duration_minutes * 60)
        spike_trade_count = int(base_trades * spike_multiplier)
        
        for _ in range(spike_trade_count):
            timestamp = random.randint(spike_start, spike_end)
            trade = self.generate_single_trade(
                market_id=market_id,
                timestamp=timestamp,
                size_usd=random.uniform(100, 2000)
            )
            trades.append(trade)
            
        # Generate normal trades after spike
        post_spike_trades = self.generate_normal_trades(
            count=base_trades // 2,
            market_id=market_id,
            time_span_hours=1
        )
        for trade in post_spike_trades:
            trade["timestamp"] = spike_end + random.randint(300, 3600)
        trades.extend(post_spike_trades)
        
        return sorted(trades, key=lambda x: x["timestamp"])
    
    def generate_whale_accumulation_pattern(
        self,
        whale_wallet: Optional[str] = None,
        accumulation_count: int = 10,
        time_span_hours: int = 6,
        market_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Generate whale accumulation pattern."""
        if whale_wallet is None:
            whale_wallet = self.generate_wallet_address()
        if market_id is None:
            market_id = self.generate_market_id()
            
        trades = []
        start_time = self.base_timestamp
        end_time = start_time + (time_span_hours * 3600)
        
        # Generate normal background trades
        background_trades = self.generate_normal_trades(
            count=50,
            market_id=market_id,
            time_span_hours=time_span_hours
        )
        trades.extend(background_trades)
        
        # Generate whale accumulation trades
        for i in range(accumulation_count):
            timestamp = random.randint(start_time, end_time)
            size_usd = random.uniform(15000, 50000)  # Large whale sizes
            
            # Whale can be either maker or taker
            if random.choice([True, False]):
                maker = whale_wallet
                taker = self.generate_wallet_address()
            else:
                maker = self.generate_wallet_address()
                taker = whale_wallet
                
            trade = self.generate_single_trade(
                market_id=market_id,
                timestamp=timestamp,
                size_usd=size_usd,
                maker=maker,
                taker=taker,
                side="BUY",  # Whale accumulating
                is_whale=True
            )
            trades.append(trade)
            
        return sorted(trades, key=lambda x: x["timestamp"])
    
    def generate_coordinated_trading_pattern(
        self,
        wallet_count: int = 5,
        coordination_window: int = 300,
        market_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Generate coordinated trading pattern among multiple wallets."""
        if market_id is None:
            market_id = self.generate_market_id()
            
        # Generate coordinated wallet addresses
        coordinated_wallets = [
            self.generate_wallet_address() for _ in range(wallet_count)
        ]
        
        trades = []
        
        # Generate normal background trades
        background_trades = self.generate_normal_trades(
            count=30,
            market_id=market_id,
            time_span_hours=4
        )
        trades.extend(background_trades)
        
        # Generate coordinated trading window
        coordination_start = max(trade["timestamp"] for trade in background_trades) + 600
        
        for wallet in coordinated_wallets:
            # Each wallet makes 2-4 trades within the coordination window
            trade_count = random.randint(2, 4)
            for _ in range(trade_count):
                timestamp = coordination_start + random.randint(0, coordination_window)
                size_usd = random.uniform(5000, 15000)
                
                trade = self.generate_single_trade(
                    market_id=market_id,
                    timestamp=timestamp,
                    size_usd=size_usd,
                    maker=wallet,
                    side="BUY"  # All coordinated on same side
                )
                trades.append(trade)
                
        return sorted(trades, key=lambda x: x["timestamp"])
    
    def generate_pump_and_dump_pattern(
        self,
        market_id: Optional[str] = None,
        pump_duration_minutes: int = 30,
        dump_duration_minutes: int = 15
    ) -> List[Dict[str, Any]]:
        """Generate pump and dump trading pattern."""
        if market_id is None:
            market_id = self.generate_market_id()
            
        trades = []
        
        # Pre-pump normal trading
        pre_pump_trades = self.generate_normal_trades(
            count=20,
            market_id=market_id,
            time_span_hours=2
        )
        trades.extend(pre_pump_trades)
        
        pump_start = max(trade["timestamp"] for trade in pre_pump_trades) + 300
        pump_end = pump_start + (pump_duration_minutes * 60)
        dump_end = pump_end + (dump_duration_minutes * 60)
        
        # Pump phase - increasing prices and volume
        pump_trade_count = pump_duration_minutes * 2  # 2 trades per minute
        base_price = 0.3
        
        for i in range(pump_trade_count):
            timestamp = pump_start + (i * 30)  # Every 30 seconds
            price_increase = (i / pump_trade_count) * 0.4  # Price rises to 0.7
            price = base_price + price_increase + random.uniform(-0.02, 0.02)
            
            trade = self.generate_single_trade(
                market_id=market_id,
                timestamp=timestamp,
                size_usd=random.uniform(1000, 5000),
                price=price,
                side="BUY"
            )
            trades.append(trade)
            
        # Dump phase - rapid price decline
        dump_trade_count = dump_duration_minutes * 3  # 3 trades per minute
        peak_price = 0.7
        
        for i in range(dump_trade_count):
            timestamp = pump_end + (i * 20)  # Every 20 seconds
            price_decrease = (i / dump_trade_count) * 0.5  # Price drops to 0.2
            price = peak_price - price_decrease + random.uniform(-0.01, 0.01)
            price = max(0.01, price)  # Don't go below 0.01
            
            trade = self.generate_single_trade(
                market_id=market_id,
                timestamp=timestamp,
                size_usd=random.uniform(2000, 8000),
                price=price,
                side="SELL"
            )
            trades.append(trade)
            
        return sorted(trades, key=lambda x: x["timestamp"])
    
    def generate_websocket_messages(
        self,
        trade_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Convert trade data to WebSocket message format."""
        messages = []
        
        for trade in trade_data:
            message = {
                "type": "trade",
                "channel": "trades",
                "market": trade["market_id"],
                "data": {
                    "id": trade["trade_id"],
                    "market": trade["market_id"],
                    "maker": trade["maker"],
                    "taker": trade["taker"],
                    "size": trade["size"],
                    "price": trade["price"],
                    "side": trade["side"],
                    "timestamp": trade["timestamp"],
                    "outcome": trade["outcome"]
                }
            }
            messages.append(message)
            
        return messages
    
    def generate_edge_case_data(self) -> List[Dict[str, Any]]:
        """Generate edge cases for testing robustness."""
        edge_cases = []
        market_id = self.generate_market_id()
        
        # Zero volume trade
        edge_cases.append(self.generate_single_trade(
            market_id=market_id,
            size_usd=0.0,
            price=0.5
        ))
        
        # Very high price (near 1.0)
        edge_cases.append(self.generate_single_trade(
            market_id=market_id,
            price=0.999,
            size_usd=1000
        ))
        
        # Very low price (near 0.0)
        edge_cases.append(self.generate_single_trade(
            market_id=market_id,
            price=0.001,
            size_usd=1000
        ))
        
        # Extremely large trade
        edge_cases.append(self.generate_single_trade(
            market_id=market_id,
            size_usd=1000000,
            is_whale=True
        ))
        
        # Rapid succession trades (same timestamp)
        timestamp = self.base_timestamp + 1000
        for _ in range(5):
            edge_cases.append(self.generate_single_trade(
                market_id=market_id,
                timestamp=timestamp,
                size_usd=random.uniform(100, 1000)
            ))
            
        return edge_cases
    
    def generate_api_response(
        self,
        trades: List[Dict[str, Any]],
        next_cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate mock API response format."""
        return {
            "data": trades,
            "next_cursor": next_cursor,
            "status": "success",
            "timestamp": int(time.time())
        }
    
    def trades_to_dataframe(self, trades: List[Dict[str, Any]]) -> pd.DataFrame:
        """Convert trade list to pandas DataFrame for analysis."""
        df = pd.DataFrame(trades)
        if not df.empty:
            df["size"] = pd.to_numeric(df["size"])
            df["price"] = pd.to_numeric(df["price"])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
            df["size_usd"] = df["size"] * df["price"]
        return df


class FixtureLoader:
    """Loads and manages test fixtures."""
    
    @staticmethod
    def load_known_anomalies() -> Dict[str, List[Dict[str, Any]]]:
        """Load known anomaly patterns for testing."""
        generator = MockDataGenerator()
        
        return {
            "volume_spike": generator.generate_volume_spike_pattern(
                spike_multiplier=8.0
            ),
            "whale_accumulation": generator.generate_whale_accumulation_pattern(
                accumulation_count=15
            ),
            "coordinated_trading": generator.generate_coordinated_trading_pattern(
                wallet_count=7
            ),
            "pump_and_dump": generator.generate_pump_and_dump_pattern(),
            "edge_cases": generator.generate_edge_case_data()
        }
    
    @staticmethod
    def load_baseline_data() -> List[Dict[str, Any]]:
        """Load baseline normal trading data."""
        generator = MockDataGenerator()
        return generator.generate_normal_trades(count=200, time_span_hours=48)
    
    @staticmethod
    def load_performance_test_data(size: str = "medium") -> List[Dict[str, Any]]:
        """Load data for performance testing."""
        generator = MockDataGenerator()
        
        sizes = {
            "small": 1000,
            "medium": 10000,
            "large": 100000,
            "xlarge": 1000000
        }
        
        trade_count = sizes.get(size, 10000)
        return generator.generate_normal_trades(
            count=trade_count,
            time_span_hours=168  # 1 week
        )
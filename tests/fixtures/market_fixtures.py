"""
Market-specific test fixtures and scenarios.
"""
from typing import Dict, List, Any
import json
import random
from datetime import datetime, timedelta


class MarketFixtures:
    """Pre-defined market scenarios for testing."""
    
    @staticmethod
    def presidential_election_market() -> Dict[str, Any]:
        """High-volume political prediction market scenario."""
        return {
            "market_id": "pres_election_2024",
            "title": "2024 Presidential Election Winner",
            "description": "Who will win the 2024 US Presidential Election?",
            "outcomes": ["Democrat", "Republican", "Other"],
            "liquidity_usd": 50000000,  # $50M liquidity
            "volume_24h": 5000000,     # $5M daily volume
            "active_traders": 25000,
            "whale_threshold": 100000,  # $100k for whale detection
            "volatility": "high",
            "trading_hours": "24/7",
            "expected_patterns": [
                "news_driven_spikes",
                "whale_accumulation",
                "coordination_around_events"
            ]
        }
    
    @staticmethod
    def sports_betting_market() -> Dict[str, Any]:
        """Sports betting market with time-sensitive trading."""
        return {
            "market_id": "superbowl_2024",
            "title": "Super Bowl 2024 Winner",
            "description": "Which team will win Super Bowl 2024?",
            "outcomes": ["Team A", "Team B"],
            "liquidity_usd": 10000000,  # $10M liquidity
            "volume_24h": 2000000,     # $2M daily volume
            "active_traders": 15000,
            "whale_threshold": 50000,   # $50k for whale detection
            "volatility": "medium",
            "trading_hours": "24/7",
            "event_time": "2024-02-11T23:30:00Z",
            "expected_patterns": [
                "time_decay_trading",
                "injury_news_spikes",
                "last_minute_whales"
            ]
        }
    
    @staticmethod
    def crypto_market() -> Dict[str, Any]:
        """Cryptocurrency price prediction market."""
        return {
            "market_id": "btc_100k_2024",
            "title": "Bitcoin to reach $100k in 2024",
            "description": "Will Bitcoin reach $100,000 USD in 2024?",
            "outcomes": ["Yes", "No"],
            "liquidity_usd": 25000000,  # $25M liquidity
            "volume_24h": 8000000,     # $8M daily volume
            "active_traders": 30000,
            "whale_threshold": 200000,  # $200k for whale detection
            "volatility": "very_high",
            "trading_hours": "24/7",
            "correlation_assets": ["BTC", "ETH", "crypto_index"],
            "expected_patterns": [
                "correlation_trading",
                "institutional_whales",
                "retail_coordination"
            ]
        }
    
    @staticmethod
    def low_liquidity_market() -> Dict[str, Any]:
        """Low liquidity niche market scenario."""
        return {
            "market_id": "niche_tech_ipo",
            "title": "Tech Company XYZ IPO Success",
            "description": "Will Tech Company XYZ IPO be oversubscribed?",
            "outcomes": ["Yes", "No"],
            "liquidity_usd": 500000,    # $500k liquidity
            "volume_24h": 50000,       # $50k daily volume
            "active_traders": 500,
            "whale_threshold": 10000,   # $10k for whale detection
            "volatility": "low",
            "trading_hours": "business_hours",
            "expected_patterns": [
                "low_volume_manipulation",
                "insider_advantage",
                "thin_order_book"
            ]
        }


class ScenarioGenerator:
    """Generates specific trading scenarios for testing."""
    
    @staticmethod
    def generate_news_driven_spike(
        market_id: str,
        news_impact: str = "positive",
        spike_magnitude: float = 3.0
    ) -> List[Dict[str, Any]]:
        """Generate trading pattern following major news."""
        from tests.fixtures.data_generators import MockDataGenerator
        
        generator = MockDataGenerator()
        
        # Base trading before news
        base_trades = generator.generate_normal_trades(
            count=50,
            market_id=market_id,
            time_span_hours=4
        )
        
        # News hits - immediate spike
        news_time = max(trade["timestamp"] for trade in base_trades) + 300
        spike_trades = []
        
        # Initial reaction (5 minutes)
        for i in range(20):
            timestamp = news_time + (i * 15)  # Every 15 seconds
            
            if news_impact == "positive":
                side = "BUY"
                size_multiplier = spike_magnitude
            else:
                side = "SELL"
                size_multiplier = spike_magnitude * 0.8
                
            trade = generator.generate_single_trade(
                market_id=market_id,
                timestamp=timestamp,
                size_usd=random.uniform(500, 2000) * size_multiplier,
                side=side
            )
            spike_trades.append(trade)
        
        # Sustained activity (30 minutes)
        for i in range(60):
            timestamp = news_time + 300 + (i * 30)  # Every 30 seconds
            trade = generator.generate_single_trade(
                market_id=market_id,
                timestamp=timestamp,
                size_usd=random.uniform(200, 1000) * (spike_magnitude * 0.6)
            )
            spike_trades.append(trade)
            
        return base_trades + spike_trades
    
    @staticmethod
    def generate_wash_trading_pattern(
        market_id: str,
        wash_trader_count: int = 3,
        cycle_count: int = 10
    ) -> List[Dict[str, Any]]:
        """Generate wash trading pattern between controlled accounts."""
        from tests.fixtures.data_generators import MockDataGenerator
        
        generator = MockDataGenerator()
        
        # Create wash trader wallets
        wash_wallets = [
            generator.generate_wallet_address() for _ in range(wash_trader_count)
        ]
        
        trades = []
        current_time = generator.base_timestamp
        
        # Generate wash trading cycles
        for cycle in range(cycle_count):
            cycle_start = current_time + (cycle * 300)  # Every 5 minutes
            
            # Each cycle: A -> B -> C -> A
            for i in range(len(wash_wallets)):
                maker = wash_wallets[i]
                taker = wash_wallets[(i + 1) % len(wash_wallets)]
                
                # Similar size trades to avoid detection
                base_size = 1000 + (cycle * 50)
                size_variance = random.uniform(0.9, 1.1)
                
                trade = generator.generate_single_trade(
                    market_id=market_id,
                    timestamp=cycle_start + (i * 30),
                    size_usd=base_size * size_variance,
                    maker=maker,
                    taker=taker,
                    price=0.5 + random.uniform(-0.02, 0.02)  # Stable price
                )
                trades.append(trade)
                
        return trades
    
    @staticmethod
    def generate_insider_accumulation(
        market_id: str,
        insider_wallet: str,
        accumulation_days: int = 7,
        event_day_spike: bool = True
    ) -> List[Dict[str, Any]]:
        """Generate insider trading pattern with gradual accumulation."""
        from tests.fixtures.data_generators import MockDataGenerator
        
        generator = MockDataGenerator()
        trades = []
        
        # Gradual accumulation over time
        daily_trades = 3
        current_time = generator.base_timestamp
        
        for day in range(accumulation_days):
            day_start = current_time + (day * 86400)
            
            for trade_num in range(daily_trades):
                # Spread trades throughout the day
                timestamp = day_start + (trade_num * 28800)  # Every 8 hours
                
                # Gradually increasing position size
                base_size = 5000 + (day * 1000)
                size_variance = random.uniform(0.8, 1.2)
                
                trade = generator.generate_single_trade(
                    market_id=market_id,
                    timestamp=timestamp,
                    size_usd=base_size * size_variance,
                    maker=insider_wallet,
                    side="BUY"
                )
                trades.append(trade)
        
        # Event day spike (if enabled)
        if event_day_spike:
            event_time = current_time + (accumulation_days * 86400)
            
            # Large position close
            for i in range(5):
                trade = generator.generate_single_trade(
                    market_id=market_id,
                    timestamp=event_time + (i * 300),
                    size_usd=random.uniform(20000, 50000),
                    taker=insider_wallet,
                    side="SELL"
                )
                trades.append(trade)
                
        return sorted(trades, key=lambda x: x["timestamp"])


class HistoricalData:
    """Historical data patterns for backtesting."""
    
    @staticmethod
    def load_2020_election_pattern() -> Dict[str, Any]:
        """Load 2020 election trading pattern for comparison."""
        return {
            "market_id": "2020_election_historical",
            "pattern_type": "political_event",
            "key_events": [
                {
                    "timestamp": 1604361600,  # Election day
                    "event": "election_day",
                    "volume_spike": 15.0,
                    "whale_activity": True
                },
                {
                    "timestamp": 1604534400,  # Results day
                    "event": "results_announcement",
                    "volume_spike": 25.0,
                    "whale_activity": True
                }
            ],
            "baseline_volume": 1000000,
            "peak_volume": 25000000,
            "manipulation_incidents": 3,
            "false_positive_rate": 0.05
        }
    
    @staticmethod
    def load_sports_finals_pattern() -> Dict[str, Any]:
        """Load sports finals trading pattern."""
        return {
            "market_id": "sports_finals_historical",
            "pattern_type": "sports_event",
            "pre_event_volume": 2000000,
            "during_event_volume": 500000,
            "post_event_volume": 100000,
            "injury_spike_magnitude": 8.0,
            "weather_impact_magnitude": 3.0,
            "referee_controversy_spike": 12.0
        }


def load_all_fixtures() -> Dict[str, Any]:
    """Load all available test fixtures."""
    return {
        "markets": {
            "presidential": MarketFixtures.presidential_election_market(),
            "sports": MarketFixtures.sports_betting_market(),
            "crypto": MarketFixtures.crypto_market(),
            "low_liquidity": MarketFixtures.low_liquidity_market()
        },
        "scenarios": {
            "news_spike": ScenarioGenerator.generate_news_driven_spike("test_market"),
            "wash_trading": ScenarioGenerator.generate_wash_trading_pattern("test_market"),
            "insider_trading": ScenarioGenerator.generate_insider_accumulation(
                "test_market", "0xinsider123"
            )
        },
        "historical": {
            "election_2020": HistoricalData.load_2020_election_pattern(),
            "sports_finals": HistoricalData.load_sports_finals_pattern()
        }
    }
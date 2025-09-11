"""
WebSocket message fixtures for testing real-time data processing.
"""
from typing import List, Dict, Any
import json
import time


class WebSocketFixtures:
    """Pre-defined WebSocket message patterns for testing."""
    
    @staticmethod
    def connection_handshake_messages() -> List[Dict[str, Any]]:
        """WebSocket connection handshake messages."""
        return [
            {
                "type": "connection",
                "status": "connected",
                "timestamp": int(time.time()),
                "subscriptions": []
            },
            {
                "type": "subscription",
                "channel": "trades",
                "status": "subscribed",
                "market_id": "all"
            },
            {
                "type": "subscription", 
                "channel": "orders",
                "status": "subscribed",
                "market_id": "all"
            }
        ]
    
    @staticmethod
    def trade_messages() -> List[Dict[str, Any]]:
        """Sample trade messages in WebSocket format."""
        return [
            {
                "type": "trade",
                "channel": "trades",
                "market": "market_123",
                "data": {
                    "id": "trade_001",
                    "market": "market_123",
                    "maker": "0xmaker123",
                    "taker": "0xtaker456",
                    "size": "1500.00",
                    "price": "0.65",
                    "side": "BUY",
                    "timestamp": int(time.time()),
                    "outcome": "YES"
                }
            },
            {
                "type": "trade",
                "channel": "trades", 
                "market": "market_123",
                "data": {
                    "id": "trade_002",
                    "market": "market_123",
                    "maker": "0xmaker789",
                    "taker": "0xtaker012",
                    "size": "25000.00",  # Whale trade
                    "price": "0.67",
                    "side": "BUY",
                    "timestamp": int(time.time()) + 30,
                    "outcome": "YES"
                }
            }
        ]
    
    @staticmethod
    def order_messages() -> List[Dict[str, Any]]:
        """Sample order messages in WebSocket format."""
        return [
            {
                "type": "order",
                "channel": "orders",
                "market": "market_456",
                "data": {
                    "id": "order_001",
                    "market": "market_456",
                    "maker": "0xordermaker1",
                    "size": "5000.00",
                    "price": "0.45",
                    "side": "BUY",
                    "timestamp": int(time.time()),
                    "outcome": "NO",
                    "status": "open"
                }
            },
            {
                "type": "order",
                "channel": "orders",
                "market": "market_456", 
                "data": {
                    "id": "order_002",
                    "market": "market_456",
                    "maker": "0xordermaker2",
                    "size": "50000.00",  # Large order
                    "price": "0.47",
                    "side": "SELL",
                    "timestamp": int(time.time()) + 60,
                    "outcome": "NO",
                    "status": "open"
                }
            }
        ]
    
    @staticmethod
    def market_update_messages() -> List[Dict[str, Any]]:
        """Market status update messages."""
        return [
            {
                "type": "market_update",
                "channel": "markets",
                "data": {
                    "market_id": "market_789",
                    "status": "active",
                    "volume_24h": "2500000.00",
                    "price": "0.55",
                    "liquidity": "10000000.00",
                    "timestamp": int(time.time())
                }
            },
            {
                "type": "market_update",
                "channel": "markets",
                "data": {
                    "market_id": "market_789",
                    "status": "suspended",
                    "reason": "high_volatility",
                    "timestamp": int(time.time()) + 120
                }
            }
        ]
    
    @staticmethod
    def error_messages() -> List[Dict[str, Any]]:
        """Error and edge case messages."""
        return [
            {
                "type": "error",
                "code": "RATE_LIMIT",
                "message": "Rate limit exceeded",
                "timestamp": int(time.time())
            },
            {
                "type": "error",
                "code": "INVALID_MARKET",
                "message": "Market not found",
                "market_id": "invalid_market",
                "timestamp": int(time.time()) + 30
            },
            {
                "type": "connection",
                "status": "disconnected",
                "reason": "timeout",
                "timestamp": int(time.time()) + 60
            }
        ]
    
    @staticmethod
    def malformed_messages() -> List[str]:
        """Malformed JSON messages for error handling tests."""
        return [
            '{"type": "trade", "incomplete":',  # Incomplete JSON
            '{"type": "trade", "data": {"invalid_field"}}',  # Invalid structure
            'not_json_at_all',  # Not JSON
            '{}',  # Empty message
            '{"type": null}',  # Null type
            '{"type": "trade", "data": {"size": "not_a_number"}}'  # Invalid data types
        ]
    
    @staticmethod
    def volume_spike_sequence() -> List[Dict[str, Any]]:
        """Sequence of messages that should trigger volume spike detection."""
        base_time = int(time.time())
        messages = []
        
        # Normal trading for 5 minutes
        for i in range(10):
            messages.append({
                "type": "trade",
                "channel": "trades",
                "market": "spike_market",
                "data": {
                    "id": f"normal_trade_{i}",
                    "market": "spike_market",
                    "maker": f"0xnormal{i}",
                    "taker": f"0xnormal{i+100}",
                    "size": "500.00",
                    "price": "0.50",
                    "side": "BUY" if i % 2 == 0 else "SELL",
                    "timestamp": base_time + (i * 30),
                    "outcome": "YES"
                }
            })
        
        # Volume spike - 20 trades in 2 minutes
        spike_start = base_time + 300
        for i in range(20):
            messages.append({
                "type": "trade",
                "channel": "trades",
                "market": "spike_market",
                "data": {
                    "id": f"spike_trade_{i}",
                    "market": "spike_market",
                    "maker": f"0xspike{i}",
                    "taker": f"0xspike{i+50}",
                    "size": "2000.00",  # 4x normal size
                    "price": "0.52",
                    "side": "BUY",
                    "timestamp": spike_start + (i * 6),  # Every 6 seconds
                    "outcome": "YES"
                }
            })
            
        return messages
    
    @staticmethod
    def whale_accumulation_sequence() -> List[Dict[str, Any]]:
        """Sequence showing whale accumulation pattern."""
        base_time = int(time.time())
        whale_wallet = "0xwhale_accumulator"
        messages = []
        
        # Whale makes 8 large trades over 30 minutes
        for i in range(8):
            messages.append({
                "type": "trade",
                "channel": "trades",
                "market": "whale_market",
                "data": {
                    "id": f"whale_trade_{i}",
                    "market": "whale_market",
                    "maker": whale_wallet,
                    "taker": f"0xcounter{i}",
                    "size": f"{15000 + (i * 2000)}.00",  # Increasing size
                    "price": f"0.{50 + i}",  # Slightly increasing price
                    "side": "BUY",
                    "timestamp": base_time + (i * 225),  # Every 3.75 minutes
                    "outcome": "YES"
                }
            })
            
        return messages
    
    @staticmethod
    def coordination_sequence() -> List[Dict[str, Any]]:
        """Sequence showing coordinated trading."""
        base_time = int(time.time())
        coordinated_wallets = [
            "0xcoord1", "0xcoord2", "0xcoord3", "0xcoord4", "0xcoord5"
        ]
        messages = []
        
        # All wallets trade within 5-minute window
        for i, wallet in enumerate(coordinated_wallets):
            # Each wallet makes 2-3 trades
            trade_count = 2 + (i % 2)
            for j in range(trade_count):
                messages.append({
                    "type": "trade",
                    "channel": "trades",
                    "market": "coord_market",
                    "data": {
                        "id": f"coord_trade_{i}_{j}",
                        "market": "coord_market",
                        "maker": wallet,
                        "taker": f"0xcounter{i}{j}",
                        "size": f"{8000 + (j * 1000)}.00",
                        "price": "0.45",
                        "side": "BUY",  # All same side
                        "timestamp": base_time + (i * 60) + (j * 20),
                        "outcome": "YES"
                    }
                })
                
        return messages
    
    @staticmethod
    def pump_and_dump_sequence() -> List[Dict[str, Any]]:
        """Sequence showing pump and dump pattern."""
        base_time = int(time.time())
        messages = []
        
        # Pump phase - 15 minutes of increasing prices
        pump_duration = 15 * 60  # 15 minutes
        pump_trades = 30
        
        for i in range(pump_trades):
            price_increase = (i / pump_trades) * 0.3  # Price increases by 0.3
            price = 0.4 + price_increase
            
            messages.append({
                "type": "trade",
                "channel": "trades",
                "market": "pump_market",
                "data": {
                    "id": f"pump_trade_{i}",
                    "market": "pump_market",
                    "maker": f"0xpumper{i}",
                    "taker": f"0xpump_target{i}",
                    "size": f"{2000 + (i * 100)}.00",  # Increasing volume
                    "price": f"{price:.3f}",
                    "side": "BUY",
                    "timestamp": base_time + (i * 30),  # Every 30 seconds
                    "outcome": "YES"
                }
            })
        
        # Dump phase - 5 minutes of rapid selling
        dump_start = base_time + pump_duration
        dump_trades = 20
        
        for i in range(dump_trades):
            price_decrease = (i / dump_trades) * 0.4  # Price drops by 0.4
            price = 0.7 - price_decrease
            
            messages.append({
                "type": "trade",
                "channel": "trades",
                "market": "pump_market",
                "data": {
                    "id": f"dump_trade_{i}",
                    "market": "pump_market",
                    "maker": f"0xdumper{i}",
                    "taker": f"0xdump_target{i}",
                    "size": f"{5000 + (i * 200)}.00",  # Large volumes
                    "price": f"{max(0.01, price):.3f}",
                    "side": "SELL",
                    "timestamp": dump_start + (i * 15),  # Every 15 seconds
                    "outcome": "YES"
                }
            })
            
        return messages


def create_mock_websocket_stream(
    message_sequences: List[List[Dict[str, Any]]],
    delay_between_messages: float = 0.1
) -> List[str]:
    """Create a mock WebSocket message stream from multiple sequences."""
    all_messages = []
    
    # Flatten all sequences and sort by timestamp
    for sequence in message_sequences:
        all_messages.extend(sequence)
    
    # Sort by timestamp if available
    def get_timestamp(msg):
        if 'timestamp' in msg:
            return msg['timestamp']
        elif 'data' in msg and 'timestamp' in msg['data']:
            return msg['data']['timestamp']
        else:
            return 0
    
    all_messages.sort(key=get_timestamp)
    
    # Convert to JSON strings
    return [json.dumps(msg) for msg in all_messages]
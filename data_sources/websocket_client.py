"""
Polymarket WebSocket Client
Real-time order book updates for market monitoring
"""

import websocket
import json
import logging
import threading
import time
from typing import List, Callable, Dict
from datetime import datetime, timezone
from colorama import init, Fore, Back, Style

# Initialize colorama
init(autoreset=True)

logger = logging.getLogger(__name__)

class WebSocketClient:
    """WebSocket client for real-time Polymarket order book data"""
    
    def __init__(self, market_ids: List[str], on_trade_callback: Callable[[Dict], None], debug_config: Dict = None):
        self.market_ids = market_ids  # These are actually token IDs for WebSocket
        self.on_trade_callback = on_trade_callback  # Keep for compatibility, not used for order books
        self.ws_url = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
        self.ws = None
        self.is_connected = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        self.reconnect_delay = 5  # seconds
        self.heartbeat_thread = None
        self.should_reconnect = True
        
        # Debug configuration
        self.debug_config = debug_config or {}
        self.debug_mode = self.debug_config.get('debug_mode', False)
        self.show_activity = self.debug_config.get('websocket_activity_logging', False)
        
        # Activity tracking
        self.messages_received = 0
        self.order_books_received = 0
        self.last_activity_report = datetime.now(timezone.utc)
        self.activity_report_interval = self.debug_config.get('activity_report_interval', 300)  # 5 minutes
        
    def connect(self):
        """Establish WebSocket connection"""
        try:
            self.ws = websocket.WebSocketApp(
                self.ws_url,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close
            )
            
            # Run in separate thread to avoid blocking
            wst = threading.Thread(target=self.ws.run_forever)
            wst.daemon = True
            wst.start()
            
            logger.info(f"Connecting to WebSocket: {self.ws_url}")
            
        except Exception as e:
            logger.error(f"Failed to establish WebSocket connection: {e}")
            self._schedule_reconnect()
    
    def _on_open(self, ws):
        """Called when WebSocket connection is established"""
        print(f"{Fore.GREEN}✅ {Style.BRIGHT}WebSocket Connected{Style.RESET_ALL}")
        self.is_connected = True
        self.reconnect_attempts = 0
        
        # Subscribe to market channels
        self._subscribe_to_markets()
        
        # Start heartbeat
        self._start_heartbeat()
    
    def _on_message(self, ws, message):
        """Handle incoming WebSocket messages"""
        try:
            # Track message count
            self.messages_received += 1
            
            # Handle non-JSON messages (like PONG)
            if message.strip() in ['PONG', '[]']:
                if self.show_activity:
                    logger.debug(f"📥 Heartbeat response: {message}")
                return
            
            # Log raw messages in debug mode (truncated)
            if self.debug_mode:
                logger.debug(f"📥 WebSocket message #{self.messages_received}: {message[:200]}...")
            
            data = json.loads(message)
            
            # Report activity periodically
            self._report_activity_if_needed()
            
            # Handle list messages (empty subscription responses)
            if isinstance(data, list):
                if not data:
                    logger.debug("📩 Received empty list (subscription confirmation)")
                    return
                # Process list of trade events
                for item in data:
                    if isinstance(item, dict):
                        self._process_trade_event(item)
                return
            
            # Handle dictionary messages
            if isinstance(data, dict):
                self._process_trade_event(data)
                
        except json.JSONDecodeError:
            # Handle non-JSON messages
            if 'PONG' in message or message.strip() == '[]':
                logger.debug(f"📥 Non-JSON message: {message}")
            else:
                logger.warning(f"Failed to parse WebSocket message: {message[:100]}...")
            
        except Exception as e:
            logger.error(f"Error processing WebSocket message: {e}")
    
    def _process_trade_event(self, data: Dict):
        """Process individual trade event"""
        try:
            msg_type = data.get('type', data.get('event', ''))
            
            # Handle subscription confirmations
            if msg_type in ['subscribed', 'SUBSCRIBED', 'subscription_success']:
                logger.info(f"✅ Subscribed successfully: {data}")
                
            elif msg_type in ['error', 'ERROR']:
                logger.error(f"❌ WebSocket error message: {data}")
                
            else:
                # This is an order book update
                self.order_books_received += 1
                # Order book display removed - count now shown in System Status
                if self.debug_mode:
                    logger.debug(f"📩 Order book #{self.order_books_received} for market {data.get('market', 'Unknown')[:10]}...")
                
        except Exception as e:
            logger.error(f"Error processing trade event: {e}")
    
    def _report_activity_if_needed(self):
        """Report WebSocket activity periodically"""
        now = datetime.now(timezone.utc)
        time_since_last_report = (now - self.last_activity_report).total_seconds()
        
        if time_since_last_report >= self.activity_report_interval:
            if self.show_activity:
                print(f"📊 WebSocket Activity: {self.messages_received} messages, "
                      f"{self.order_books_received} order books")
            
            # Reset counters for next period and update stats tracking
            self.messages_received = 0
            self.order_books_received = 0
            self.last_activity_report = now
    
    def get_activity_stats(self) -> Dict:
        """Get current activity statistics"""
        return {
            'messages_received': self.messages_received,
            'order_books_received': self.order_books_received,
            'is_connected': self.is_connected,
            'reconnect_attempts': self.reconnect_attempts
        }
    
    def _on_error(self, ws, error):
        """Handle WebSocket errors"""
        logger.error(f"WebSocket error: {error}")
        self.is_connected = False
    
    def _on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket connection close"""
        logger.warning(f"WebSocket disconnected (code: {close_status_code}, msg: {close_msg})")
        self.is_connected = False
        self._stop_heartbeat()
        
        if self.should_reconnect:
            self._schedule_reconnect()
    
    def _subscribe_to_markets(self):
        """Subscribe to trade events for monitored markets"""
        if not self.ws or not self.market_ids:
            return
            
        # Subscribe to market data (order books)
        subscriptions = [
            # Market data subscription
            {"type": "MARKET", "assets_ids": self.market_ids},
        ]
        
        try:
            # Send market data subscription only (order books)
            market_sub = subscriptions[0]  # MARKET subscription
            sub_json = json.dumps(market_sub)
            logger.info(f"📤 Sending MARKET subscription for {len(self.market_ids)} tokens")
            if self.debug_mode:
                logger.debug(f"📤 Subscription: {sub_json[:200]}...")
            self.ws.send(sub_json)
            
            logger.info(f"✅ Sent MARKET subscription for {len(self.market_ids)} tokens")
            
        except Exception as e:
            logger.error(f"❌ Failed to subscribe to markets: {e}")
    
    
    def _start_heartbeat(self):
        """Start heartbeat to keep connection alive"""
        def heartbeat():
            while self.is_connected:
                try:
                    if self.ws:
                        ping_msg = {"type": "ping"}
                        self.ws.send(json.dumps(ping_msg))
                        logger.debug("Sent heartbeat ping")
                except Exception as e:
                    logger.error(f"Heartbeat failed: {e}")
                    break
                    
                time.sleep(30)  # Ping every 30 seconds
        
        self.heartbeat_thread = threading.Thread(target=heartbeat)
        self.heartbeat_thread.daemon = True
        self.heartbeat_thread.start()
    
    def _stop_heartbeat(self):
        """Stop heartbeat thread"""
        if self.heartbeat_thread:
            self.heartbeat_thread = None
    
    def _schedule_reconnect(self):
        """Schedule reconnection attempt"""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error("Max reconnection attempts reached. Giving up on WebSocket.")
            return
        
        self.reconnect_attempts += 1
        delay = self.reconnect_delay * (2 ** min(self.reconnect_attempts - 1, 4))  # Exponential backoff
        
        logger.info(f"Scheduling reconnect attempt {self.reconnect_attempts}/{self.max_reconnect_attempts} in {delay}s")
        
        def reconnect():
            time.sleep(delay)
            if self.should_reconnect:
                logger.info("Attempting WebSocket reconnection...")
                self.connect()
        
        reconnect_thread = threading.Thread(target=reconnect)
        reconnect_thread.daemon = True
        reconnect_thread.start()
    
    def disconnect(self):
        """Gracefully disconnect WebSocket"""
        logger.info("Disconnecting WebSocket...")
        self.should_reconnect = False
        self.is_connected = False
        
        if self.ws:
            self.ws.close()
            
        self._stop_heartbeat()
    
    def add_markets(self, market_ids: List[str]):
        """Add new markets to monitor"""
        new_markets = [mid for mid in market_ids if mid not in self.market_ids]
        
        if new_markets:
            self.market_ids.extend(new_markets)
            
            if self.is_connected:
                self._subscribe_to_markets()
                
            logger.info(f"Added {len(new_markets)} new markets to monitoring")
    
    def remove_markets(self, market_ids: List[str]):
        """Remove markets from monitoring"""
        for mid in market_ids:
            if mid in self.market_ids:
                self.market_ids.remove(mid)
        
        # Note: WebSocket API might not support unsubscribe, would need reconnect
        logger.info(f"Removed {len(market_ids)} markets from monitoring")
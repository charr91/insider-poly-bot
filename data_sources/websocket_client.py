"""
Polymarket WebSocket Client
Real-time trade stream for immediate detection
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
    """WebSocket client for real-time Polymarket trade data"""
    
    def __init__(self, market_ids: List[str], on_trade_callback: Callable[[Dict], None], debug_config: Dict = None):
        self.market_ids = market_ids  # These are actually token IDs for WebSocket
        self.on_trade_callback = on_trade_callback
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
        self.trades_processed = 0
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
            
            if msg_type in ['trade', 'TRADE']:
                # This is a trade event - process it
                trade_data = self._normalize_trade_data(data)
                
                if trade_data:
                    self.trades_processed += 1
                    
                    # Add timestamp if not present
                    if 'timestamp' not in trade_data:
                        trade_data['timestamp'] = datetime.now().timestamp()
                    
                    # Call the trade callback
                    self.on_trade_callback(trade_data)
                    
                    if self.show_activity or self.debug_mode:
                        side_color = Fore.GREEN if trade_data.get('side') == 'BUY' else Fore.RED
                        print(f"{Fore.YELLOW}🚨 {Style.BRIGHT}TRADE DETECTED #{self.trades_processed}{Style.RESET_ALL}")
                        print(f"   {Fore.CYAN}Size:{Style.RESET_ALL} {Fore.GREEN}${trade_data.get('size', 0):.2f}{Style.RESET_ALL} @ {Fore.WHITE}{trade_data.get('price', 0):.3f}{Style.RESET_ALL} {side_color}({trade_data.get('side', 'UNK')}){Style.RESET_ALL}")
                    else:
                        logger.debug(f"📈 Processed trade: {trade_data.get('size', 0)} @ {trade_data.get('price', 0)}")
                    
            elif msg_type in ['subscribed', 'SUBSCRIBED', 'subscription_success']:
                logger.info(f"✅ Subscribed successfully: {data}")
                
            elif msg_type in ['error', 'ERROR']:
                logger.error(f"❌ WebSocket error message: {data}")
                
            else:
                # This is an order book update
                self.order_books_received += 1
                if self.show_activity and self.order_books_received <= 3:
                    # Show first few order book updates to confirm we're getting data
                    market_id = data.get('market', data.get('asset_id', 'Unknown'))[:10]
                    msg_type_display = msg_type if msg_type else 'order_book'
                    print(f"{Fore.BLUE}📩 {Style.BRIGHT}Order Book #{self.order_books_received}:{Style.RESET_ALL} {Fore.CYAN}{market_id}...{Style.RESET_ALL} {Fore.WHITE}({msg_type_display}){Style.RESET_ALL}")
                elif self.show_activity:
                    logger.debug(f"📩 Order book #{self.order_books_received} for market {data.get('market', 'Unknown')[:10]}...")
                
        except Exception as e:
            logger.error(f"Error processing trade event: {e}")
    
    def _report_activity_if_needed(self):
        """Report WebSocket activity periodically"""
        now = datetime.now(timezone.utc)
        time_since_last_report = (now - self.last_activity_report).total_seconds()
        
        if time_since_last_report >= self.activity_report_interval:
            if self.show_activity or self.debug_mode:
                # Format time display appropriately
                if time_since_last_report >= 60:
                    time_display = f"{int(time_since_last_report/60)} min"
                else:
                    time_display = f"{int(time_since_last_report)} sec"
                
                # Create a nice activity report box with consistent width
                title = f"─ WebSocket Activity ({time_display}) "
                remaining_dashes = max(0, 48 - len(title))  # Target total width of 48 inside chars
                top_border = f"┌{title}{'─' * remaining_dashes}┐"
                total_width = len(top_border)
                
                print(f"{Fore.MAGENTA}{top_border}{Style.RESET_ALL}")
                print(f"{Fore.MAGENTA}│{Style.RESET_ALL} {Fore.CYAN}Messages:{Style.RESET_ALL} {Fore.WHITE}{self.messages_received:>4}{Style.RESET_ALL} {Fore.MAGENTA}│{Style.RESET_ALL} {Fore.CYAN}Trades:{Style.RESET_ALL} {Fore.GREEN if self.trades_processed > 0 else Fore.YELLOW}{self.trades_processed:>4}{Style.RESET_ALL} {Fore.MAGENTA}│{Style.RESET_ALL} {Fore.CYAN}Books:{Style.RESET_ALL} {Fore.BLUE}{self.order_books_received:>4}{Style.RESET_ALL} {Fore.MAGENTA}│{Style.RESET_ALL}")
                print(f"{Fore.MAGENTA}└{'─' * (total_width - 2)}┘{Style.RESET_ALL}")  # -2 for └┘
            
            # Reset counters for next period
            self.messages_received = 0
            self.trades_processed = 0  
            self.order_books_received = 0
            self.last_activity_report = now
    
    def get_activity_stats(self) -> Dict:
        """Get current activity statistics"""
        return {
            'messages_received': self.messages_received,
            'trades_processed': self.trades_processed,
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
            
        # Use correct Polymarket WebSocket format  
        # assets_ids should be token IDs from clobTokenIds
        subscribe_msg = {
            "type": "MARKET",
            "assets_ids": self.market_ids  # Subscribe to all tokens
        }
        
        try:
            msg_json = json.dumps(subscribe_msg)
            logger.info(f"📤 Sending subscription for {len(self.market_ids)} tokens")
            logger.debug(f"📤 Full subscription: {msg_json[:200]}...")
            self.ws.send(msg_json)
            logger.info(f"✅ Sent subscription to WebSocket for {len(self.market_ids)} tokens")
            
        except Exception as e:
            logger.error(f"❌ Failed to subscribe to markets: {e}")
    
    def _normalize_trade_data(self, data: Dict) -> Dict:
        """Normalize WebSocket trade data to standard format"""
        try:
            # Extract trade information from WebSocket message
            normalized = {
                'market': data.get('market'),
                'price': float(data.get('price', 0)),
                'size': float(data.get('size', 0)),
                'side': data.get('side', '').upper(),
                'maker': data.get('maker'),
                'taker': data.get('taker'),
                'timestamp': data.get('timestamp', datetime.now().timestamp()),
                'tx_hash': data.get('txHash') or data.get('transaction_hash'),
                'source': 'websocket'
            }
            
            # Validate required fields
            if not normalized['market'] or normalized['price'] <= 0 or normalized['size'] <= 0:
                logger.warning(f"Invalid trade data received: {data}")
                return None
                
            return normalized
            
        except (ValueError, TypeError) as e:
            logger.warning(f"Error normalizing trade data: {e}")
            return None
    
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
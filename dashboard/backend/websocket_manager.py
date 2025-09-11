"""
WebSocket Manager for Real-time Dashboard Communication

Handles WebSocket connections, subscriptions, and real-time data streaming
for the insider trading detection dashboard.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Set, Any, Optional

from fastapi import WebSocket


logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages WebSocket connections and real-time data streaming"""
    
    def __init__(self):
        # Store active WebSocket connections
        self.active_connections: Dict[str, WebSocket] = {}
        
        # Store client subscriptions to different data channels
        self.subscriptions: Dict[str, Set[str]] = {
            "alerts": set(),
            "markets": set(), 
            "anomaly_scores": set(),
            "system_health": set(),
            "wallet_coordination": set(),
            "cross_market_correlation": set(),
            "wash_trading": set(),
            "historical_baseline": set()
        }
        
        # Store client metadata
        self.client_metadata: Dict[str, Dict[str, Any]] = {}
        
        # Data streaming control
        self.streaming_active = False
        self.streaming_tasks: List[asyncio.Task] = []
    
    async def connect(self, websocket: WebSocket, channel: Optional[str] = None) -> str:
        """Connect a new WebSocket client"""
        await websocket.accept()
        
        client_id = str(uuid.uuid4())
        self.active_connections[client_id] = websocket
        
        # Store client metadata
        self.client_metadata[client_id] = {
            "connected_at": datetime.utcnow(),
            "channel": channel,
            "subscriptions": set()
        }
        
        # Auto-subscribe to channel if specified
        if channel and channel in self.subscriptions:
            self.subscriptions[channel].add(client_id)
            self.client_metadata[client_id]["subscriptions"].add(channel)
        
        logger.info(f"Client {client_id} connected" + (f" to channel {channel}" if channel else ""))
        
        # Send welcome message
        await self.send_personal_message(client_id, {
            "type": "welcome",
            "client_id": client_id,
            "timestamp": datetime.utcnow().isoformat(),
            "available_channels": list(self.subscriptions.keys())
        })
        
        return client_id
    
    async def disconnect(self, client_id: str):
        """Disconnect a WebSocket client"""
        if client_id in self.active_connections:
            # Remove from all subscriptions
            for channel, clients in self.subscriptions.items():
                clients.discard(client_id)
            
            # Clean up metadata and connections
            del self.active_connections[client_id]
            if client_id in self.client_metadata:
                del self.client_metadata[client_id]
            
            logger.info(f"Client {client_id} disconnected")
    
    async def send_personal_message(self, client_id: str, data: Dict[str, Any]):
        """Send message to specific client"""
        if client_id in self.active_connections:
            try:
                websocket = self.active_connections[client_id]
                await websocket.send_text(json.dumps(data))
            except Exception as e:
                logger.error(f"Failed to send message to client {client_id}: {e}")
                await self.disconnect(client_id)
    
    async def broadcast_to_channel(self, channel: str, data: Dict[str, Any]):
        """Broadcast message to all clients subscribed to a channel"""
        if channel in self.subscriptions:
            disconnected_clients = []
            
            for client_id in self.subscriptions[channel].copy():
                try:
                    await self.send_personal_message(client_id, data)
                except Exception as e:
                    logger.error(f"Failed to broadcast to client {client_id}: {e}")
                    disconnected_clients.append(client_id)
            
            # Clean up disconnected clients
            for client_id in disconnected_clients:
                await self.disconnect(client_id)
    
    async def subscribe_client(self, client_id: str, channels: List[str]):
        """Subscribe client to one or more channels"""
        if client_id not in self.active_connections:
            return
        
        for channel in channels:
            if channel in self.subscriptions:
                self.subscriptions[channel].add(client_id)
                self.client_metadata[client_id]["subscriptions"].add(channel)
                logger.info(f"Client {client_id} subscribed to {channel}")
                
                # Send subscription confirmation
                await self.send_personal_message(client_id, {
                    "type": "subscription_confirmed",
                    "channel": channel,
                    "timestamp": datetime.utcnow().isoformat()
                })
    
    async def unsubscribe_client(self, client_id: str, channels: List[str]):
        """Unsubscribe client from one or more channels"""
        if client_id not in self.active_connections:
            return
        
        for channel in channels:
            if channel in self.subscriptions:
                self.subscriptions[channel].discard(client_id)
                self.client_metadata[client_id]["subscriptions"].discard(channel)
                logger.info(f"Client {client_id} unsubscribed from {channel}")
                
                # Send unsubscription confirmation
                await self.send_personal_message(client_id, {
                    "type": "unsubscription_confirmed", 
                    "channel": channel,
                    "timestamp": datetime.utcnow().isoformat()
                })
    
    async def start_data_streaming(self):
        """Start background tasks for real-time data streaming"""
        if self.streaming_active:
            return
        
        self.streaming_active = True
        logger.info("🔄 Starting real-time data streaming tasks")
        
        # Start different streaming tasks
        self.streaming_tasks = [
            asyncio.create_task(self.stream_market_data()),
            asyncio.create_task(self.stream_anomaly_scores()),
            asyncio.create_task(self.stream_system_health()),
            asyncio.create_task(self.stream_alert_updates())
        ]
    
    async def stop_data_streaming(self):
        """Stop all data streaming tasks"""
        self.streaming_active = False
        logger.info("🛑 Stopping data streaming tasks")
        
        for task in self.streaming_tasks:
            task.cancel()
        
        await asyncio.gather(*self.streaming_tasks, return_exceptions=True)
        self.streaming_tasks = []
    
    async def stream_market_data(self):
        """Stream real-time market data updates"""
        while self.streaming_active:
            try:
                # TODO: Connect to actual bot data source
                # For now, simulate market data
                market_data = {
                    "type": "market_data",
                    "timestamp": datetime.utcnow().isoformat(),
                    "data": {
                        "active_markets": 47,
                        "total_volume": 125000.50,
                        "alerts_last_hour": 3
                    }
                }
                
                await self.broadcast_to_channel("markets", market_data)
                await asyncio.sleep(5)  # Update every 5 seconds
                
            except Exception as e:
                logger.error(f"Error in market data streaming: {e}")
                await asyncio.sleep(10)
    
    async def stream_anomaly_scores(self):
        """Stream real-time anomaly score updates"""
        while self.streaming_active:
            try:
                # TODO: Connect to bot's anomaly detection system
                # For now, simulate anomaly scores
                anomaly_data = {
                    "type": "anomaly_scores",
                    "timestamp": datetime.utcnow().isoformat(),
                    "data": {
                        "current_max_score": 7.2,
                        "active_alerts": 2,
                        "confidence_bonuses": {
                            "coordination": 2.0,
                            "historical_match": 1.0
                        }
                    }
                }
                
                await self.broadcast_to_channel("anomaly_scores", anomaly_data)
                await asyncio.sleep(3)  # Update every 3 seconds
                
            except Exception as e:
                logger.error(f"Error in anomaly score streaming: {e}")
                await asyncio.sleep(10)
    
    async def stream_system_health(self):
        """Stream system health monitoring data"""
        while self.streaming_active:
            try:
                # TODO: Connect to bot's system monitoring
                system_health = {
                    "type": "system_health",
                    "timestamp": datetime.utcnow().isoformat(),
                    "data": {
                        "websocket_status": "connected",
                        "api_rate_limit": 85.5,
                        "memory_usage": 245.8,
                        "active_connections": len(self.active_connections),
                        "detection_algorithms": {
                            "volume_detector": "active",
                            "whale_detector": "active", 
                            "price_detector": "active",
                            "coordination_detector": "active"
                        }
                    }
                }
                
                await self.broadcast_to_channel("system_health", system_health)
                await asyncio.sleep(10)  # Update every 10 seconds
                
            except Exception as e:
                logger.error(f"Error in system health streaming: {e}")
                await asyncio.sleep(15)
    
    async def stream_alert_updates(self):
        """Stream new alert notifications"""
        while self.streaming_active:
            try:
                # TODO: Monitor bot's alert system for new alerts
                # For now, simulate occasional alerts
                await asyncio.sleep(30)  # Check every 30 seconds
                
                # Simulate alert (remove in production)
                if len(self.subscriptions["alerts"]) > 0:
                    alert_data = {
                        "type": "new_alert",
                        "timestamp": datetime.utcnow().isoformat(),
                        "data": {
                            "severity": "HIGH",
                            "market": "2024 Presidential Election",
                            "anomaly_score": 9.5,
                            "confidence_bonuses": ["coordination", "volume_spike"],
                            "description": "Coordinated whale activity detected"
                        }
                    }
                    
                    await self.broadcast_to_channel("alerts", alert_data)
                
            except Exception as e:
                logger.error(f"Error in alert streaming: {e}")
                await asyncio.sleep(30)
    
    async def cleanup(self):
        """Cleanup all connections and resources"""
        logger.info("🧹 Cleaning up WebSocket manager")
        
        # Stop streaming
        await self.stop_data_streaming()
        
        # Close all connections
        for client_id in list(self.active_connections.keys()):
            try:
                await self.active_connections[client_id].close()
            except Exception as e:
                logger.error(f"Error closing connection for {client_id}: {e}")
        
        # Clear all data
        self.active_connections.clear()
        self.client_metadata.clear()
        for channel in self.subscriptions:
            self.subscriptions[channel].clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get WebSocket manager statistics"""
        return {
            "total_connections": len(self.active_connections),
            "channel_subscriptions": {
                channel: len(clients) for channel, clients in self.subscriptions.items()
            },
            "streaming_active": self.streaming_active,
            "active_tasks": len(self.streaming_tasks)
        }
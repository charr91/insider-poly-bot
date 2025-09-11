"""
FastAPI backend for Insider Trading Detection Dashboard

Provides real-time WebSocket communication, REST API endpoints,
and integration with the bot's detection algorithms.
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

from websocket_manager import WebSocketManager
from api_routes import router as api_router
from config_manager import DashboardConfig


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Polymarket Insider Trading Detection Dashboard",
    description="Real-time monitoring and analytics dashboard for insider trading detection",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# Configure CORS for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  # React dev server
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Initialize WebSocket manager
ws_manager = WebSocketManager()

# Initialize dashboard configuration
dashboard_config = DashboardConfig()


@app.on_event("startup")
async def startup_event():
    """Initialize dashboard backend on startup"""
    logger.info("🚀 Starting Insider Trading Detection Dashboard Backend")
    logger.info(f"📊 Dashboard API: http://localhost:8000/api/docs")
    logger.info(f"🔌 WebSocket endpoint: ws://localhost:8000/ws")
    
    # Initialize background tasks for real-time data streaming
    asyncio.create_task(ws_manager.start_data_streaming())


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("🛑 Shutting down dashboard backend")
    await ws_manager.cleanup()


@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    """Serve the frontend application"""
    frontend_path = Path(__file__).parent.parent / "frontend" / "index.html"
    if frontend_path.exists():
        return HTMLResponse(content=frontend_path.read_text())
    return HTMLResponse(
        content="<h1>Insider Trading Detection Dashboard</h1><p>Frontend not built yet. Visit <a href='/api/docs'>/api/docs</a> for API documentation.</p>"
    )


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time data streaming
    
    Handles real-time communication for:
    - Market data updates
    - Alert notifications  
    - Anomaly score updates
    - System health status
    """
    client_id = await ws_manager.connect(websocket)
    logger.info(f"🔌 WebSocket client connected: {client_id}")
    
    try:
        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Handle different message types
            if message.get("type") == "subscribe":
                await ws_manager.subscribe_client(client_id, message.get("channels", []))
            elif message.get("type") == "unsubscribe":
                await ws_manager.unsubscribe_client(client_id, message.get("channels", []))
            elif message.get("type") == "ping":
                await websocket.send_text(json.dumps({
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                }))
                
    except WebSocketDisconnect:
        logger.info(f"🔌 WebSocket client disconnected: {client_id}")
    except Exception as e:
        logger.error(f"❌ WebSocket error for client {client_id}: {e}")
    finally:
        await ws_manager.disconnect(client_id)


@app.websocket("/ws/alerts")
async def alerts_websocket(websocket: WebSocket):
    """Dedicated WebSocket endpoint for alert notifications"""
    client_id = await ws_manager.connect(websocket, channel="alerts")
    logger.info(f"🚨 Alert WebSocket client connected: {client_id}")
    
    try:
        while True:
            await asyncio.sleep(1)  # Keep connection alive
    except WebSocketDisconnect:
        logger.info(f"🚨 Alert WebSocket client disconnected: {client_id}")
    finally:
        await ws_manager.disconnect(client_id)


@app.websocket("/ws/system")
async def system_websocket(websocket: WebSocket):
    """Dedicated WebSocket endpoint for system health monitoring"""
    client_id = await ws_manager.connect(websocket, channel="system")
    logger.info(f"📊 System WebSocket client connected: {client_id}")
    
    try:
        while True:
            await asyncio.sleep(1)  # Keep connection alive
    except WebSocketDisconnect:
        logger.info(f"📊 System WebSocket client disconnected: {client_id}")
    finally:
        await ws_manager.disconnect(client_id)


# Include API routes
app.include_router(api_router, prefix="/api/v1", tags=["api"])

# Serve static files for frontend (when built)
frontend_dist_path = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_dist_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dist_path)), name="static")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "connected_clients": len(ws_manager.active_connections),
        "active_subscriptions": len(ws_manager.subscriptions)
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info",
        access_log=True
    )
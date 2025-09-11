# Insider Trading Detection Dashboard

Modern web-based dashboard for real-time monitoring and analysis of the Polymarket insider trading detection bot.

## 🏗️ Architecture

The dashboard uses a modern web architecture with:
- **Backend**: FastAPI with WebSocket support for real-time communication
- **Frontend**: React/Vue.js (to be implemented in subtask 5.2)
- **Real-time Communication**: WebSocket channels for live data streaming
- **API**: RESTful API for data queries and configuration management

## 📁 Project Structure

```
dashboard/
├── backend/                    # FastAPI backend server
│   ├── main.py                # FastAPI application and WebSocket endpoints
│   ├── websocket_manager.py   # WebSocket connection and data streaming management
│   ├── api_routes.py          # REST API endpoints
│   ├── config_manager.py      # Configuration loading and validation
│   ├── run_dashboard.py       # Server startup script
│   ├── test_backend.py        # Backend component tests
│   └── __init__.py            # Package initialization
├── frontend/                  # Frontend application (to be implemented)
└── README.md                  # This file
```

## ✅ Completed Features (Subtask 5.1)

### FastAPI Backend Infrastructure
- **FastAPI Application**: Modern async web framework with automatic API documentation
- **WebSocket Support**: Real-time bidirectional communication with multiple channels
- **CORS Configuration**: Proper cross-origin setup for frontend integration
- **Health Monitoring**: Built-in health check endpoints

### Real-time WebSocket System
- **Multi-channel Subscriptions**: Clients can subscribe to specific data channels:
  - `alerts` - New alert notifications
  - `markets` - Market data updates
  - `anomaly_scores` - Anomaly score updates
  - `system_health` - System health monitoring
  - `wallet_coordination` - Wallet coordination tracking
  - `cross_market_correlation` - Cross-market analysis
  - `wash_trading` - Wash trading pattern detection
  - `historical_baseline` - Historical baseline analysis

### REST API Endpoints
- **Alert Management**: `/api/v1/alerts` - Alert history with filtering and pagination
- **Performance Metrics**: `/api/v1/performance` - Bot performance statistics  
- **Market Data**: `/api/v1/markets` - Current market monitoring status
- **Anomaly Scores**: `/api/v1/anomaly-scores` - Current anomaly scores and thresholds
- **Configuration**: `/api/v1/config` - Bot configuration management
- **System Health**: `/api/v1/system/health` - System monitoring and diagnostics
- **Logs**: `/api/v1/system/logs` - System log viewing with filtering
- **Cross-market Analysis**: `/api/v1/cross-market-correlation` - Correlation analysis
- **Wallet Coordination**: `/api/v1/wallet-coordination` - Coordination tracking data

### Configuration Management
- **Dynamic Loading**: Configuration loaded from `insider_config.json`
- **Validation**: Comprehensive configuration validation with error reporting
- **Hot Reload**: Configuration changes detected and reloaded automatically
- **Default Values**: Sensible defaults for all configuration options

### Advanced Features
- **Connection Management**: Automatic client reconnection and cleanup
- **Data Streaming**: Background tasks for real-time data streaming
- **Error Handling**: Comprehensive error handling with logging
- **Type Safety**: Pydantic models for request/response validation

## 🚀 Running the Backend

### Prerequisites
- Python 3.8+
- Dependencies installed: `pip install -r requirements.txt`

### Start the Server
```bash
# From project root
cd dashboard/backend
python run_dashboard.py

# Or directly with uvicorn
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

### Access Points
- **Dashboard**: http://localhost:8000
- **API Documentation**: http://localhost:8000/api/docs
- **WebSocket**: ws://localhost:8000/ws
- **Health Check**: http://localhost:8000/health

### Testing
```bash
cd dashboard/backend
python test_backend.py
```

## 🔌 WebSocket Usage

### Connection
```javascript
const ws = new WebSocket('ws://localhost:8000/ws');

// Subscribe to alerts
ws.send(JSON.stringify({
    type: 'subscribe',
    channels: ['alerts', 'anomaly_scores']
}));
```

### Message Types
- **welcome** - Connection established with client ID
- **market_data** - Real-time market updates
- **anomaly_scores** - Anomaly score updates  
- **system_health** - System health status
- **new_alert** - New alert notifications

## 🎯 Next Steps

The following subtasks will build upon this backend foundation:

- **5.2**: Design responsive frontend framework with React/Vue
- **5.3**: Implement real-time market monitoring views with charts
- **5.4**: Create alert history and filtering interface
- **5.5**: Build performance metrics and statistics pages
- **5.6**: Add configuration management UI for bot settings
- **5.7**: Build advanced anomaly score visualization system
- **5.8**: Implement cross-market correlation analysis dashboard
- **5.9**: Create wallet coordination tracking and timeline visualization
- **5.10**: Build wash trading pattern detection visualization
- **5.11**: Implement historical baseline analysis visualization
- **5.12**: Build advanced configuration editor for granular detection parameters
- **5.13**: Implement system health monitoring and log viewer
- **5.14**: Create cross-detection algorithm correlation dashboard

## 🔧 Configuration

The backend loads configuration from the main bot's `insider_config.json` file with the following dashboard-specific settings:

```json
{
  "dashboard": {
    "host": "127.0.0.1",
    "port": 8000,
    "debug": true,
    "cors_origins": ["http://localhost:3000"],
    "websocket_ping_interval": 30,
    "max_clients": 100
  }
}
```

## 🧪 Development Notes

- The backend currently uses mock data for development
- Real bot integration will be added as subtasks are completed
- All endpoints are documented with OpenAPI/Swagger
- WebSocket connections are managed efficiently with automatic cleanup
- Configuration validation ensures system stability

---

**Status**: ✅ Subtask 5.1 Complete - Backend infrastructure ready for frontend integration
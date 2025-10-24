# Usage Examples and Command Reference

This guide provides comprehensive examples of how to use the Polymarket Insider Trading Detection Bot in various scenarios and configurations.

> **📖 Documentation**: [README](README.md) • [Configuration Guide](CONFIGURATION.md) • [Troubleshooting](TROUBLESHOOTING.md)

## 📑 Table of Contents

- [🚀 Basic Usage](#-basic-usage)
- [💻 Interactive Usage Examples](#-interactive-usage-examples)
- [🎛️ Configuration-Based Usage Patterns](#️-configuration-based-usage-patterns)
- [🛠️ Debug and Development Usage](#️-debug-and-development-usage)
- [📝 Utility Scripts](#-utility-scripts)
- [🔍 Output Analysis](#-output-analysis)
- [🔄 Runtime Management](#-runtime-management)
- [⚡ Performance Optimization](#-performance-optimization)

## 🚀 Basic Usage

### Standard Startup
```bash
# Run with default configuration
python main.py

# Run in the background (Linux/Mac)
nohup python main.py > bot.log 2>&1 &

# Run with Python virtual environment
source insider-env/bin/activate
python main.py
```

### Using Custom Configuration
```bash
# Currently, configuration is loaded from insider_config.json
# To use a different config, copy and modify:
cp insider_config.json my_custom_config.json
# Edit my_custom_config.json as needed
# Then modify main.py to load your config file
```

> ⚙️ **Need help with configuration?** See the [Configuration Guide](CONFIGURATION.md) for complete parameter reference and examples.

## 💻 Interactive Usage Examples

### Monitoring Startup Sequence
```bash
$ python main.py

================================================================================
🚀 POLYMARKET INSIDER TRADING DETECTION BOT
📊 Modular WebSocket + Data API Architecture
================================================================================

⚙️  CONFIGURATION SUMMARY
────────────────────────────────────────
  📊 Markets: 50 max, $1,000 min volume
  🔍 Detection: 3.0x volume spike, $10,000 whale threshold
  🔔 Alerts: MEDIUM severity, Discord ❌
  🌐 Mode: 🟢 Live Trading
  🔐 Auth: ❌ No CLOB API

2024-09-10 15:30:01 - market_monitor - INFO - 🔍 Starting market discovery...
2024-09-10 15:30:02 - market_monitor - INFO - 📊 Found 47 active markets above volume threshold
2024-09-10 15:30:02 - websocket_client - INFO - 🌐 WebSocket connected successfully
2024-09-10 15:30:02 - market_monitor - INFO - ✅ Monitoring started - Press Ctrl+C to stop
```

### Sample Detection Output
```bash
2024-09-10 15:35:15 - volume_detector - WARNING - 🚨 VOLUME SPIKE DETECTED
  Market: 2024 Presidential Election Winner
  Volume: $45,230 (4.2x above baseline)
  Z-Score: 3.8 (HIGH significance)
  Severity: HIGH

2024-09-10 15:36:42 - whale_detector - WARNING - 🐋 WHALE ACTIVITY DETECTED
  Market: Fed Rate Decision - September
  Trade Size: $18,500
  Wallet: 0x742d35Cc6554C418BBF4...
  Price Impact: +2.3%
  Severity: MEDIUM

2024-09-10 15:38:20 - coordination_detector - CRITICAL - ⚠️ COORDINATED TRADING DETECTED
  Market: Tesla Q3 Earnings Beat
  Coordinated Wallets: 7
  Total Volume: $127,400
  Time Window: 25 seconds
  Directional Bias: 89% (BUY)
  Severity: CRITICAL
```

### Graceful Shutdown
```bash
^C
2024-09-10 16:15:33 - main - INFO - 🛑 Received shutdown signal
2024-09-10 16:15:33 - websocket_client - INFO - 🔌 WebSocket disconnected
2024-09-10 16:15:33 - market_monitor - INFO - 🛑 Stopping monitoring...
2024-09-10 16:15:33 - main - INFO - 👋 Bot shutdown complete
```

## 🎛️ Configuration-Based Usage Patterns

### Conservative Monitoring (Fewer Alerts)
```json
{
  "detection": {
    "volume_thresholds": {
      "volume_spike_multiplier": 5.0,
      "z_score_threshold": 4.0
    },
    "whale_thresholds": {
      "whale_threshold_usd": 25000
    }
  },
  "alerts": {
    "min_severity": "HIGH"
  }
}
```

Expected behavior:
- Only major volume spikes (5x+ above average)
- Only large whale trades ($25k+)
- Only HIGH and CRITICAL alerts shown

### High-Frequency Monitoring
```json
{
  "monitoring": {
    "check_interval": 15,
    "analysis_interval": 15,
    "max_markets": 25
  },
  "detection": {
    "volume_thresholds": {
      "volume_spike_multiplier": 2.0
    }
  },
  "debug": {
    "activity_report_interval": 10
  }
}
```

Expected behavior:
- Checks every 15 seconds
- More sensitive detection (2x volume spikes)
- Faster activity reports

### Specific Markets Only
```json
{
  "monitoring": {
    "markets": [
      "0x1234567890abcdef...",
      "0xabcdef1234567890...",
      "0x9876543210fedcba..."
    ],
    "max_markets": 3
  }
}
```

Expected behavior:
- Monitors only specified market IDs
- No automatic market discovery
- Focused monitoring on selected markets

## 🛠️ Debug and Development Usage

### Debug Mode Operation
```json
{
  "debug": {
    "debug_mode": true,
    "show_normal_activity": true,
    "verbose_analysis": true,
    "show_trade_samples": true
  }
}
```

Sample debug output:
```bash
2024-09-10 15:40:12 - volume_detector - DEBUG - 📊 Normal Activity
  Market: Bitcoin Price Above $45k
  Current Volume: $2,340 (0.8x baseline)
  Z-Score: -0.3 (normal range)

2024-09-10 15:40:12 - whale_detector - DEBUG - 🔍 Trade Sample
  Size: $3,200, Price: 0.67, Side: BUY
  Wallet: 0x123...abc (known trader)

2024-09-10 15:40:12 - market_monitor - DEBUG - 📈 Analysis Summary
  Active Markets: 47
  Total Volume (1h): $1,247,892
  Alerts Generated: 3
  WebSocket Status: Connected
```

### Simulation Mode
```json
{
  "api": {
    "simulation_mode": true,
    "websocket_enabled": false
  }
}
```

Use for:
- Testing configuration changes
- Development work
- Understanding detection algorithms
- Avoiding API rate limits

## 📝 Utility Scripts

### Market Discovery Test
```bash
# Test market discovery without full monitoring
python -c "
from data_sources.data_api_client import DataAPIClient
client = DataAPIClient()
markets = client.get_active_markets()
print(f'Found {len(markets)} markets')
for market in markets[:5]:
    print(f'  {market[\"question\"]}: ${market[\"volume\"]:,.0f}')
"
```

### Configuration Validation
```bash
# Validate configuration file syntax
python -c "
import json
with open('insider_config.json') as f:
    config = json.load(f)
print('✅ Configuration file is valid JSON')
print(f'Markets to monitor: {len(config[\"monitoring\"][\"markets\"])}')
print(f'Volume threshold: ${config[\"monitoring\"][\"volume_threshold\"]:,}')
"
```

## 🔍 Output Analysis

### Log File Analysis
```bash
# View recent alerts only
grep "DETECTED\|WARNING\|CRITICAL" insider_bot.log | tail -20

# Count alerts by severity
grep -c "HIGH" insider_bot.log
grep -c "MEDIUM" insider_bot.log  
grep -c "CRITICAL" insider_bot.log

# Monitor log file in real-time
tail -f insider_bot.log

# Find specific market activity
grep "Presidential Election" insider_bot.log
```

### Performance Monitoring
```bash
# Monitor system resource usage
top -p $(pgrep -f "python main.py")

# Check memory usage
ps aux | grep "python main.py"

# Monitor network connections
netstat -an | grep 443  # HTTPS connections
netstat -an | grep 8080 # WebSocket connections
```

## 🔄 Runtime Management

### Process Management
```bash
# Start in background with process management
python main.py &
BOT_PID=$!
echo $BOT_PID > bot.pid

# Stop the bot gracefully
kill -SIGINT $(cat bot.pid)

# Force stop if needed
kill -SIGKILL $(cat bot.pid)

# Check if bot is running
ps aux | grep "python main.py" | grep -v grep
```

### Log Rotation
```bash
# Rotate logs when they get large
mv insider_bot.log insider_bot.log.$(date +%Y%m%d)
touch insider_bot.log

# Compress old logs
gzip insider_bot.log.$(date -d "1 day ago" +%Y%m%d)
```

## 🐳 Docker Usage (Future Enhancement)

While not currently implemented, here's how the bot could be containerized:

```dockerfile
# Example Dockerfile structure
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

```bash
# Example Docker commands
docker build -t insider-bot .
docker run -d --name insider-bot \
  -v $(pwd)/insider_config.json:/app/insider_config.json \
  -v $(pwd)/logs:/app/logs \
  insider-bot
```

## 🌐 API Integration Examples

### Discord Webhook Setup
```bash
# Test Discord webhook
curl -X POST YOUR_DISCORD_WEBHOOK_URL \
  -H "Content-Type: application/json" \
  -d '{
    "content": "🤖 Insider Bot Test Alert",
    "embeds": [{
      "title": "Test Alert",
      "description": "Bot is configured correctly",
      "color": 65280
    }]
  }'
```

### Environment Variables
```bash
# Example .env file usage
export POLYMARKET_API_KEY="your_api_key"
export DISCORD_WEBHOOK_URL="your_webhook_url"
python main.py
```

## ⚡ Performance Optimization

### High-Performance Configuration
```json
{
  "monitoring": {
    "max_markets": 20,
    "check_interval": 45,
    "analysis_interval": 30
  },
  "debug": {
    "debug_mode": false,
    "show_normal_activity": false,
    "verbose_analysis": false
  }
}
```

### Resource-Constrained Settings
```json
{
  "monitoring": {
    "max_markets": 10,
    "check_interval": 120,
    "volume_threshold": 5000
  },
  "api": {
    "websocket_enabled": false
  }
}
```

## 🔧 Troubleshooting Commands

### Connection Testing
```bash
# Test Polymarket API connectivity
curl -s "https://data-api.polymarket.com/markets" | head -100

# Test WebSocket endpoint (requires wscat)
wscat -c "wss://ws-subscriptions-clob.polymarket.com/ws/market"
```

### Configuration Debugging
```bash
# Pretty-print current configuration
python -c "
import json
with open('insider_config.json') as f:
    config = json.load(f)
print(json.dumps(config, indent=2))
"
```

## 📊 Data Export Examples

### Export Trading Data
```python
# Example script to export detected trades
import json
from datetime import datetime

def export_alerts(log_file="insider_bot.log"):
    alerts = []
    with open(log_file) as f:
        for line in f:
            if "DETECTED" in line:
                alerts.append({
                    "timestamp": line.split(" - ")[0],
                    "type": line.split(" - ")[2],
                    "message": line.split(" - ")[3]
                })
    
    with open(f"alerts_{datetime.now().strftime('%Y%m%d')}.json", "w") as f:
        json.dump(alerts, f, indent=2)
    
    print(f"Exported {len(alerts)} alerts")

export_alerts()
```

This usage guide covers the current functionality and provides examples for various operational scenarios. As the bot evolves, additional command-line options and features can be added to enhance usability.
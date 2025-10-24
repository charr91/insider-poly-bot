# Polymarket Insider Trading Detection Bot

🚀 **Real-time detection of unusual trading patterns and potential insider activity on Polymarket**

A sophisticated bot that monitors Polymarket trading activity to identify potential insider trading through advanced pattern detection algorithms including volume spikes, whale activity, price movements, and coordinated trading behavior.

## 📚 Documentation

- **[Configuration Guide](CONFIGURATION.md)** - Complete setup and parameter reference
- **[Usage Examples](USAGE.md)** - Commands and operational scenarios
- **[Testing Guide](TESTING.md)** - Testing documentation and development guidelines
- **[Architecture Guide](ARCHITECTURE.md)** - System design, database patterns, and technical details
- **[Troubleshooting](TROUBLESHOOTING.md)** - Common issues and solutions
- **[Deployment Guide](DEPLOYMENT.md)** - Docker setup and VPS deployment

## ✨ Key Features

- **📊 Real-time Market Monitoring**: Live WebSocket connection for instant trade data
- **🔍 Multi-Algorithm Detection**: Volume spikes, whale detection, price movement analysis, and coordination detection
- **⚡ Advanced Pattern Recognition**: Statistical analysis using Z-scores, volatility measurements, and momentum indicators
- **🔔 Smart Alerting**: Actionable trading recommendations with Discord & Telegram support
- **🎯 Intelligent Recommendations**: Context-aware buy/sell/monitor recommendations based on signal strength and confidence
- **🐋 Whale Address Tracking**: Automatic database storage of whale wallet addresses from alerts for analysis
- **🔗 Market Integration**: Direct links to Polymarket events and Polygonscan transactions in alerts
- **🌐 Modular Architecture**: Separate data sources, detection algorithms, and alert systems
- **📈 Comprehensive Analytics**: Detailed logging and activity reporting
- **⚙️ Flexible Configuration**: Extensive customization through JSON configuration

## 🛠️ Prerequisites

- **Python 3.8+** (Python 3.10+ recommended)
- **API Access**: Polymarket CLOB API access (optional for enhanced features)
- **Discord Webhook** (optional - for Discord alerts)
- **Telegram Bot** (optional - for Telegram alerts)
  - Create bot via [@BotFather](https://t.me/BotFather) on Telegram
  - Get your chat ID by messaging the bot and visiting: `https://api.telegram.org/bot<YourBOTToken>/getUpdates`

## 📦 Installation

### 1. Clone the Repository
```bash
git clone <repository-url>
cd insider-poly-bot
```

### 2. Create Virtual Environment
```bash
python -m venv insider-env
source insider-env/bin/activate  # On Windows: insider-env\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Environment Setup
```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your API keys (optional)
nano .env
```

### 5. Configuration Setup
```bash
# The bot comes with a default configuration
# Copy and customize as needed
cp insider_config.json my_config.json
```

> 📖 **For detailed configuration options, see the [Configuration Guide](CONFIGURATION.md)**

## 🚀 Quick Start

### Basic Usage
```bash
# Start monitoring with default configuration
python main.py

# Use custom configuration file
python main.py --config my_config.json
```

> 💻 **For more usage examples and operational guidance, see the [Usage Guide](USAGE.md)**

### Example Output
```
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

[INFO] Starting market discovery...
[INFO] Found 47 active markets
[INFO] WebSocket connected successfully
[INFO] Monitoring started - Press Ctrl+C to stop
```

## 📁 Project Structure

```
insider-poly-bot/
├── main.py                    # Entry point and orchestrator
├── market_monitor.py          # Main monitoring coordination
├── insider_config.json        # Default configuration
├── requirements.txt           # Python dependencies
├── 
├── data_sources/             # Data collection modules
│   ├── data_api_client.py    # Polymarket API client
│   └── websocket_client.py   # Real-time WebSocket client
│
├── detection/                # Detection algorithms
│   ├── volume_detector.py    # Volume spike detection
│   ├── whale_detector.py     # Large trade detection  
│   ├── price_detector.py     # Price movement analysis
│   └── coordination_detector.py # Coordinated trading detection
│
├── alerts/                   # Alert and notification system
│   └── alert_manager.py      # Discord/notification management
│
├── config/                   # Configuration management
│   └── settings.py           # Settings parser and validation
│
└── utils/                    # Utility functions
```

## 🔧 Core Components

### Market Monitor (`market_monitor.py`)
- **Orchestrates** all data sources and detection algorithms
- **Manages** market discovery and WebSocket connections
- **Coordinates** detection analysis and alert generation

### Data Sources
- **Data API Client**: Fetches historical and current market data
- **WebSocket Client**: Real-time trade stream processing

### Detection Algorithms
- **Volume Detector**: Identifies unusual volume spikes using statistical analysis
- **Whale Detector**: Detects large trades and potential market manipulation
- **Price Detector**: Analyzes rapid price movements and volatility
- **Coordination Detector**: Identifies patterns of coordinated trading activity

### Alert System
- **Configurable severity levels** (LOW, MEDIUM, HIGH, CRITICAL)
- **Discord webhook integration**
- **Rate limiting** to prevent spam

## 📊 Detection Capabilities

- **Volume Spike Detection** - Statistical Z-score analysis identifies trades 3x+ above average
- **Whale Detection** - Tracks large trades ($10K+) and coordinated whale activity
- **Price Movement Analysis** - Detects rapid price changes (15%+) and volatility spikes
- **Coordination Detection** - Identifies synchronized trading patterns across multiple wallets

> 📖 **For detailed detection parameters and scoring systems, see [Architecture Guide](ARCHITECTURE.md)**

## 🔐 Security Features

- **No Private Key Storage**: Read-only market monitoring
- **Configurable Rate Limits**: Prevents API abuse
- **Environment Variable Security**: Sensitive data in .env files
- **Comprehensive Logging**: Audit trail for all activities

## 📝 Logs and Output

### Log Files
- **`insider_bot.log`**: Comprehensive application logs
- **Console Output**: Real-time monitoring status with colored output

### Activity Reporting
- **Periodic Market Summaries**: Regular status updates
- **Detection Alerts**: Immediate notifications for suspicious activity
- **Debug Mode**: Detailed analysis output for development

## 🤝 Contributing

This bot is designed for educational and research purposes. When contributing:

1. Follow the modular architecture patterns
2. Add comprehensive logging for new features
3. Update configuration documentation for new parameters
4. Include tests for detection algorithms (see [Testing Guide](TESTING.md))
5. Ensure all tests pass: `python -m pytest`

> 🔧 **Having issues? Check the [Troubleshooting Guide](TROUBLESHOOTING.md) for solutions to common problems.**

## ⚠️ Disclaimer

This bot is for **educational and research purposes only**. It is designed to detect patterns that *may* indicate insider trading but should not be considered definitive proof. Always verify findings through additional research and comply with all applicable laws and regulations.

## 📄 License

[Add your license information here]

---

## 💾 Database & Persistence

The bot now includes a robust database persistence layer for tracking alerts, whale addresses, and alert outcomes.

### Database Features

- **Alert Storage**: All alerts are automatically saved to SQLite database
- **Whale Tracking**: Tracks whale addresses with automatic market maker detection
- **Outcome Correlation**: Tracks alert outcomes (price movements at 1h, 4h, 24h intervals)
- **Performance Analytics**: Calculate win rates and profitability of alerts

### Market Maker Detection

Automatically identifies and filters market makers using heuristic scoring (frequency, balance, diversity, consistency). Addresses with score ≥70 are classified as market makers and excluded from whale alerts.

> 📖 **For detailed scoring algorithm, see [Architecture Guide](ARCHITECTURE.md#market-maker-detection)**

**Database Tables**: alerts, alert_outcomes, whale_addresses, whale_alert_associations

> 📖 **For complete schema details, see [Architecture Guide](ARCHITECTURE.md#database-schema)**

## 🖥️ CLI Usage

The bot includes a comprehensive CLI for querying tracked data.

### Installation

```bash
# Install the package
pip install -e .

# Verify installation
insider-bot --help
```

### Running the Bot

```bash
# Start the monitoring bot
insider-bot run

# Use custom configuration
insider-bot run --config my_config.json

# Use custom database path
insider-bot --db-path /path/to/data.db run
```

### Whale Commands

```bash
# List all tracked whales (excluding market makers)
insider-bot whales list --limit 20 --exclude-mm

# Show specific whale details
insider-bot whales show 0x1234567890abcdef...

# Quick top whales summary
insider-bot whales top --limit 10

# Include market makers
insider-bot whales list --limit 50 --no-exclude-mm

# Filter by minimum volume
insider-bot whales list --min-volume 50000
```

### Alert Commands

```bash
# Test alert system connections (sends test messages)
insider-bot alerts test

# Show recent alerts (last 24 hours)
insider-bot alerts recent --hours 24

# Filter by severity
insider-bot alerts recent --severity HIGH

# Show specific alert details
insider-bot alerts show 123

# Get all alerts for a market
insider-bot alerts by-market <market-id>
```

#### Testing Alert Connections

Test your Discord and Telegram configurations by sending actual test messages:

```bash
insider-bot alerts test                      # Test with default config
insider-bot alerts test --config my_config.json  # Test with custom config
```

**Prerequisites**: Set `DISCORD_WEBHOOK`, `TELEGRAM_BOT_TOKEN`, and `TELEGRAM_CHAT_ID` in `.env` file.

> 📖 **For detailed alert setup, see [Configuration Guide](CONFIGURATION.md#alert-configuration)**

### Statistics Commands

```bash
# View alert performance statistics
insider-bot stats performance --days 30

# System summary
insider-bot stats summary

# Whale statistics
insider-bot stats whales
```

### Database Management Commands

```bash
# Run database migrations (after code updates)
insider-bot db migrate --verify

# Check current database schema
insider-bot db check-schema
```

**When to use migrations:**
- After pulling new code from git
- When encountering "no such column" errors
- After upgrading to a new version

**Example:**
```bash
# After upgrading the bot
git pull
docker compose build
docker compose exec insider-poly-bot insider-bot db migrate --verify

# Check if migration was successful
docker compose exec insider-poly-bot insider-bot db check-schema
```

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md#database-issues) for database-related issues.

### Example CLI Session

```bash
# Check top whales
$ insider-bot whales top --limit 5
Top 5 Whales: 0x1a2b... ($125K, 45 trades), 0x9f8e... ($98.5K, 32 trades)...

# Check performance
$ insider-bot stats performance --days 7
Alert Performance (7d): 24 total, 16 profitable (66.7%), Avg: +3.45%

# View recent alerts
$ insider-bot alerts recent --severity HIGH --hours 12
2 HIGH alerts: Will Trump... (WHALE), Bitcoin to... (COORD)
```

> 💻 **For complete CLI documentation, see [Usage Guide](USAGE.md#cli-commands)**

## 🐳 Deployment

### Run with Docker

The bot runs in Docker for easy setup and 24/7 operation.

#### Quick Start

```bash
# Clone and configure
git clone <repository-url>
cd insider-poly-bot
cp .env.example .env
nano .env  # Add your API keys

# Start the bot
docker-compose up -d

# View logs
docker-compose logs -f
```

See **[DEPLOYMENT.md](DEPLOYMENT.md)** for complete setup instructions, monitoring, and troubleshooting.

For advanced VPS deployment with automated backups and monitoring, see [deployment/ADVANCED.md](deployment/ADVANCED.md).

---

**📖 Quick Reference**
- **Setup**: [Installation](#-installation) → [Configuration](CONFIGURATION.md) → [Quick Start](#-quick-start)
- **Deploy**: [Docker Setup](#-deployment) → [DEPLOYMENT.md](DEPLOYMENT.md)
- **Develop**: [Testing Guide](TESTING.md) → [Architecture](ARCHITECTURE.md)
- **Issues**: [Troubleshooting](TROUBLESHOOTING.md)
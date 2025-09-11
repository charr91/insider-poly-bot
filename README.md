# Polymarket Insider Trading Detection Bot

🚀 **Real-time detection of unusual trading patterns and potential insider activity on Polymarket**

A sophisticated bot that monitors Polymarket trading activity to identify potential insider trading through advanced pattern detection algorithms including volume spikes, whale activity, price movements, and coordinated trading behavior.

## 📚 Documentation

| Document | Description |
|----------|-------------|
| **[📖 Configuration Guide](CONFIGURATION.md)** | Complete reference for `insider_config.json` parameters and setup |
| **[💻 Usage Examples](USAGE.md)** | Detailed usage patterns, commands, and operational scenarios |
| **[🧪 Testing Guide](TESTING.md)** | Comprehensive testing documentation and development guidelines |
| **[🔧 Troubleshooting](TROUBLESHOOTING.md)** | Common issues, solutions, and FAQ for quick problem resolution |

> 💡 **Quick Links**: [Installation](#-installation) • [Quick Start](#-quick-start) • [Configuration](CONFIGURATION.md) • [Usage Examples](USAGE.md) • [Testing](TESTING.md) • [Troubleshooting](TROUBLESHOOTING.md)

## ✨ Key Features

- **📊 Real-time Market Monitoring**: Live WebSocket connection for instant trade data
- **🔍 Multi-Algorithm Detection**: Volume spikes, whale detection, price movement analysis, and coordination detection  
- **⚡ Advanced Pattern Recognition**: Statistical analysis using Z-scores, volatility measurements, and momentum indicators
- **🔔 Smart Alerting**: Configurable Discord notifications with severity levels
- **🌐 Modular Architecture**: Separate data sources, detection algorithms, and alert systems
- **📈 Comprehensive Analytics**: Detailed logging and activity reporting
- **⚙️ Flexible Configuration**: Extensive customization through JSON configuration

## 🛠️ Prerequisites

- **Python 3.8+** (Python 3.10+ recommended)
- **API Access**: Polymarket CLOB API access (optional for enhanced features)
- **Discord Webhook** (optional for alerts)

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

### Volume Analysis
- **Volume Spike Detection**: Identifies trades with volumes 3x+ above average
- **Z-Score Analysis**: Statistical significance testing for unusual activity
- **Historical Comparison**: Compares current activity to historical patterns

### Whale Detection  
- **Large Trade Identification**: Configurable USD thresholds for significant trades
- **Wallet Coordination**: Detects multiple large wallets acting in coordination
- **Market Impact Analysis**: Measures price impact of large trades

### Price Movement Analysis
- **Rapid Movement Detection**: Identifies sudden price changes (15%+ default)
- **Volatility Spike Detection**: Detects unusual volatility patterns
- **Momentum Analysis**: Measures sustained directional movement

### Coordination Detection
- **Multi-Wallet Analysis**: Identifies coordinated activity across wallets
- **Timing Analysis**: Detects synchronized trading patterns
- **Directional Bias**: Measures coordinated directional trading

## 📊 Technical Fields Reference

Understanding the key metrics and scores used in alert analysis:

### 🎯 Anomaly Score System
- **Calculation Method**: Z-score based (standard deviations above historical baseline)
- **Interpretation Scale**:
  - **0-2**: Normal market activity
  - **3-5**: Unusual but not necessarily suspicious activity
  - **6-8**: Potentially suspicious activity worth monitoring
  - **8+**: High anomaly requiring investigation
  - **10+**: Critical anomaly (very rare, immediate attention)

### 🎯 Confidence Scoring System
Multi-metric scoring system that combines various detection signals:

- **Single Anomaly Threshold**: `8.0` - High confidence required for single-metric alerts
- **Multi-Anomaly Threshold**: `10.0` - Combined metrics increase detection sensitivity
- **Critical Threshold**: `15.0` - Immediate attention required

**Confidence Bonuses Applied**:
- Historical Baseline Match: `+1.0`
- Coordination Detected: `+2.0` 
- Directional Bias: `+1.0`
- Multi-Trigger Events: `+2.0`
- Wash Trading Patterns: `+2.0`

### 🎯 Detection Parameters

**Volume Spike Detection**:
- **Multiplier**: `3.0x` above baseline average
- **Statistical Analysis**: Z-score threshold of `3.0`
- **Baseline Period**: 7-day historical data window

**Whale Activity Thresholds**:
- **Minimum Trade Size**: `$10,000` USD
- **Coordination Threshold**: `0.7` (70% directional alignment)
- **Minimum Whales**: `3+` for coordination detection

**Price Movement Analysis**:
- **Rapid Movement**: `15%` price change threshold
- **Volatility Multiplier**: `3.0x` above normal volatility
- **Momentum Threshold**: `0.8` for sustained directional movement

**Coordination Detection**:
- **Minimum Wallets**: `5` coordinated wallets required
- **Time Window**: `30` seconds for coordination analysis
- **Directional Bias**: `0.8` threshold for coordinated direction
- **Burst Intensity**: `3.0` multiplier for rapid coordination

### 🎯 Cross-Market Filtering
- **Analysis Window**: `15` minutes for cross-market correlation
- **Similar Market Threshold**: `3+` markets showing similar patterns
- **Volume Surge Detection**: `4+` markets with simultaneous volume increases
- **Filter Strategy**: Quality-based filtering using confidence scores and anomaly strength

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

## 📖 Documentation Navigation

| **Getting Started** | **Configuration** | **Operations** | **Development** | **Support** |
|:-------------------|:------------------|:---------------|:----------------|:------------|
| [📦 Installation](#-installation) | [⚙️ Configuration Guide](CONFIGURATION.md) | [💻 Usage Examples](USAGE.md) | [🧪 Testing Guide](TESTING.md) | [🔧 Troubleshooting](TROUBLESHOOTING.md) |
| [🚀 Quick Start](#-quick-start) | [🎛️ Tuning Guidelines](CONFIGURATION.md#-tuning-guidelines) | [🐳 Debug Mode](USAGE.md#-debug-and-development-usage) | [🏗️ Test Architecture](TESTING.md#-test-architecture) | [❓ FAQ](TROUBLESHOOTING.md#-frequently-asked-questions) |
| [📁 Project Structure](#-project-structure) | [🔐 Environment Setup](CONFIGURATION.md#-environment-variables) | [📊 Performance Tips](USAGE.md#-performance-optimization) | [🚀 Running Tests](TESTING.md#-running-tests) | [🚨 Emergency Procedures](TROUBLESHOOTING.md#-emergency-procedures) |

### Quick Reference
- **First time setup**: [Installation](#-installation) → [Configuration](CONFIGURATION.md) → [Quick Start](#-quick-start)
- **Customization**: [Configuration Guide](CONFIGURATION.md) → [Usage Examples](USAGE.md)
- **Development**: [Testing Guide](TESTING.md) → [Writing Tests](TESTING.md#-writing-new-tests)
- **Issues**: [Troubleshooting](TROUBLESHOOTING.md) → [FAQ](TROUBLESHOOTING.md#-frequently-asked-questions)
- **Advanced usage**: [Usage Guide](USAGE.md) → [Performance Optimization](USAGE.md#-performance-optimization)
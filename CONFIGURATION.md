# Configuration Guide for insider_config.json

This guide covers all configuration parameters for the Polymarket Insider Trading Detection Bot. The configuration is stored in `insider_config.json` and controls all aspects of monitoring, detection, and alerting.

> **📖 Documentation**: [README](README.md) • [Usage Examples](USAGE.md) • [Troubleshooting](TROUBLESHOOTING.md)

## 📑 Table of Contents

- [📋 Complete Configuration Reference](#-complete-configuration-reference)
- [🔧 Configuration Examples](#-configuration-examples)
- [🎯 Tuning Guidelines](#-tuning-guidelines)
- [🔐 Environment Variables](#-environment-variables)
- [⚠️ Important Notes](#️-important-notes)
- [🔄 Configuration Validation](#-configuration-validation)

## 📋 Complete Configuration Reference

### API Configuration (`api`)

Controls connection settings and operational mode.

```json
{
  "api": {
    "simulation_mode": false,
    "data_api_base_url": "https://data-api.polymarket.com",
    "websocket_url": "wss://ws-subscriptions-clob.polymarket.com/ws/market",
    "websocket_enabled": true
  }
}
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `simulation_mode` | boolean | `false` | If `true`, runs in simulation mode (no real API calls) |
| `data_api_base_url` | string | `"https://data-api.polymarket.com"` | Base URL for Polymarket data API |
| `websocket_url` | string | `"wss://ws-subscriptions-clob.polymarket.com/ws/market"` | WebSocket endpoint for real-time data |
| `websocket_enabled` | boolean | `true` | Enable/disable WebSocket connections |

### Monitoring Configuration (`monitoring`)

Controls which markets to monitor and how frequently.

```json
{
  "monitoring": {
    "markets": [],
    "volume_threshold": 1000,
    "max_markets": 50,
    "check_interval": 60,
    "sort_by_volume": true,
    "market_discovery_interval": 300,
    "analysis_interval": 60
  }
}
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `markets` | array | `[]` | Specific market IDs to monitor (empty = auto-discover) |
| `volume_threshold` | number | `1000` | Minimum USD volume for market inclusion |
| `max_markets` | number | `50` | Maximum number of markets to monitor simultaneously |
| `check_interval` | number | `60` | Seconds between market data checks |
| `sort_by_volume` | boolean | `true` | Prioritize high-volume markets for monitoring |
| `market_discovery_interval` | number | `300` | Seconds between market discovery scans |
| `analysis_interval` | number | `60` | Seconds between detection analysis runs |

### Detection Configuration (`detection`)

Core detection algorithm parameters organized by detection type.

#### Volume Detection (`volume_thresholds`)

```json
{
  "volume_thresholds": {
    "volume_spike_multiplier": 3.0,
    "z_score_threshold": 3.0
  }
}
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `volume_spike_multiplier` | number | `3.0` | Volume must be X times above average to trigger alert |
| `z_score_threshold` | number | `3.0` | Statistical significance threshold (standard deviations) |

#### Whale Detection (`whale_thresholds`)

```json
{
  "whale_thresholds": {
    "whale_threshold_usd": 10000,
    "coordination_threshold": 0.7,
    "min_whales_for_coordination": 3
  }
}
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `whale_threshold_usd` | number | `10000` | Minimum USD value to classify as "whale" trade |
| `coordination_threshold` | number | `0.7` | Correlation threshold for coordinated whale activity (0-1) |
| `min_whales_for_coordination` | number | `3` | Minimum number of whales needed to detect coordination |

#### Price Movement Detection (`price_thresholds`)

```json
{
  "price_thresholds": {
    "rapid_movement_pct": 15,
    "price_movement_std": 2.5,
    "volatility_spike_multiplier": 3.0,
    "momentum_threshold": 0.8
  }
}
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `rapid_movement_pct` | number | `15` | Percentage price change to trigger rapid movement alert |
| `price_movement_std` | number | `2.5` | Standard deviations for price movement detection |
| `volatility_spike_multiplier` | number | `3.0` | Volatility must be X times above average |
| `momentum_threshold` | number | `0.8` | Momentum indicator threshold for sustained movements |

#### Coordination Detection (`coordination_thresholds`)

```json
{
  "coordination_thresholds": {
    "min_coordinated_wallets": 5,
    "coordination_time_window": 30,
    "directional_bias_threshold": 0.8,
    "burst_intensity_threshold": 3.0
  }
}
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `min_coordinated_wallets` | number | `5` | Minimum wallets needed to detect coordination |
| `coordination_time_window` | number | `30` | Time window (seconds) for detecting coordinated activity |
| `directional_bias_threshold` | number | `0.8` | Threshold for directional coordination (0-1) |
| `burst_intensity_threshold` | number | `3.0` | Intensity multiplier for burst activity detection |

### Alert Configuration (`alerts`)

Controls notification settings and alert behavior.

```json
{
  "alerts": {
    "discord_webhook": "",
    "min_severity": "MEDIUM",
    "max_alerts_per_hour": 10
  }
}
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `discord_webhook` | string | `""` | Discord webhook URL for notifications (empty = disabled) |
| `min_severity` | string | `"MEDIUM"` | Minimum severity level: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` |
| `max_alerts_per_hour` | number | `10` | Rate limit for alerts to prevent spam |

### Debug Configuration (`debug`)

Development and troubleshooting options.

```json
{
  "debug": {
    "debug_mode": true,
    "show_normal_activity": true,
    "activity_report_interval": 30,
    "show_trade_samples": true,
    "verbose_analysis": true,
    "websocket_activity_logging": true
  }
}
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `debug_mode` | boolean | `true` | Enable detailed debug logging |
| `show_normal_activity` | boolean | `true` | Log normal trading activity (not just alerts) |
| `activity_report_interval` | number | `30` | Seconds between activity summary reports |
| `show_trade_samples` | boolean | `true` | Include sample trades in debug output |
| `verbose_analysis` | boolean | `true` | Show detailed analysis calculations |
| `websocket_activity_logging` | boolean | `true` | Log WebSocket connection activity |

## 🔧 Configuration Examples

### Conservative Detection (Fewer False Positives)
```json
{
  "detection": {
    "volume_thresholds": {
      "volume_spike_multiplier": 5.0,
      "z_score_threshold": 4.0
    },
    "whale_thresholds": {
      "whale_threshold_usd": 25000,
      "coordination_threshold": 0.8,
      "min_whales_for_coordination": 5
    },
    "price_thresholds": {
      "rapid_movement_pct": 25,
      "price_movement_std": 3.0,
      "volatility_spike_multiplier": 4.0,
      "momentum_threshold": 0.9
    }
  },
  "alerts": {
    "min_severity": "HIGH"
  }
}
```

### Aggressive Detection (More Sensitive)
```json
{
  "detection": {
    "volume_thresholds": {
      "volume_spike_multiplier": 2.0,
      "z_score_threshold": 2.0
    },
    "whale_thresholds": {
      "whale_threshold_usd": 5000,
      "coordination_threshold": 0.5,
      "min_whales_for_coordination": 2
    },
    "price_thresholds": {
      "rapid_movement_pct": 8,
      "price_movement_std": 1.5,
      "volatility_spike_multiplier": 2.0,
      "momentum_threshold": 0.6
    }
  },
  "alerts": {
    "min_severity": "LOW"
  }
}
```

### High-Volume Markets Only
```json
{
  "monitoring": {
    "volume_threshold": 50000,
    "max_markets": 20,
    "sort_by_volume": true
  }
}
```

### Development/Testing Configuration
```json
{
  "api": {
    "simulation_mode": true
  },
  "debug": {
    "debug_mode": true,
    "show_normal_activity": true,
    "activity_report_interval": 10,
    "verbose_analysis": true
  },
  "alerts": {
    "min_severity": "LOW",
    "max_alerts_per_hour": 100
  }
}
```

## 🎯 Tuning Guidelines

### For Different Market Conditions

**Bull Market (High Activity)**
- Increase `volume_spike_multiplier` to 4.0-5.0
- Increase `whale_threshold_usd` to $15,000-25,000
- Increase `rapid_movement_pct` to 20-30%

**Bear Market (Low Activity)**  
- Decrease `volume_spike_multiplier` to 2.0-2.5
- Decrease `whale_threshold_usd` to $5,000-7,500
- Decrease `rapid_movement_pct` to 10-15%

**High Volatility Periods**
- Increase `price_movement_std` to 3.0-4.0
- Increase `volatility_spike_multiplier` to 4.0-5.0
- Increase `min_severity` to reduce noise

### Performance Optimization

**High-Performance Setup**
```json
{
  "monitoring": {
    "max_markets": 25,
    "check_interval": 30,
    "analysis_interval": 30
  },
  "debug": {
    "debug_mode": false,
    "show_normal_activity": false,
    "verbose_analysis": false
  }
}
```

**Resource-Constrained Environment**
```json
{
  "monitoring": {
    "max_markets": 10,
    "check_interval": 120,
    "analysis_interval": 120,
    "volume_threshold": 10000
  },
  "api": {
    "websocket_enabled": false
  }
}
```

## 🔐 Environment Variables

Some sensitive configuration should be stored in `.env` file:

```bash
# Polymarket API (optional - for enhanced features)
POLYMARKET_API_KEY=your_api_key_here
POLYMARKET_SECRET=your_secret_here

# Discord Webhook (optional - for alerts)
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/your_webhook_url

# Additional API keys for enhanced features
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
EMAIL_API_KEY=your_email_service_api_key
```

## ⚠️ Important Notes

### Security Considerations
- **Never commit API keys** to version control
- **Use environment variables** for sensitive data
- **Review webhook URLs** before sharing configuration
- **Limit API rate limits** to prevent account suspension

### Performance Impact
- **Lower intervals = higher resource usage**
- **More markets = more memory usage**  
- **Debug mode = significant log file growth**
- **WebSocket = continuous network activity**

### Detection Accuracy
- **Lower thresholds = more false positives**
- **Higher thresholds = missed legitimate alerts**
- **Test configurations** in simulation mode first
- **Monitor alert volume** and adjust thresholds accordingly

## 🔄 Configuration Validation

The bot automatically validates configuration on startup and will report any issues:

```bash
python main.py --validate-config
```

Common validation errors:
- **Invalid threshold ranges** (negative values, impossible percentages)
- **Missing required fields**
- **Incompatible parameter combinations**
- **Invalid webhook URLs**

For configuration assistance, run the bot with `--config-help` for interactive guidance.

> 🔧 **Having configuration issues?** See the [Configuration Troubleshooting Section](TROUBLESHOOTING.md#configuration-issues) for common problems and solutions.
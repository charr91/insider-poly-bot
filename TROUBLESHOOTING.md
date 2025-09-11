# Troubleshooting Guide and FAQ

This guide covers common issues, solutions, and frequently asked questions for the Polymarket Insider Trading Detection Bot.

> **📖 Documentation**: [README](README.md) • [Configuration Guide](CONFIGURATION.md) • [Usage Examples](USAGE.md)

## 📑 Table of Contents

- [🔧 Common Issues and Solutions](#-common-issues-and-solutions)
  - [Installation Issues](#installation-issues)
  - [Configuration Issues](#configuration-issues)
  - [Connection Issues](#connection-issues)
  - [Performance Issues](#performance-issues)
  - [Detection Issues](#detection-issues)
  - [Runtime Issues](#runtime-issues)
- [📋 Frequently Asked Questions](#-frequently-asked-questions)
- [🚨 Emergency Procedures](#-emergency-procedures)
- [📞 Getting Help](#-getting-help)

## 🔧 Common Issues and Solutions

### Installation Issues

#### Issue: `pip install` fails with dependency conflicts
**Symptoms:**
```bash
ERROR: pip's dependency resolver does not currently consider all packages
conflict: package requires numpy>=1.26.0 but you have numpy==1.25.0
```

**Solutions:**
```bash
# Option 1: Create fresh virtual environment
rm -rf insider-env
python -m venv insider-env
source insider-env/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Option 2: Force upgrade dependencies
pip install --upgrade --force-reinstall -r requirements.txt

# Option 3: Install specific versions
pip install numpy==1.26.2 pandas==2.1.4 scipy==1.11.4
pip install -r requirements.txt
```

#### Issue: Python version incompatibility
**Symptoms:**
```bash
SyntaxError: invalid syntax (using Python 3.7 or older)
f-strings not supported
```

**Solutions:**
```bash
# Check Python version
python --version

# Install Python 3.8+ (Ubuntu/Debian)
sudo apt update
sudo apt install python3.10 python3.10-venv python3.10-pip

# Use specific Python version
python3.10 -m venv insider-env
```

#### Issue: Virtual environment activation fails
**Symptoms:**
```bash
bash: insider-env/bin/activate: No such file or directory
```

**Solutions:**
```bash
# Windows
insider-env\Scripts\activate.bat

# Windows PowerShell
insider-env\Scripts\Activate.ps1

# Linux/Mac
source insider-env/bin/activate

# If still failing, recreate environment
python -m venv insider-env --clear
```

### Configuration Issues

#### Issue: Bot starts but finds no markets
**Symptoms:**
```bash
Found 0 active markets above volume threshold
No markets to monitor, waiting...
```

**Solutions:**
```json
// Lower volume threshold in insider_config.json
{
  "monitoring": {
    "volume_threshold": 100,  // Reduced from 1000
    "max_markets": 50
  }
}
```

#### Issue: Invalid JSON configuration
**Symptoms:**
```bash
JSONDecodeError: Expecting ',' delimiter: line 15 column 5
```

**Solutions:**
```bash
# Validate JSON syntax
python -c "
import json
with open('insider_config.json') as f:
    config = json.load(f)
print('✅ Configuration is valid')
"

# Use online JSON validator: jsonlint.com
# Check for:
# - Missing commas
# - Trailing commas
# - Unmatched brackets
# - Unescaped quotes
```

#### Issue: Discord webhook not working
**Symptoms:**
```bash
Failed to send Discord alert: HTTP 404
Discord webhook test failed: Invalid webhook URL
```

**Solutions:**
```bash
# Test webhook manually
curl -X POST "YOUR_WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{"content": "Test message"}'

# Check webhook URL format
# Should be: https://discord.com/api/webhooks/ID/TOKEN

# Regenerate webhook if needed
# Discord Server Settings > Integrations > Webhooks
```

### Connection Issues

#### Issue: WebSocket connection fails
**Symptoms:**
```bash
Failed to establish WebSocket connection: ConnectionRefusedError
WebSocket disconnected, attempting reconnect...
```

**Solutions:**
```bash
# Test WebSocket endpoint manually
pip install websocket-client
python -c "
import websocket
ws = websocket.create_connection('wss://ws-subscriptions-clob.polymarket.com/ws/market')
print('✅ WebSocket connection successful')
ws.close()
"

# Disable WebSocket if problematic
{
  "api": {
    "websocket_enabled": false
  }
}

# Check firewall/proxy settings
# Corporate networks may block WebSocket connections
```

#### Issue: API connection timeout
**Symptoms:**
```bash
Error fetching markets: HTTPSConnectionPool timeout
RequestException: Connection timeout after 30 seconds
```

**Solutions:**
```bash
# Test API connectivity
curl -s "https://data-api.polymarket.com/markets" | head -100

# Check network connectivity
ping data-api.polymarket.com

# Configure proxy if needed (in environment)
export HTTP_PROXY=http://proxy.company.com:8080
export HTTPS_PROXY=http://proxy.company.com:8080
```

#### Issue: Rate limiting errors
**Symptoms:**
```bash
HTTP 429 Too Many Requests
API rate limit exceeded
```

**Solutions:**
```json
// Increase intervals to reduce API calls
{
  "monitoring": {
    "check_interval": 120,    // Increased from 60
    "analysis_interval": 120,  // Increased from 60
    "market_discovery_interval": 600  // Increased from 300
  }
}
```

### Performance Issues

#### Issue: High memory usage
**Symptoms:**
```bash
Bot uses 500MB+ RAM
System becomes slow
```

**Solutions:**
```json
// Reduce monitoring scope
{
  "monitoring": {
    "max_markets": 20,        // Reduced from 50
    "volume_threshold": 5000  // Increased to filter markets
  },
  "debug": {
    "debug_mode": false,      // Reduces logging
    "show_normal_activity": false,
    "verbose_analysis": false
  }
}
```

#### Issue: High CPU usage
**Symptoms:**
```bash
Python process uses 100% CPU
System fan runs constantly
```

**Solutions:**
```json
// Optimize processing intervals
{
  "monitoring": {
    "check_interval": 180,    // Longer intervals
    "analysis_interval": 180
  },
  "api": {
    "websocket_enabled": false  // Disable real-time processing
  }
}

// Add delays in code
await asyncio.sleep(0.1)  # Add small delays in loops
```

#### Issue: Large log files
**Symptoms:**
```bash
insider_bot.log grows to several GB
Disk space warning
```

**Solutions:**
```bash
# Rotate logs
mv insider_bot.log insider_bot.log.$(date +%Y%m%d)
touch insider_bot.log

# Configure log rotation (Linux)
sudo tee /etc/logrotate.d/insider-bot << EOF
/path/to/insider-poly-bot/insider_bot.log {
    daily
    missingok
    rotate 7
    compress
    notifempty
    create 644 user user
}
EOF

# Reduce logging verbosity
{
  "debug": {
    "debug_mode": false,
    "show_normal_activity": false,
    "verbose_analysis": false
  }
}
```

### Detection Issues

#### Issue: No alerts generated
**Symptoms:**
```bash
Bot runs for hours without detecting anything
All activity shows as "normal"
```

**Solutions:**
```json
// Make detection more sensitive
{
  "detection": {
    "volume_thresholds": {
      "volume_spike_multiplier": 2.0,  // Reduced from 3.0
      "z_score_threshold": 2.0         // Reduced from 3.0
    },
    "whale_thresholds": {
      "whale_threshold_usd": 5000      // Reduced from 10000
    }
  },
  "alerts": {
    "min_severity": "LOW"              // Show all alerts
  }
}
```

#### Issue: Too many false positive alerts
**Symptoms:**
```bash
Constant alerts for normal trading activity
Alert spam in Discord
```

**Solutions:**
```json
// Make detection more conservative
{
  "detection": {
    "volume_thresholds": {
      "volume_spike_multiplier": 5.0,  // Increased from 3.0
      "z_score_threshold": 4.0         // Increased from 3.0
    }
  },
  "alerts": {
    "min_severity": "HIGH",            // Only important alerts
    "max_alerts_per_hour": 5          // Rate limit
  }
}
```

### Runtime Issues

#### Issue: Bot stops unexpectedly
**Symptoms:**
```bash
Process exits without error message
Bot stops after few hours of operation
```

**Solutions:**
```bash
# Check system logs
journalctl -u your-service-name -f  # If running as service
dmesg | grep -i "killed"             # Check for OOM kills

# Run with error handling
python main.py 2>&1 | tee bot_output.log

# Add process monitoring
#!/bin/bash
while true; do
    if ! pgrep -f "python main.py" > /dev/null; then
        echo "Bot not running, restarting..."
        cd /path/to/insider-poly-bot
        source insider-env/bin/activate
        python main.py &
    fi
    sleep 60
done
```

#### Issue: Keyboard interrupt not working
**Symptoms:**
```bash
Ctrl+C doesn't stop the bot
Process becomes unresponsive
```

**Solutions:**
```bash
# Force kill process
ps aux | grep "python main.py"
kill -9 <PID>

# Or kill by name
pkill -f "python main.py"

# Find listening processes
netstat -tulpn | grep python
```

## 📋 Frequently Asked Questions

### General Questions

**Q: What markets does the bot monitor?**
A: By default, it auto-discovers the top 50 markets by volume (configurable). You can specify exact markets in the `markets` array in the configuration.

**Q: How accurate is the insider trading detection?**
A: The bot identifies statistical anomalies that *may* indicate insider trading. It's designed for research and educational purposes - patterns should be verified through additional analysis.

**Q: Can I run multiple instances of the bot?**
A: Yes, but be careful about API rate limits. Use different configuration files and consider monitoring different market segments.

**Q: Does the bot require API keys?**
A: No, the bot works with public Polymarket data. API keys are optional for enhanced features like Discord notifications.

### Technical Questions

**Q: What Python version is required?**
A: Python 3.8 or newer. Python 3.10+ is recommended for best performance and compatibility.

**Q: How much memory/CPU does the bot use?**
A: Typically 50-200MB RAM and 5-15% CPU on a modern system. Usage scales with the number of monitored markets.

**Q: Can I run this on a Raspberry Pi?**
A: Yes, but reduce the number of monitored markets and increase check intervals to accommodate limited resources.

**Q: Does the bot work with other prediction markets?**
A: Currently designed specifically for Polymarket. Adapting to other markets would require significant code changes.

### Configuration Questions

**Q: How do I monitor only specific markets?**
A: Add market condition IDs to the `markets` array in the configuration:
```json
{
  "monitoring": {
    "markets": ["0x1234...", "0x5678..."],
    "max_markets": 2
  }
}
```

**Q: What's the difference between volume spike multiplier and Z-score?**
A: Volume spike multiplier compares current volume to recent average (e.g., 3x higher). Z-score measures statistical significance (how unusual the volume is historically).

**Q: How often should I run market discovery?**
A: Default 300 seconds (5 minutes) is usually good. Increase for stable markets, decrease for rapidly changing markets.

**Q: Can I get notifications via email or Telegram?**
A: Currently only Discord webhooks are implemented. Email/Telegram would require code modifications.

### Troubleshooting Questions

**Q: Why does the bot say "No CLOB API" in the status?**
A: This indicates you don't have Polymarket CLOB API credentials configured. The bot works fine without them using public data.

**Q: The bot finds markets but no trades - why?**
A: Check if markets are actually active. Try lowering the volume threshold or check if WebSocket connections are working.

**Q: How can I test if my configuration is working?**
A: Set `debug_mode: true` and `show_normal_activity: true` to see all bot activity, not just alerts.

### Performance Questions

**Q: How can I make the bot faster?**
A: Reduce check intervals, monitor fewer markets, disable verbose logging, and enable WebSocket connections.

**Q: The bot seems slow to detect events - why?**
A: Check the `analysis_interval` setting. Lower values mean faster detection but higher resource usage.

**Q: Can I run the bot 24/7?**
A: Yes, designed for continuous operation. Consider implementing log rotation and process monitoring for production use.

## 🚨 Emergency Procedures

### Bot Completely Frozen
```bash
# Find and kill the process
ps aux | grep python | grep main.py
kill -9 <PID>

# Clear any lock files if they exist
rm -f *.lock *.pid

# Restart with fresh logs
mv insider_bot.log insider_bot.log.backup
python main.py
```

### Configuration Corrupted
```bash
# Restore from backup
cp insider_config.json.backup insider_config.json

# Or reset to defaults
cp insider_config.json.original insider_config.json

# Validate before starting
python -c "import json; json.load(open('insider_config.json'))"
```

### System Out of Resources
```bash
# Emergency resource-light configuration
{
  "monitoring": {
    "max_markets": 5,
    "check_interval": 300,
    "volume_threshold": 10000
  },
  "api": {
    "websocket_enabled": false
  },
  "debug": {
    "debug_mode": false,
    "show_normal_activity": false
  }
}
```

### Data Corruption Suspected
```bash
# Clear all cached data
rm -rf __pycache__/
rm -rf data_sources/__pycache__/
rm -rf detection/__pycache__/

# Restart with clean slate
python main.py
```

## 📞 Getting Help

### Log Information to Provide
When seeking help, include:
- Bot version/commit hash
- Operating system and Python version
- Complete error messages
- Configuration file (remove sensitive data)
- Steps to reproduce the issue

### Useful Diagnostic Commands
```bash
# System information
python --version
uname -a
df -h  # Disk space
free -h  # Memory usage

# Network connectivity
ping data-api.polymarket.com
curl -I https://data-api.polymarket.com/markets

# Bot-specific diagnostics
python -c "import requirements; print('Dependencies OK')"
python -c "from market_monitor import MarketMonitor; print('Import OK')"
```

### Support Resources
- Check GitHub issues for similar problems
- Review bot logs for error patterns
- Test with minimal configuration first
- Consider running in simulation mode for debugging

Remember: This bot is for educational purposes. Always verify any suspicious trading patterns through additional research and analysis.
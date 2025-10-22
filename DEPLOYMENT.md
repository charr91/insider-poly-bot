# Deployment Guide

Complete guide for running the Polymarket Insider Trading Detection Bot with Docker.

## Prerequisites

- **Docker** installed ([Get Docker](https://docs.docker.com/get-docker/))
- **Docker Compose** installed (usually included with Docker Desktop)
- Basic terminal/command line knowledge

**Note:** Use `docker-compose` (with hyphen) if you have the standalone version, or `docker compose` (with space) for the plugin version.

## Quick Start

### 1. Clone the Repository

```bash
git clone <your-repository-url>
cd insider-poly-bot
```

### 2. Configure Environment Variables

```bash
# Copy the example file
cp .env.example .env

# Edit with your credentials
nano .env  # or use your preferred editor
```

**Required variables:**
- `CLOB_API_KEY` - Your Polymarket API key
- `CLOB_API_SECRET` - Your Polymarket API secret
- `CLOB_API_PASSPHRASE` - Your Polymarket API passphrase
- `POLYGON_PRIVATE_KEY` - Your Polygon wallet private key
- `FUNDER_ADDRESS` - Your wallet address
- `DISCORD_WEBHOOK` - Discord webhook URL for alerts

See [CONFIGURATION.md](CONFIGURATION.md) for detailed configuration options.

### 3. Start the Bot

```bash
docker-compose up -d
```

The bot will:
- Build the Docker image (first time only)
- Start running in the background
- Begin monitoring Polymarket for unusual activity
- Send alerts to your Discord webhook

## Running the Bot

### Basic Commands

```bash
# Start the bot
docker-compose up -d

# Stop the bot
docker-compose down

# Restart the bot
docker-compose restart

# View logs (live)
docker-compose logs -f

# View last 50 lines of logs
docker-compose logs --tail=50

# Check bot status
docker-compose ps
```

### Check Bot Health

```bash
# View container status
docker-compose ps

# Check health status
docker inspect --format='{{.State.Health.Status}}' insider-poly-bot

# Monitor resource usage
docker stats insider-poly-bot
```

## Monitoring

### View Logs

```bash
# Follow logs in real-time
docker-compose logs -f

# View recent logs
docker-compose logs --tail=100

# Search logs for errors
docker-compose logs | grep -i error
```

### Database Queries

The bot stores alerts and whale activity in a SQLite database.

**Quick queries:**

```bash
# Count total alerts
docker-compose exec insider-poly-bot sqlite3 /app/insider_data.db \
  "SELECT COUNT(*) FROM alerts;"

# View recent alerts
docker-compose exec insider-poly-bot sqlite3 /app/insider_data.db \
  "SELECT id, alert_type, severity, timestamp FROM alerts ORDER BY timestamp DESC LIMIT 10;"

# View top whale addresses
docker-compose exec insider-poly-bot sqlite3 /app/insider_data.db \
  "SELECT address, total_volume_usd, trade_count FROM whale_addresses ORDER BY total_volume_usd DESC LIMIT 10;"
```

**Interactive database session:**

```bash
# Open SQLite shell
docker-compose exec insider-poly-bot sqlite3 /app/insider_data.db
```

Inside the SQLite shell:
```sql
-- Enable formatting
.headers on
.mode column

-- View recent alerts
SELECT * FROM alerts ORDER BY timestamp DESC LIMIT 10;

-- View whales (excluding market makers)
SELECT address, total_volume_usd, trade_count 
FROM whale_addresses 
WHERE is_market_maker = 0 
ORDER BY total_volume_usd DESC LIMIT 10;

-- Exit
.quit
```

### Discord Alerts

The bot automatically sends alerts to your configured Discord webhook when it detects:
- Unusual volume spikes
- Large whale trades
- Rapid price movements
- Coordinated trading activity

Check your Discord channel to see real-time alerts.

## Configuration

### Bot Settings

Edit `insider_config.json` to customize detection parameters:

```bash
nano insider_config.json
```

Key settings:
- `monitoring.max_markets` - Maximum markets to monitor (default: 50)
- `detection.whale_threshold_usd` - Minimum trade size to be considered a whale (default: $10,000)
- `alerts.min_severity` - Minimum alert severity to send (LOW, MEDIUM, HIGH, CRITICAL)

See [CONFIGURATION.md](CONFIGURATION.md) for all available options.

### Resource Limits

Adjust resource limits in `docker-compose.yml`:

```yaml
mem_limit: 1g      # Maximum memory
cpus: 1.0          # Maximum CPU cores
```

## Updating the Bot

### Pull Latest Changes

```bash
# Stop the bot
docker-compose down

# Pull latest code
git pull

# Rebuild and restart
docker-compose up -d --build
```

### Check for Updates

```bash
# View recent commits
git log --oneline -5

# Pull changes without rebuilding
git pull
docker-compose restart
```

## Troubleshooting

### Bot Won't Start

```bash
# Check logs for errors
docker-compose logs

# Verify environment file exists
cat .env

# Rebuild from scratch
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Database Access Issues

```bash
# Check if database file exists
docker-compose exec insider-poly-bot ls -la /app/insider_data.db

# Backup and reset database
docker-compose down
cp insider_data.db insider_data.db.backup
rm insider_data.db
docker-compose up -d
```

### Out of Disk Space

```bash
# Check disk usage
df -h

# Clean up Docker resources
docker system prune -a

# Remove old logs
docker-compose logs --tail=0
```

### Connection Issues

```bash
# Test API connectivity
docker-compose exec insider-poly-bot curl -I https://data-api.polymarket.com

# Check Discord webhook
curl -X POST -H "Content-Type: application/json" \
  -d '{"content":"Test message"}' \
  YOUR_DISCORD_WEBHOOK_URL
```

### Bot Consuming Too Much Memory

```bash
# Check resource usage
docker stats insider-poly-bot

# Reduce memory limit in docker-compose.yml
nano docker-compose.yml
# Change: mem_limit: 512M

# Restart bot
docker-compose up -d
```

## Data Persistence

The following data persists even when the container is recreated:
- **Database:** `insider_data.db` - All alerts and whale data
- **Logs:** `logs/` directory - Bot logs
- **Configuration:** `insider_config.json` - Bot settings

To backup your data:

```bash
# Backup database
cp insider_data.db insider_data.db.backup

# Backup with timestamp
cp insider_data.db "insider_data_$(date +%Y%m%d).db"
```

## Production Deployment

For running the bot 24/7 on a VPS:

1. Provision a VPS with Docker installed (1-2GB RAM recommended)
2. Clone this repository
3. Configure `.env` with production credentials
4. Run `docker-compose up -d`
5. Set up automated backups (see `deployment/backup.sh`)
6. Configure monitoring (see `deployment/health-check.sh`)

See [deployment/ADVANCED.md](deployment/ADVANCED.md) for detailed VPS deployment instructions.

## Getting Help

- **Configuration issues:** See [CONFIGURATION.md](CONFIGURATION.md)
- **Bot behavior:** See [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- **Usage examples:** See [USAGE.md](USAGE.md)
- **Testing:** See [TESTING.md](TESTING.md)

## Quick Reference

```bash
# Essential commands
docker-compose up -d              # Start bot
docker-compose down               # Stop bot
docker-compose logs -f            # View logs
docker-compose ps                 # Check status
docker-compose restart            # Restart bot
docker stats insider-poly-bot     # Resource usage

# Database queries
docker-compose exec insider-poly-bot sqlite3 /app/insider_data.db

# Update bot
git pull && docker-compose up -d --build
```

---

**Security Note:** Never commit your `.env` file or share your API keys. The `.env` file is excluded from git by default.

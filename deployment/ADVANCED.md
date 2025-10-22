# Deployment Guide: Polymarket Insider Trading Bot

Complete guide for deploying the bot to a VPS for 24/7 operation.

## Table of Contents

1. [VPS Requirements](#vps-requirements)
2. [VPS Provider Recommendations](#vps-provider-recommendations)
3. [Initial VPS Setup](#initial-vps-setup)
4. [Docker Installation](#docker-installation)
5. [Bot Deployment](#bot-deployment)
6. [Operational Management](#operational-management)
7. [Monitoring & Maintenance](#monitoring--maintenance)
8. [Troubleshooting](#troubleshooting)

---

## VPS Requirements

### Recommended Specs for This Bot

- **CPU**: 1-2 cores (burstable/shared acceptable)
- **RAM**: 1-2GB minimum
- **Storage**: 20-50GB SSD
- **Bandwidth**: 1-2TB/month
- **OS**: Ubuntu 22.04 LTS or Debian 12

### For Multiple Bots (2-3 crypto bots)

- **CPU**: 2-4 cores
- **RAM**: 4-8GB
- **Storage**: 50-80GB SSD
- **Bandwidth**: 2-4TB/month

---

## VPS Provider Recommendations

### Budget Options ($5-12/month)

| Provider | Plan | Price | CPU | RAM | Storage | Notes |
|----------|------|-------|-----|-----|---------|-------|
| **Hetzner** | CPX21 | €5.88 | 3 vCPU | 4GB | 80GB | **BEST VALUE** - Perfect for 2-3 bots |
| **Contabo** | VPS M | €6.99 | 4 vCPU | 8GB | 200GB | Great for multiple bots |
| **Vultr** | 4GB | $12 | 2 vCPU | 4GB | 80GB | Reliable, good support |
| **DigitalOcean** | Droplet 4GB | $24 | 2 vCPU | 4GB | 80GB | Premium but expensive |

**Recommendation**: Hetzner CPX21 offers the best value for running 2-3 lightweight crypto bots.

---

## Initial VPS Setup

### 1. Provision Your VPS

Choose your provider and create a VPS with Ubuntu 22.04 LTS.

### 2. Initial Server Configuration

```bash
# SSH into your VPS
ssh root@your-vps-ip

# Update system packages
apt update && apt upgrade -y

# Create a non-root user (recommended for security)
adduser botuser
usermod -aG sudo botuser

# Set up SSH key authentication (recommended)
mkdir -p /home/botuser/.ssh
cp ~/.ssh/authorized_keys /home/botuser/.ssh/
chown -R botuser:botuser /home/botuser/.ssh
chmod 700 /home/botuser/.ssh
chmod 600 /home/botuser/.ssh/authorized_keys

# Switch to new user
su - botuser
```

### 3. Configure Firewall (Optional but Recommended)

```bash
# Install and configure UFW
sudo apt install ufw -y
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw enable
```

---

## Docker Installation

### Install Docker & Docker Compose

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add your user to docker group (to run docker without sudo)
sudo usermod -aG docker $USER

# Install Docker Compose
sudo apt install docker-compose-plugin -y

# Log out and back in for group changes to take effect
exit
# SSH back in
ssh botuser@your-vps-ip

# Verify installation
docker --version
docker compose version
```

---

## Bot Deployment

### 1. Clone Repository

```bash
# Create directory for bots
mkdir -p ~/bots
cd ~/bots

# Clone the repository
git clone <your-repository-url> insider-poly-bot
cd insider-poly-bot
```

### 2. Configure Environment Variables

```bash
# Copy example environment file
cp .env.example .env

# Edit with your credentials
nano .env
```

**Required variables to set:**
- `CLOB_API_KEY`: Your Polymarket API key
- `CLOB_API_SECRET`: Your Polymarket API secret
- `CLOB_API_PASSPHRASE`: Your Polymarket API passphrase
- `POLYGON_PRIVATE_KEY`: Your Polygon wallet private key
- `FUNDER_ADDRESS`: Your wallet address
- `DISCORD_WEBHOOK`: Your Discord webhook URL for alerts

**Save and exit** (Ctrl+X, then Y, then Enter)

### 3. Configure Bot Settings (Optional)

```bash
# Edit config file if needed
nano insider_config.json
```

See [CONFIGURATION.md](../CONFIGURATION.md) for detailed configuration options.

### 4. Deploy with Docker Compose

```bash
# Build and start the bot
docker compose up -d

# Check logs
docker compose logs -f

# Stop watching logs: Ctrl+C
```

### 5. Verify Deployment

```bash
# Check if container is running
docker compose ps

# Should show:
# NAME                  STATUS
# insider-poly-bot      Up X minutes (healthy)

# View recent logs
docker compose logs --tail=50

# Follow logs in real-time
docker compose logs -f
```

---

## Operational Management

### Basic Commands

```bash
# Start the bot
docker compose up -d

# Stop the bot
docker compose down

# Restart the bot
docker compose restart

# View logs
docker compose logs -f

# View last 100 lines
docker compose logs --tail=100

# Update and rebuild
docker compose down
git pull
docker compose up -d --build
```

### Checking Bot Status

```bash
# Check container status
docker compose ps

# Check health status
docker inspect --format='{{.State.Health.Status}}' insider-poly-bot

# Check resource usage
docker stats insider-poly-bot
```

---

## Monitoring & Maintenance

### 1. Set Up Automated Backups

```bash
# Make backup script executable
chmod +x deployment/backup.sh

# Add to crontab for daily backups at 2 AM
crontab -e

# Add this line:
0 2 * * * /home/botuser/bots/insider-poly-bot/deployment/backup.sh >> /home/botuser/logs/backup.log 2>&1
```

### 2. Set Up Health Monitoring

```bash
# Make health check script executable
chmod +x deployment/health-check.sh

# Add to crontab for hourly checks
crontab -e

# Add this line:
0 * * * * /home/botuser/bots/insider-poly-bot/deployment/health-check.sh >> /home/botuser/logs/health-check.log 2>&1
```

### 3. Configure Log Rotation

Docker automatically rotates logs (configured in docker-compose.yml), but for host logs:

```bash
# Create log directory
mkdir -p ~/logs

# Install logrotate configuration
sudo cp deployment/docker-logrotate.conf /etc/logrotate.d/insider-bot

# Test logrotate
sudo logrotate -d /etc/logrotate.d/insider-bot
```

### 4. Viewing Database Activity

```bash
# Access the SQLite database
docker compose exec insider-poly-bot sqlite3 /app/insider_data.db

# Example queries:
.mode column
.headers on

-- View recent alerts
SELECT * FROM alerts ORDER BY timestamp DESC LIMIT 10;

-- View top whales
SELECT address, total_volume_usd, trade_count FROM whale_addresses ORDER BY total_volume_usd DESC LIMIT 10;

-- Exit
.quit
```

---

## Multiple Bots Setup

If you're running multiple crypto bots on the same VPS:

### 1. Organize Directories

```bash
~/bots/
├── insider-poly-bot/          # This bot
├── other-bot-1/               # Another bot
└── other-bot-2/               # Another bot
```

### 2. Assign Different Ports (if needed)

Edit each `docker-compose.yml` to use different port mappings if bots expose web interfaces.

### 3. Monitor All Bots

```bash
# View all running containers
docker ps

# View all bots' resource usage
docker stats

# View specific bot logs
docker compose -f ~/bots/insider-poly-bot/docker-compose.yml logs -f
```

---

## Troubleshooting

### Bot Won't Start

```bash
# Check logs for errors
docker compose logs

# Check if ports are in use
sudo netstat -tlnp

# Rebuild from scratch
docker compose down
docker compose build --no-cache
docker compose up -d
```

### WebSocket Connection Issues

```bash
# Check if WebSocket URL is reachable
curl -I https://ws-subscriptions-clob.polymarket.com

# Verify environment variables
docker compose config

# Check firewall isn't blocking outbound connections
sudo ufw status
```

### Database Issues

```bash
# Check database file permissions
ls -la insider_data.db

# Backup and reset database
docker compose down
cp insider_data.db insider_data.db.backup
rm insider_data.db
docker compose up -d
```

### Out of Disk Space

```bash
# Check disk usage
df -h

# Clean up Docker resources
docker system prune -a

# Remove old log files
find ~/logs -name "*.log" -mtime +30 -delete
```

### Bot Consuming Too Much Memory

```bash
# Check memory usage
docker stats insider-poly-bot

# Reduce memory limit in docker-compose.yml
nano docker-compose.yml
# Change: memory: 512M

# Restart
docker compose up -d
```

### Accessing Backups

```bash
# List backups
ls -lh ~/backups/

# Restore from backup
docker compose down
cp ~/backups/insider_data_YYYY-MM-DD.db insider_data.db
docker compose up -d
```

---

## Security Best Practices

1. **Never commit `.env` file** - It contains sensitive credentials
2. **Use SSH keys** instead of passwords for VPS access
3. **Keep system updated**: `sudo apt update && sudo apt upgrade -y`
4. **Monitor alerts** - Set up Discord/Telegram for bot alerts
5. **Regular backups** - Automated daily backups are critical
6. **Restrict SSH access** - Use firewall rules and fail2ban
7. **Use strong passwords** - For database and user accounts

---

## Quick Reference

### Common Commands

```bash
# Start bot
docker compose up -d

# View logs
docker compose logs -f

# Restart bot
docker compose restart

# Stop bot
docker compose down

# Update bot
git pull && docker compose up -d --build

# Check status
docker compose ps

# View resource usage
docker stats insider-poly-bot
```

### File Locations

- **Bot code**: `~/bots/insider-poly-bot/`
- **Database**: `~/bots/insider-poly-bot/insider_data.db`
- **Logs**: `~/bots/insider-poly-bot/logs/`
- **Backups**: `~/backups/`
- **Environment**: `~/bots/insider-poly-bot/.env`

---

## Support

For issues specific to the bot, see [TROUBLESHOOTING.md](../TROUBLESHOOTING.md)

For deployment-specific issues, check:
- Docker logs: `docker compose logs`
- System logs: `journalctl -xe`
- VPS provider documentation

---

**Note**: This guide assumes basic familiarity with Linux command line and SSH. If you need help with any step, consult your VPS provider's documentation or reach out for support.

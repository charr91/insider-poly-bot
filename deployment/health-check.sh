#!/bin/bash
#
# Health Check Script for Insider Poly Bot
# Monitors bot status and sends alerts if issues detected
#

set -euo pipefail

# Configuration
CONTAINER_NAME="insider-poly-bot"
DISCORD_WEBHOOK="${HEALTH_CHECK_DISCORD_WEBHOOK:-}"
MAX_MEMORY_PCT=90
MAX_CPU_PCT=80

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to send Discord alert
send_alert() {
    local title="$1"
    local message="$2"
    local severity="$3"  # success=3066993, warning=16776960, critical=15158332
    
    if [[ -n "${DISCORD_WEBHOOK}" ]]; then
        local color
        case "$severity" in
            success) color=3066993 ;;
            warning) color=16776960 ;;
            critical) color=15158332 ;;
            *) color=16776960 ;;
        esac
        
        curl -H "Content-Type: application/json" \
             -X POST \
             -d "{\"embeds\": [{\"title\": \"${title}\", \"description\": \"${message}\", \"color\": ${color}, \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%S.000Z)\"}]}" \
             "${DISCORD_WEBHOOK}" 2>/dev/null || true
    fi
}

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    echo -e "${RED}❌ Docker is not running${NC}"
    send_alert "🚨 Critical: Docker Not Running" "Docker daemon is not running on the VPS. Bot is offline." "critical"
    exit 1
fi

# Check if container exists
if ! docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo -e "${RED}❌ Container '${CONTAINER_NAME}' not found${NC}"
    send_alert "🚨 Critical: Container Missing" "Container ${CONTAINER_NAME} does not exist. Bot may need to be deployed." "critical"
    exit 1
fi

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo -e "${RED}❌ Container '${CONTAINER_NAME}' is not running${NC}"
    
    # Try to get container status
    STATUS=$(docker inspect --format='{{.State.Status}}' "${CONTAINER_NAME}" 2>/dev/null || echo "unknown")
    EXIT_CODE=$(docker inspect --format='{{.State.ExitCode}}' "${CONTAINER_NAME}" 2>/dev/null || echo "unknown")
    
    send_alert "🚨 Critical: Bot Offline" "Container is not running.\nStatus: ${STATUS}\nExit Code: ${EXIT_CODE}\n\nAttempting automatic restart..." "critical"
    
    # Attempt to restart
    echo "🔄 Attempting to restart container..."
    if docker start "${CONTAINER_NAME}" >/dev/null 2>&1; then
        sleep 5
        if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
            echo -e "${GREEN}✅ Container successfully restarted${NC}"
            send_alert "✅ Bot Restarted" "Container was restarted automatically and is now running." "success"
        else
            echo -e "${RED}❌ Container failed to stay running after restart${NC}"
            send_alert "🚨 Critical: Restart Failed" "Container restarted but immediately exited. Manual intervention required." "critical"
            exit 1
        fi
    else
        echo -e "${RED}❌ Failed to restart container${NC}"
        send_alert "🚨 Critical: Restart Failed" "Unable to restart container. Manual intervention required." "critical"
        exit 1
    fi
fi

# Check container health status
HEALTH_STATUS=$(docker inspect --format='{{.State.Health.Status}}' "${CONTAINER_NAME}" 2>/dev/null || echo "none")
if [[ "${HEALTH_STATUS}" != "healthy" ]] && [[ "${HEALTH_STATUS}" != "none" ]]; then
    echo -e "${YELLOW}⚠️  Container health check failing: ${HEALTH_STATUS}${NC}"
    send_alert "⚠️ Warning: Health Check Failing" "Container health status: ${HEALTH_STATUS}\nBot may be experiencing issues." "warning"
fi

# Get resource usage statistics
STATS=$(docker stats --no-stream --format "{{.CPUPerc}}|{{.MemPerc}}|{{.MemUsage}}" "${CONTAINER_NAME}" 2>/dev/null || echo "0%|0%|0B / 0B")
IFS='|' read -r CPU_PCT MEM_PCT MEM_USAGE <<< "$STATS"

# Remove % sign for comparison
CPU_NUM=$(echo "$CPU_PCT" | sed 's/%//' | cut -d'.' -f1)
MEM_NUM=$(echo "$MEM_PCT" | sed 's/%//' | cut -d'.' -f1)

# Check CPU usage
if [[ "$CPU_NUM" -gt "$MAX_CPU_PCT" ]]; then
    echo -e "${YELLOW}⚠️  High CPU usage: ${CPU_PCT}${NC}"
    send_alert "⚠️ Warning: High CPU Usage" "CPU usage is at ${CPU_PCT}, which exceeds ${MAX_CPU_PCT}% threshold.\nThis may indicate a problem." "warning"
fi

# Check memory usage
if [[ "$MEM_NUM" -gt "$MAX_MEMORY_PCT" ]]; then
    echo -e "${YELLOW}⚠️  High memory usage: ${MEM_PCT}${NC}"
    send_alert "⚠️ Warning: High Memory Usage" "Memory usage is at ${MEM_PCT} (${MEM_USAGE}), which exceeds ${MAX_MEMORY_PCT}% threshold." "warning"
fi

# Check for recent errors in logs (last 50 lines)
ERROR_COUNT=$(docker logs --tail 50 "${CONTAINER_NAME}" 2>&1 | grep -i "error\|exception\|fatal\|critical" | grep -v "INFO" | wc -l)
if [[ "$ERROR_COUNT" -gt 5 ]]; then
    echo -e "${YELLOW}⚠️  Detected ${ERROR_COUNT} errors in recent logs${NC}"
    RECENT_ERRORS=$(docker logs --tail 10 "${CONTAINER_NAME}" 2>&1 | grep -i "error\|exception\|fatal" | head -3)
    send_alert "⚠️ Warning: Errors in Logs" "Detected ${ERROR_COUNT} errors in recent logs:\n\`\`\`\n${RECENT_ERRORS}\n\`\`\`" "warning"
fi

# Check database file exists and is accessible
if docker exec "${CONTAINER_NAME}" test -f /app/insider_data.db 2>/dev/null; then
    DB_SIZE=$(docker exec "${CONTAINER_NAME}" stat -f%z /app/insider_data.db 2>/dev/null || echo "0")
    DB_SIZE_MB=$((DB_SIZE / 1024 / 1024))
    echo -e "${GREEN}✅ Database accessible (${DB_SIZE_MB}MB)${NC}"
else
    echo -e "${RED}❌ Database file not found or not accessible${NC}"
    send_alert "🚨 Critical: Database Missing" "Database file /app/insider_data.db not found or not accessible." "critical"
fi

# Check disk space on host
DISK_USAGE=$(df -h / | tail -1 | awk '{print $5}' | sed 's/%//')
if [[ "$DISK_USAGE" -gt 90 ]]; then
    echo -e "${RED}❌ Critical: Disk usage at ${DISK_USAGE}%${NC}"
    send_alert "🚨 Critical: Low Disk Space" "Disk usage is at ${DISK_USAGE}%. Bot may stop working if disk fills up." "critical"
elif [[ "$DISK_USAGE" -gt 80 ]]; then
    echo -e "${YELLOW}⚠️  Warning: Disk usage at ${DISK_USAGE}%${NC}"
    send_alert "⚠️ Warning: Disk Space Low" "Disk usage is at ${DISK_USAGE}%. Consider cleaning up old files." "warning"
fi

# Get container uptime
STARTED=$(docker inspect --format='{{.State.StartedAt}}' "${CONTAINER_NAME}")
STARTED_TIMESTAMP=$(date -d "$STARTED" +%s 2>/dev/null || date -j -f "%Y-%m-%dT%H:%M:%S" "$STARTED" +%s 2>/dev/null || echo 0)
CURRENT_TIMESTAMP=$(date +%s)
UPTIME_SECONDS=$((CURRENT_TIMESTAMP - STARTED_TIMESTAMP))
UPTIME_DAYS=$((UPTIME_SECONDS / 86400))
UPTIME_HOURS=$(( (UPTIME_SECONDS % 86400) / 3600 ))

echo ""
echo -e "${GREEN}✅ Health check passed${NC}"
echo "   Container: ${CONTAINER_NAME}"
echo "   Status: Running"
echo "   Health: ${HEALTH_STATUS}"
echo "   Uptime: ${UPTIME_DAYS}d ${UPTIME_HOURS}h"
echo "   CPU: ${CPU_PCT}"
echo "   Memory: ${MEM_PCT} (${MEM_USAGE})"
echo "   Disk Usage: ${DISK_USAGE}%"

exit 0

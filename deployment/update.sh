#!/bin/bash
#
# Update Script for Insider Poly Bot
# Safely updates the bot with minimal downtime
#

set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}  Insider Poly Bot - Update${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""

# Change to project directory
cd "${PROJECT_DIR}"

# Step 1: Check if bot is currently running
echo -e "${YELLOW}[1/6]${NC} Checking current status..."

CONTAINER_RUNNING=false
if docker compose ps | grep -q "Up"; then
    CONTAINER_RUNNING=true
    echo -e "${GREEN}✅ Bot is currently running${NC}"
else
    echo -e "${YELLOW}⚠️  Bot is not running${NC}"
fi

# Step 2: Create backup before update
echo ""
echo -e "${YELLOW}[2/6]${NC} Creating pre-update backup..."

if [[ -f insider_data.db ]]; then
    BACKUP_FILE="insider_data.db.pre-update-$(date +%Y%m%d-%H%M%S)"
    cp insider_data.db "${BACKUP_FILE}"
    echo -e "${GREEN}✅ Database backed up to ${BACKUP_FILE}${NC}"
else
    echo -e "${YELLOW}⚠️  No database file found to backup${NC}"
fi

# Step 3: Pull latest code
echo ""
echo -e "${YELLOW}[3/6]${NC} Pulling latest code from repository..."

if git pull; then
    echo -e "${GREEN}✅ Code updated successfully${NC}"
else
    echo -e "${RED}❌ Failed to pull latest code${NC}"
    echo "You may need to stash or commit local changes first"
    exit 1
fi

# Step 4: Check for .env changes
echo ""
echo -e "${YELLOW}[4/6]${NC} Checking for configuration changes..."

if git diff HEAD@{1} HEAD -- .env.example | grep -q "^+"; then
    echo -e "${YELLOW}⚠️  .env.example has been updated${NC}"
    echo "Please review and update your .env file if needed"
    echo ""
    echo "New variables in .env.example:"
    git diff HEAD@{1} HEAD -- .env.example | grep "^+" | grep -v "+++" || true
    echo ""
    read -p "Press Enter to continue after reviewing..."
fi

echo -e "${GREEN}✅ Configuration checked${NC}"

# Step 5: Rebuild and restart
echo ""
echo -e "${YELLOW}[5/6]${NC} Rebuilding Docker image..."

if docker compose build --no-cache; then
    echo -e "${GREEN}✅ Image rebuilt successfully${NC}"
else
    echo -e "${RED}❌ Failed to rebuild image${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}[6/6]${NC} Restarting bot with new version..."

if docker compose down; then
    echo -e "${GREEN}✅ Old container stopped${NC}"
else
    echo -e "${YELLOW}⚠️  No container to stop${NC}"
fi

if docker compose up -d; then
    echo -e "${GREEN}✅ Bot started with new version${NC}"
else
    echo -e "${RED}❌ Failed to start bot${NC}"
    echo ""
    echo "Attempting to restore from backup..."
    if [[ -f "${BACKUP_FILE}" ]]; then
        cp "${BACKUP_FILE}" insider_data.db
        docker compose up -d
        echo -e "${YELLOW}⚠️  Restored previous version, please check logs${NC}"
    fi
    exit 1
fi

# Verify deployment
echo ""
echo "Waiting for bot to start..."
sleep 5

if docker compose ps | grep -q "Up"; then
    echo -e "${GREEN}✅ Bot is running${NC}"
else
    echo -e "${RED}❌ Bot failed to start${NC}"
    echo "Check logs with: docker compose logs"
    exit 1
fi

# Display update summary
echo ""
echo -e "${BLUE}======================================${NC}"
echo -e "${GREEN}✅ Update Complete!${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""
echo "📊 Container Status:"
docker compose ps
echo ""
echo "📋 Recent Commits:"
git log --oneline -5
echo ""
echo "🔍 Monitor logs with: docker compose logs -f"
echo ""

# Cleanup old backup after 30 seconds if all is well
(
    sleep 30
    if docker compose ps | grep -q "Up"; then
        echo "Cleaning up pre-update backup..."
        rm -f "insider_data.db.pre-update-"* 2>/dev/null || true
    fi
) &

exit 0

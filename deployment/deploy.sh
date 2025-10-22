#!/bin/bash
#
# One-Command Deployment Script for Insider Poly Bot
# Handles initial deployment and setup
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
echo -e "${BLUE}  Insider Poly Bot - Deployment${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""

# Change to project directory
cd "${PROJECT_DIR}"

# Step 1: Check prerequisites
echo -e "${YELLOW}[1/7]${NC} Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker is not installed${NC}"
    echo "Please install Docker first: https://docs.docker.com/get-docker/"
    exit 1
fi

if ! command -v docker compose version &> /dev/null; then
    echo -e "${RED}❌ Docker Compose is not installed${NC}"
    echo "Please install Docker Compose: https://docs.docker.com/compose/install/"
    exit 1
fi

echo -e "${GREEN}✅ Docker and Docker Compose are installed${NC}"

# Step 2: Check .env file
echo ""
echo -e "${YELLOW}[2/7]${NC} Checking environment configuration..."

if [[ ! -f .env ]]; then
    echo -e "${YELLOW}⚠️  .env file not found${NC}"
    if [[ -f .env.example ]]; then
        echo "Creating .env from .env.example..."
        cp .env.example .env
        echo -e "${YELLOW}⚠️  IMPORTANT: Edit .env and add your API credentials${NC}"
        echo -e "${YELLOW}   Run: nano .env${NC}"
        echo ""
        read -p "Press Enter after you've configured .env, or Ctrl+C to exit..."
    else
        echo -e "${RED}❌ .env.example not found${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}✅ Environment file exists${NC}"

# Step 3: Validate .env has required variables
echo ""
echo -e "${YELLOW}[3/7]${NC} Validating environment variables..."

REQUIRED_VARS=("DISCORD_WEBHOOK")
MISSING_VARS=()

for var in "${REQUIRED_VARS[@]}"; do
    if ! grep -q "^${var}=" .env || grep "^${var}=.*your_.*_here" .env &>/dev/null; then
        MISSING_VARS+=("$var")
    fi
done

if [[ ${#MISSING_VARS[@]} -gt 0 ]]; then
    echo -e "${YELLOW}⚠️  The following variables need to be configured in .env:${NC}"
    for var in "${MISSING_VARS[@]}"; do
        echo "   - $var"
    done
    echo ""
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo -e "${GREEN}✅ Required environment variables are set${NC}"
fi

# Step 4: Create necessary directories
echo ""
echo -e "${YELLOW}[4/7]${NC} Creating directories..."

mkdir -p logs
mkdir -p ~/backups
mkdir -p ~/logs

echo -e "${GREEN}✅ Directories created${NC}"

# Step 5: Build Docker image
echo ""
echo -e "${YELLOW}[5/7]${NC} Building Docker image..."
echo "This may take a few minutes on first run..."

if docker compose build; then
    echo -e "${GREEN}✅ Docker image built successfully${NC}"
else
    echo -e "${RED}❌ Failed to build Docker image${NC}"
    exit 1
fi

# Step 6: Start the bot
echo ""
echo -e "${YELLOW}[6/7]${NC} Starting the bot..."

if docker compose up -d; then
    echo -e "${GREEN}✅ Bot started successfully${NC}"
else
    echo -e "${RED}❌ Failed to start bot${NC}"
    exit 1
fi

# Step 7: Verify deployment
echo ""
echo -e "${YELLOW}[7/7]${NC} Verifying deployment..."

sleep 5

if docker compose ps | grep -q "Up"; then
    echo -e "${GREEN}✅ Bot is running${NC}"
else
    echo -e "${RED}❌ Bot is not running${NC}"
    echo "Check logs with: docker compose logs"
    exit 1
fi

# Display status
echo ""
echo -e "${BLUE}======================================${NC}"
echo -e "${GREEN}✅ Deployment Complete!${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""
echo "📊 Container Status:"
docker compose ps
echo ""
echo "📋 Useful Commands:"
echo "  View logs:     docker compose logs -f"
echo "  Stop bot:      docker compose down"
echo "  Restart bot:   docker compose restart"
echo "  Update bot:    ./deployment/update.sh"
echo ""
echo "🔧 Next Steps:"
echo "  1. Set up automated backups (see deployment/DEPLOYMENT.md)"
echo "  2. Configure health monitoring (see deployment/DEPLOYMENT.md)"
echo "  3. Monitor logs for any issues: docker compose logs -f"
echo ""
echo -e "${GREEN}Bot is now running 24/7!${NC}"
echo ""

exit 0

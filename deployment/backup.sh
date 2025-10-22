#!/bin/bash
#
# Automated Database Backup Script for Insider Poly Bot
# Backs up SQLite database with 7-day retention
#

set -euo pipefail

# Configuration
BOT_DIR="${BOT_DIR:-$HOME/bots/insider-poly-bot}"
BACKUP_DIR="${BACKUP_DIR:-$HOME/backups}"
DB_FILE="${BOT_DIR}/insider_data.db"
RETENTION_DAYS=7
TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)
BACKUP_FILE="${BACKUP_DIR}/insider_data_${TIMESTAMP}.db"

# Discord webhook for backup notifications (optional)
DISCORD_WEBHOOK="${BACKUP_DISCORD_WEBHOOK:-}"

# Create backup directory if it doesn't exist
mkdir -p "${BACKUP_DIR}"

# Function to send Discord notification
send_discord_notification() {
    local message="$1"
    local color="$2"  # green=3066993, red=15158332, yellow=16776960
    
    if [[ -n "${DISCORD_WEBHOOK}" ]]; then
        curl -H "Content-Type: application/json" \
             -X POST \
             -d "{\"embeds\": [{\"title\": \"🔄 Backup Notification\", \"description\": \"${message}\", \"color\": ${color}}]}" \
             "${DISCORD_WEBHOOK}" 2>/dev/null || true
    fi
}

# Check if database file exists
if [[ ! -f "${DB_FILE}" ]]; then
    echo "❌ Error: Database file not found at ${DB_FILE}"
    send_discord_notification "Backup failed: Database file not found" 15158332
    exit 1
fi

# Get database size
DB_SIZE=$(du -h "${DB_FILE}" | cut -f1)

echo "📦 Starting database backup..."
echo "  Source: ${DB_FILE} (${DB_SIZE})"
echo "  Destination: ${BACKUP_FILE}"

# Perform backup using SQLite's backup command (safer than cp)
if command -v sqlite3 &> /dev/null; then
    # Use SQLite backup command for consistency
    sqlite3 "${DB_FILE}" ".backup '${BACKUP_FILE}'"
    echo "✅ Backup completed using SQLite backup command"
else
    # Fallback to file copy if sqlite3 not available
    cp "${DB_FILE}" "${BACKUP_FILE}"
    echo "✅ Backup completed using file copy"
fi

# Verify backup was created
if [[ ! -f "${BACKUP_FILE}" ]]; then
    echo "❌ Error: Backup file was not created"
    send_discord_notification "Backup failed: File not created" 15158332
    exit 1
fi

# Get backup size
BACKUP_SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
echo "  Backup size: ${BACKUP_SIZE}"

# Compress backup to save space
echo "🗜️  Compressing backup..."
gzip "${BACKUP_FILE}"
COMPRESSED_FILE="${BACKUP_FILE}.gz"
COMPRESSED_SIZE=$(du -h "${COMPRESSED_FILE}" | cut -f1)
echo "  Compressed size: ${COMPRESSED_SIZE}"

# Remove old backups (keep last 7 days)
echo "🧹 Cleaning old backups (keeping last ${RETENTION_DAYS} days)..."
find "${BACKUP_DIR}" -name "insider_data_*.db.gz" -type f -mtime +${RETENTION_DAYS} -delete

# Count remaining backups
BACKUP_COUNT=$(find "${BACKUP_DIR}" -name "insider_data_*.db.gz" -type f | wc -l)
echo "  Backups retained: ${BACKUP_COUNT}"

# List recent backups
echo ""
echo "📋 Recent backups:"
ls -lht "${BACKUP_DIR}"/insider_data_*.db.gz | head -5

# Calculate total backup directory size
TOTAL_SIZE=$(du -sh "${BACKUP_DIR}" | cut -f1)
echo ""
echo "💾 Total backup directory size: ${TOTAL_SIZE}"

# Send success notification
send_discord_notification "✅ Database backup successful\nSize: ${COMPRESSED_SIZE}\nBackups retained: ${BACKUP_COUNT}" 3066993

echo ""
echo "✅ Backup process completed successfully"
echo "   Backup file: ${COMPRESSED_FILE}"

exit 0

# Architecture Documentation

## Overview

This document describes the architectural decisions and patterns used in the Polymarket Insider Bot project.

---

## Database Architecture

### Single Source of Truth Pattern

**CRITICAL:** This project uses a **centralized database configuration** pattern to prevent database proliferation and ensure consistency across all components.

### Database Path Configuration

All database paths are defined in a single file: [`config/database.py`](config/database.py)

**Primary Database:**
```python
DATABASE_PATH = "data/insider_data.db"
```

This translates to `/app/data/insider_data.db` inside Docker containers, which is persisted via the Docker volume mount `./data:/app/data`.

### Why This Matters

**Problem Prevented:** Without centralized configuration, different parts of the codebase may hardcode different database paths, leading to:
- Multiple databases being created
- Data being written to one database but read from another
- CLI commands showing empty results even when data exists
- Confusion about which database is "active"

**Solution:** The `config/database.py` module serves as the **single source of truth** for all database paths. All code must import from this module rather than hardcoding paths.

### How to Use Database Paths

#### ✅ CORRECT Usage

```python
from config.database import DATABASE_PATH, get_connection_string

# For file paths
db_path = DATABASE_PATH  # "data/insider_data.db"

# For SQLAlchemy connection strings
connection_string = get_connection_string()  # "sqlite+aiosqlite:///data/insider_data.db"
```

#### ❌ INCORRECT Usage (Never Do This)

```python
# WRONG - Hardcoded path
db_path = "insider_data.db"

# WRONG - Manual connection string construction
connection_string = f"sqlite+aiosqlite:///{some_path}"
```

### Database File Locations

| Database File | Purpose | Persistence | Location (Docker) | Location (Host) |
|--------------|---------|-------------|-------------------|-----------------|
| `data/insider_data.db` | **Primary production database** | ✅ Persisted in Docker volume | `/app/data/insider_data.db` | `./data/insider_data.db` |
| `backtesting_data.db` | Backtesting data (separate from prod) | ⚠️ Ephemeral (not in volume) | `/app/backtesting_data.db` | `./backtesting_data.db` |
| `demo_backtest.db` | Demo backtesting data | ⚠️ Ephemeral (not in volume) | `/app/demo_backtest.db` | `./demo_backtest.db` |

### Docker Volume Configuration

The production database is persisted using a Docker volume mount:

```yaml
# docker-compose.yml
volumes:
  - ./data:/app/data
```

This ensures:
- ✅ Data survives container restarts
- ✅ Data can be accessed from host system
- ✅ Database can be backed up easily

### Code Patterns

#### Main Application Entry Point

```python
# main.py
from config.database import DATABASE_PATH

monitor = MarketMonitor("insider_config.json", db_path=DATABASE_PATH)
```

#### CLI Commands

```python
# cli/main.py
from config.database import DATABASE_PATH

@click.group()
@click.option('--db-path', default=DATABASE_PATH, help='Path to database file')
def cli(ctx, db_path):
    ctx.obj['DB_PATH'] = db_path
```

```python
# cli/commands/whale_commands.py
from config.database import get_connection_string

async def _list_whales_async(db_path, limit, exclude_mm, min_volume, sort_by):
    db_manager = DatabaseManager.get_instance(get_connection_string(db_path))
```

#### Database Migrations

```python
# database/add_fresh_wallet_fields.py
from config.database import DATABASE_PATH, get_connection_string

async def run_migration(db_path: str = DATABASE_PATH):
    db_url = get_connection_string(db_path)
    db_manager = DatabaseManager.get_instance(db_url)
```

### Migration Guide

If you need to add a new database or change paths:

1. **Update `config/database.py`** - Add new constant or modify existing
2. **Update documentation** - Document the change in this file
3. **Update all code** - Search codebase for hardcoded paths and replace with imports
4. **Update tests** - Ensure tests use the centralized constants
5. **Verify deployment scripts** - Update health checks, backups, etc.

### Verification

To verify the database configuration is correct:

```bash
# Inside container
docker-compose exec insider-poly-bot python3 -c "from config.database import DATABASE_PATH; print(DATABASE_PATH)"

# Check database exists
docker-compose exec insider-poly-bot ls -lh /app/data/insider_data.db

# Verify CLI uses correct database
docker-compose exec insider-poly-bot insider-bot alerts recent --hours 24
```

### Common Issues and Solutions

#### Issue: CLI Commands Return Empty Results

**Cause:** Database path mismatch - CLI reading from different database than bot writes to.

**Solution:**
1. Verify `config/database.py` exists and is correct
2. Check all imports use `from config.database import DATABASE_PATH`
3. Rebuild container: `docker-compose build insider-poly-bot`
4. Verify database path: See verification steps above

#### Issue: Multiple Database Files Found

**Cause:** Hardcoded paths in different parts of codebase.

**Solution:**
1. Search for hardcoded paths: `grep -r "insider_data.db" --exclude-dir=.git`
2. Replace all hardcoded paths with imports from `config/database.py`
3. Delete stale databases after verification
4. Update this documentation

---

## Future Architectural Sections

(To be added as the project evolves)

- Detection Pipeline Architecture
- Alert Management System
- Data Sources and API Integration
- Testing Strategy

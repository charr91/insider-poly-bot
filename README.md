# Polymarket Insider Trading Detection Bot

Real-time detection of unusual trading patterns on [Polymarket](https://polymarket.com) — a prediction market on Polygon. The bot connects to live trade streams, runs statistical detection algorithms, and surfaces actionable alerts via Discord and Telegram.

## What It Does

The bot monitors Polymarket trades in real time and flags activity that may indicate informed trading:

- **Volume spike detection** — Z-score analysis identifies statistically unusual trade bursts
- **Whale tracking** — Flags large trades ($2K+) and tracks repeat whale wallets in a database, with automatic market maker filtering
- **Price movement analysis** — Detects rapid price swings, volatility spikes, and momentum shifts
- **Coordination detection** — Identifies synchronized trading across multiple wallets within tight time windows
- **Fresh wallet detection** — Flags large bets from wallets with little or no trading history

When anomalies are detected, the bot generates severity-rated alerts with context-aware trading recommendations and sends them to Discord/Telegram.

## Tech Stack

| Layer | Technology |
|---|---|
| **Runtime** | Python 3.10+, fully async (`asyncio`, `aiohttp`) |
| **Data Ingestion** | WebSocket (live trades) + REST API (market discovery, historical data) |
| **Detection** | NumPy, SciPy, Pandas — Z-scores, rolling statistics, momentum indicators |
| **Persistence** | SQLAlchemy 2.0 + aiosqlite (async SQLite) with Alembic migrations |
| **API / Dashboard** | FastAPI + Uvicorn, WebSocket push to React frontend |
| **CLI** | Click + Rich for whale queries, alert history, and performance stats |
| **Notifications** | Discord webhooks, Telegram Bot API |
| **Testing** | pytest (async), Hypothesis (property-based), 18 unit + 7 integration test modules |
| **Deployment** | Docker Compose |

## Architecture

```
                    ┌─────────────────┐
                    │   Polymarket    │
                    │   WebSocket     │
                    └────────┬────────┘
                             │ live trades
                             ▼
┌──────────────┐    ┌────────────────┐    ┌──────────────────┐
│  Data API    │───▶│ Market Monitor │───▶│   Detection      │
│  Client      │    │ (orchestrator) │    │   Pipeline       │
└──────────────┘    └────────────────┘    │                  │
  market discovery    manages lifecycle    │  VolumeDetector  │
  historical data     coordinates flow     │  WhaleDetector   │
                                          │  PriceDetector   │
                                          │  CoordDetector   │
                                          │  FreshWalletDet. │
                                          └────────┬─────────┘
                                                   │ anomalies
                                                   ▼
                                          ┌──────────────────┐
                                          │  Alert Manager   │
                                          │                  │
                                          │  Recommendation  │
                                          │  Engine          │
                                          │       │          │
                                          │  ┌────┴────┐     │
                                          │  │Discord  │     │
                                          │  │Telegram │     │
                                          │  │Console  │     │
                                          │  └─────────┘     │
                                          └────────┬─────────┘
                                                   │
                                                   ▼
                                          ┌──────────────────┐
                                          │  SQLite (async)  │
                                          │  alerts, whales, │
                                          │  outcomes, stats │
                                          └──────────────────┘
```

All detectors inherit from a common `DetectorBase` and load thresholds from config. The alert system uses a pluggable storage backend (protocol-based) and formats are handled by dedicated `DiscordFormatter`/`TelegramFormatter` classes.

## Key Design Decisions

- **Async everywhere** — The entire pipeline is async, from WebSocket ingestion through database writes. This allows monitoring hundreds of markets concurrently on a single thread.
- **Statistical detection over rules** — Detectors use Z-scores, rolling standard deviations, and momentum calculations rather than hard thresholds, adapting to each market's baseline.
- **Market maker filtering** — Whale alerts are noisy without it. A heuristic scoring system (trade frequency, balance, diversity, consistency) identifies market makers and excludes them automatically.
- **Centralized config** — All detection thresholds come from `insider_config.json` with env var overrides. No magic numbers in detection code.
- **Pluggable alert storage** — Alert storage uses a Protocol-based backend, making it straightforward to swap SQLite for Postgres or any other store.

## Project Structure

```
insider-poly-bot/
├── main.py                       # Entry point
├── market_monitor.py             # Orchestrator — market lifecycle and analysis loop
├── insider_config.json           # Detection thresholds and settings
│
├── data_sources/
│   ├── data_api_client.py        # Polymarket REST API (async aiohttp)
│   └── websocket_client.py       # Live trade stream
│
├── detection/
│   ├── base_detector.py          # Abstract base for all detectors
│   ├── volume_detector.py        # Z-score volume spike detection
│   ├── whale_detector.py         # Large trade + market maker filtering
│   ├── price_detector.py         # Price movement and volatility analysis
│   ├── coordination_detector.py  # Multi-wallet coordination patterns
│   └── fresh_wallet_detector.py  # New wallet large-bet detection
│
├── alerts/
│   ├── alert_manager.py          # Multi-channel dispatch + rate limiting
│   ├── recommendation_engine.py  # Context-aware trade recommendations
│   ├── telegram_notifier.py      # Telegram Bot API integration
│   └── formatters.py             # Discord/Telegram message formatting
│
├── database/                     # SQLAlchemy models, async session management
├── config/                       # Settings dataclasses, validation, DB config
├── cli/                          # Click CLI — whale queries, alert history, stats
├── dashboard/                    # FastAPI backend + React frontend
├── common/                       # Shared enums, constants, types
│
└── tests/
    ├── unit/                     # 18 test modules
    ├── integration/              # 7 test modules (API, DB, WebSocket, E2E)
    └── conftest.py               # Shared fixtures
```

## Getting Started

```bash
# Clone and set up
git clone https://github.com/charr91/insider-poly-bot.git
cd insider-poly-bot
python -m venv insider-env && source insider-env/bin/activate
pip install -r requirements.txt

# Configure environment (API keys are optional — bot works without them)
cp .env.example .env

# Run
python main.py
```

The bot starts monitoring markets immediately using Polymarket's public APIs. Optional Discord/Telegram webhooks can be configured in `.env` for alert delivery.

## CLI

```bash
pip install -e .

insider-bot run                              # Start the bot
insider-bot whales top --limit 10            # Top whales by volume
insider-bot whales list --exclude-mm         # Exclude market makers
insider-bot alerts recent --severity HIGH    # Recent high-severity alerts
insider-bot stats performance --days 30      # Alert accuracy stats
```

## Documentation

- [Configuration Guide](CONFIGURATION.md) — All parameters and thresholds
- [Architecture Guide](ARCHITECTURE.md) — Database schema, detection scoring, design patterns
- [Usage Guide](USAGE.md) — CLI commands and operational examples
- [Deployment Guide](DEPLOYMENT.md) — Docker setup and production deployment

## License

MIT

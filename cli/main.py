"""
Main CLI entry point for Polymarket Insider Bot

Usage:
    insider-bot run                    # Run the monitoring bot
    insider-bot whales list            # View whale addresses
    insider-bot alerts recent          # View recent alerts
    insider-bot stats performance      # View performance stats
"""

import click
import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

# Import command groups
from cli.commands.whale_commands import whales
from cli.commands.alert_commands import alerts
from cli.commands.stats_commands import stats
from config.database import DATABASE_PATH


@click.group()
@click.option('--db-path', default=DATABASE_PATH, help='Path to database file')
@click.pass_context
def cli(ctx, db_path):
    """
    Polymarket Insider Bot - CLI for tracking whales, alerts, and performance

    Track whale addresses, analyze alert outcomes, and measure detection performance.
    """
    # Store db_path in context for subcommands
    ctx.ensure_object(dict)
    ctx.obj['DB_PATH'] = db_path


@cli.command()
@click.option('--config', default='insider_config.json', help='Path to configuration file')
@click.pass_context
def run(ctx, config):
    """
    Run the Polymarket Insider Bot monitoring system

    This starts the main monitoring loop that tracks markets, detects unusual
    activity, and sends alerts.
    """
    asyncio.run(_run_async(config, ctx.obj['DB_PATH']))


async def _run_async(config_path, db_path):
    """Async implementation of run command"""
    from market_monitor import MarketMonitor
    import logging

    # Load environment variables from .env file
    load_dotenv()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    try:
        # Create and start market monitor
        monitor = MarketMonitor(config_path=config_path, db_path=db_path)
        await monitor.start_monitoring()
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down gracefully...")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


# Register command groups
cli.add_command(whales)
cli.add_command(alerts)
cli.add_command(stats)


if __name__ == '__main__':
    cli()

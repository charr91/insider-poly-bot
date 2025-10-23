"""
CLI commands for performance statistics

Usage:
    insider-bot stats performance [--days N]
    insider-bot stats summary
"""

import click
import asyncio
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from database import DatabaseManager
from persistence.outcome_tracker import OutcomeTracker
from data_sources.data_api_client import DataAPIClient

console = Console()


@click.group()
def stats():
    """Commands for performance statistics and analysis"""
    pass


@stats.command('performance')
@click.option('--days', default=30, help='Number of days to analyze')
@click.pass_context
def performance_stats(ctx, days):
    """Show alert performance statistics"""
    asyncio.run(_performance_stats_async(ctx.obj['DB_PATH'], days))


async def _performance_stats_async(db_path, days):
    """Async implementation of performance stats"""
    db_manager = DatabaseManager.get_instance(f"sqlite+aiosqlite:///{db_path}")
    await db_manager.init_db()

    # Use async context manager for DataAPIClient
    async with DataAPIClient() as data_api:
        outcome_tracker = OutcomeTracker(db_manager, data_api)

        stats = await outcome_tracker.get_performance_stats(days=days)

        if not stats or stats.get('total_alerts', 0) == 0:
            console.print(f"[yellow]No alert outcome data available for the last {days} days[/yellow]")
            return

        # Create performance panel
        total = stats.get('total_alerts', 0)
        profitable = stats.get('profitable_count', 0)
        unprofitable = stats.get('unprofitable_count', 0)
        win_rate = stats.get('win_rate', 0)
        avg_profit = stats.get('avg_profit_pct', 0)

        info = f"""
[cyan]Period:[/cyan] Last {days} days

[bold]Alert Outcomes:[/bold]
  Total Alerts: {total}
  Profitable: {profitable} ([green]{win_rate:.1f}%[/green])
  Unprofitable: {unprofitable}

[bold]Profitability Metrics:[/bold]
  Win Rate: {win_rate:.1f}%
  Avg Profit: {avg_profit:+.2f}%
        """

        # Determine border color based on win rate
        if win_rate >= 60:
            border_color = "green"
            status = "✅ Excellent"
        elif win_rate >= 50:
            border_color = "yellow"
            status = "⚠️  Good"
        else:
            border_color = "red"
            status = "❌ Needs Improvement"

        info += f"\n[bold]Overall Status:[/bold] {status}"

        panel = Panel(
            info.strip(),
            title=f"📊 Alert Performance ({days}d)",
            border_style=border_color
        )

        console.print(panel)

        # Show breakdown by alert type if available
        if 'by_alert_type' in stats:
            console.print("\n[bold]Performance by Alert Type:[/bold]")
            for alert_type, type_stats in stats['by_alert_type'].items():
                type_win_rate = type_stats.get('win_rate', 0)
                console.print(f"  {alert_type}: {type_win_rate:.1f}% win rate ({type_stats.get('count', 0)} alerts)")


@stats.command('summary')
@click.pass_context
def summary_stats(ctx):
    """Show overall system summary statistics"""
    asyncio.run(_summary_stats_async(ctx.obj['DB_PATH']))


async def _summary_stats_async(db_path):
    """Async implementation of summary stats"""
    db_manager = DatabaseManager.get_instance(f"sqlite+aiosqlite:///{db_path}")
    await db_manager.init_db()

    from database import AlertRepository, WhaleRepository, OutcomeRepository

    async with db_manager.session() as session:
        alert_repo = AlertRepository(session)
        whale_repo = WhaleRepository(session)
        outcome_repo = OutcomeRepository(session)

        # Get counts
        recent_alerts = await alert_repo.get_recent_alerts(hours=24, limit=1000)
        all_alerts = await alert_repo.get_recent_alerts(hours=24*365, limit=10000)  # Last year
        top_whales = await whale_repo.get_top_whales(limit=10000, exclude_market_makers=False)
        mm_count = sum(1 for w in top_whales if w.is_market_maker)

        # Create summary table
        table = Table(title="System Summary", box=box.ROUNDED, show_header=False)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right", style="bold")

        table.add_row("Total Alerts (All Time)", str(len(all_alerts)))
        table.add_row("Alerts (Last 24h)", str(len(recent_alerts)))
        table.add_row("", "")  # Spacer
        table.add_row("Total Tracked Whales", str(len(top_whales)))
        table.add_row("Market Makers Detected", str(mm_count))
        table.add_row("Active Whales", str(len(top_whales) - mm_count))

        console.print(table)

        # Alert breakdown by severity
        if recent_alerts:
            console.print("\n[bold]Recent Alerts by Severity (24h):[/bold]")
            severity_counts = {}
            for alert in recent_alerts:
                severity_counts[alert.severity] = severity_counts.get(alert.severity, 0) + 1

            for severity in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
                count = severity_counts.get(severity, 0)
                if count > 0:
                    console.print(f"  {severity}: {count}")


@stats.command('whales')
@click.pass_context
def whale_stats(ctx):
    """Show whale statistics summary"""
    asyncio.run(_whale_stats_async(ctx.obj['DB_PATH']))


async def _whale_stats_async(db_path):
    """Async implementation of whale stats"""
    db_manager = DatabaseManager.get_instance(f"sqlite+aiosqlite:///{db_path}")
    await db_manager.init_db()

    from database import WhaleRepository

    async with db_manager.session() as session:
        whale_repo = WhaleRepository(session)

        # Get all whales
        all_whales = await whale_repo.get_top_whales(limit=10000, exclude_market_makers=False)

        if not all_whales:
            console.print("[yellow]No whale data available[/yellow]")
            return

        # Calculate statistics
        total_whales = len(all_whales)
        mm_count = sum(1 for w in all_whales if w.is_market_maker)
        active_whales = total_whales - mm_count

        total_volume = sum(w.total_volume_usd for w in all_whales)
        whale_volume = sum(w.total_volume_usd for w in all_whales if not w.is_market_maker)

        # Create stats panel
        info = f"""
[cyan]Total Tracked Addresses:[/cyan] {total_whales}
[cyan]Active Whales:[/cyan] {active_whales} ({active_whales/total_whales*100:.1f}%)
[cyan]Market Makers:[/cyan] {mm_count} ({mm_count/total_whales*100:.1f}%)

[cyan]Total Volume:[/cyan] ${total_volume:,.0f}
[cyan]Whale Volume:[/cyan] ${whale_volume:,.0f}
[cyan]MM Volume:[/cyan] ${total_volume - whale_volume:,.0f}

[cyan]Avg Volume per Whale:[/cyan] ${whale_volume/active_whales if active_whales > 0 else 0:,.0f}
        """

        panel = Panel(
            info.strip(),
            title="🐋 Whale Statistics",
            border_style="cyan"
        )

        console.print(panel)

        # Show top 5 whales by volume
        console.print("\n[bold]Top 5 Whales by Volume:[/bold]")
        top_5 = sorted([w for w in all_whales if not w.is_market_maker],
                       key=lambda w: w.total_volume_usd, reverse=True)[:5]

        for i, whale in enumerate(top_5, 1):
            address_short = f"{whale.address[:10]}...{whale.address[-6:]}"
            console.print(f"  {i}. {address_short}: ${whale.total_volume_usd:,.0f}")

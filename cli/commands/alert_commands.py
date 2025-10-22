"""
CLI commands for alert tracking

Usage:
    insider-bot alerts recent [--hours N] [--severity LEVEL]
    insider-bot alerts show <alert-id>
    insider-bot alerts by-market <market-id>
"""

import click
import asyncio
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
from datetime import datetime

from database import DatabaseManager, AlertRepository

console = Console()


@click.group()
def alerts():
    """Commands for alert tracking and analysis"""
    pass


@alerts.command('recent')
@click.option('--hours', default=24, help='Hours to look back')
@click.option('--severity', type=click.Choice(['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']), help='Filter by severity')
@click.option('--limit', default=50, help='Maximum number of alerts to show')
@click.pass_context
def recent_alerts(ctx, hours, severity, limit):
    """Show recent alerts"""
    asyncio.run(_recent_alerts_async(ctx.obj['DB_PATH'], hours, severity, limit))


async def _recent_alerts_async(db_path, hours, severity, limit):
    """Async implementation of recent alerts"""
    db_manager = DatabaseManager.get_instance(f"sqlite+aiosqlite:///{db_path}")
    await db_manager.init_db()

    async with db_manager.session() as session:
        alert_repo = AlertRepository(session)
        alerts = await alert_repo.get_recent_alerts(hours=hours, severity=severity, limit=limit)

        if not alerts:
            console.print(f"[yellow]No alerts found in the last {hours} hours[/yellow]")
            return

        # Create rich table
        table = Table(title=f"Recent Alerts (Last {hours}h)", box=box.ROUNDED)
        table.add_column("ID", style="cyan", justify="right")
        table.add_column("Time", style="dim")
        table.add_column("Market", no_wrap=False)
        table.add_column("Type", style="magenta")
        table.add_column("Severity", justify="center")
        table.add_column("Confidence", justify="right")

        for alert in alerts:
            # Severity with color
            severity_colors = {
                'CRITICAL': '[red bold]🔴 CRITICAL[/red bold]',
                'HIGH': '[red]🟠 HIGH[/red]',
                'MEDIUM': '[yellow]🟡 MEDIUM[/yellow]',
                'LOW': '[green]🟢 LOW[/green]'
            }
            severity_str = severity_colors.get(alert.severity, alert.severity)

            # Time formatting
            time_str = alert.timestamp.strftime('%m/%d %H:%M')

            # Market name truncation
            market_name = (alert.market_question[:35] + '...') if len(alert.market_question) > 35 else alert.market_question

            table.add_row(
                str(alert.id),
                time_str,
                market_name,
                alert.alert_type,
                severity_str,
                f"{alert.confidence_score:.1f}"
            )

        console.print(table)
        console.print(f"\n[dim]Showing {len(alerts)} alert(s)[/dim]")


@alerts.command('show')
@click.argument('alert_id', type=int)
@click.pass_context
def show_alert(ctx, alert_id):
    """Show detailed information about a specific alert"""
    asyncio.run(_show_alert_async(ctx.obj['DB_PATH'], alert_id))


async def _show_alert_async(db_path, alert_id):
    """Async implementation of show alert"""
    db_manager = DatabaseManager.get_instance(f"sqlite+aiosqlite:///{db_path}")
    await db_manager.init_db()

    async with db_manager.session() as session:
        alert_repo = AlertRepository(session)
        alert = await alert_repo.get_by_id(alert_id)

        if not alert:
            console.print(f"[red]Alert not found: {alert_id}[/red]")
            return

        # Create detailed panel
        info = f"""
[cyan]Alert ID:[/cyan] {alert.id}
[cyan]Market ID:[/cyan] {alert.market_id}
[cyan]Market Question:[/cyan] {alert.market_question}

[cyan]Alert Type:[/cyan] {alert.alert_type}
[cyan]Severity:[/cyan] {alert.severity}
[cyan]Timestamp:[/cyan] {alert.timestamp}
[cyan]Confidence Score:[/cyan] {alert.confidence_score:.2f}
        """

        # Add analysis if available
        if alert.analysis:
            analysis_dict = alert.analysis if isinstance(alert.analysis, dict) else {}
            if analysis_dict:
                info += "\n[cyan]Analysis:[/cyan]\n"
                for key, value in analysis_dict.items():
                    info += f"  • {key}: {value}\n"

        severity_colors = {'CRITICAL': 'red', 'HIGH': 'red', 'MEDIUM': 'yellow', 'LOW': 'green'}
        border_color = severity_colors.get(alert.severity, 'cyan')

        panel = Panel(
            info.strip(),
            title=f"🚨 Alert Details",
            border_style=border_color
        )

        console.print(panel)


@alerts.command('by-market')
@click.argument('market_id')
@click.option('--limit', default=20, help='Maximum number of alerts to show')
@click.pass_context
def alerts_by_market(ctx, market_id, limit):
    """Show all alerts for a specific market"""
    asyncio.run(_alerts_by_market_async(ctx.obj['DB_PATH'], market_id, limit))


async def _alerts_by_market_async(db_path, market_id, limit):
    """Async implementation of alerts by market"""
    db_manager = DatabaseManager.get_instance(f"sqlite+aiosqlite:///{db_path}")
    await db_manager.init_db()

    async with db_manager.session() as session:
        alert_repo = AlertRepository(session)
        alerts = await alert_repo.get_alerts_by_market(market_id, limit=limit)

        if not alerts:
            console.print(f"[yellow]No alerts found for market: {market_id[:20]}...[/yellow]")
            return

        console.print(f"\n[bold cyan]Alerts for Market: {alerts[0].market_question}[/bold cyan]\n")

        for alert in alerts:
            time_str = alert.timestamp.strftime('%Y-%m-%d %H:%M')
            console.print(f"  [{alert.severity}] {alert.alert_type} - {time_str} (Confidence: {alert.confidence_score:.1f})")

        console.print(f"\n[dim]Total: {len(alerts)} alert(s)[/dim]")

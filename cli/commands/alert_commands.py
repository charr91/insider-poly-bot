"""
CLI commands for alert tracking

Usage:
    insider-bot alerts recent [--hours N] [--severity LEVEL]
    insider-bot alerts show <alert-id>
    insider-bot alerts by-market <market-id>
    insider-bot alerts test [--config CONFIG]
"""

import click
import asyncio
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
from datetime import datetime
import json
from pathlib import Path
from dotenv import load_dotenv

from database import DatabaseManager, AlertRepository
from alerts.alert_manager import AlertManager
from config.settings import Settings
from config.database import get_connection_string

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
    db_manager = DatabaseManager.get_instance(get_connection_string(db_path))
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
    db_manager = DatabaseManager.get_instance(get_connection_string(db_path))
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
    db_manager = DatabaseManager.get_instance(get_connection_string(db_path))
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


@alerts.command('test')
@click.option('--config', default='insider_config.json', help='Path to configuration file')
@click.pass_context
def test_alerts(ctx, config):
    """Test Discord and Telegram alert connections"""
    asyncio.run(_test_alerts_async(config))


async def _test_alerts_async(config_path):
    """Async implementation of test alerts"""
    # Load environment variables
    load_dotenv()

    # Load configuration
    try:
        config_file = Path(config_path)
        if not config_file.exists():
            console.print(f"[red]Config file not found: {config_path}[/red]")
            return

        with open(config_file) as f:
            config = json.load(f)
    except Exception as e:
        console.print(f"[red]Failed to load config: {e}[/red]")
        return

    # Create settings and alert manager
    try:
        settings = Settings(config)
        alert_manager = AlertManager(settings)

        console.print("\n[bold cyan]🧪 Testing Alert System Connections[/bold cyan]\n")

        # Show configuration status
        table = Table(title="Alert Channel Configuration", box=box.ROUNDED)
        table.add_column("Channel", style="cyan")
        table.add_column("Status", justify="center")
        table.add_column("Details", style="dim")

        # Discord configuration
        if alert_manager.discord_webhook:
            webhook_preview = alert_manager.discord_webhook[:50] + "..." if len(alert_manager.discord_webhook) > 50 else alert_manager.discord_webhook
            table.add_row("Discord", "[green]✓ Configured[/green]", webhook_preview)
        else:
            table.add_row("Discord", "[yellow]✗ Not configured[/yellow]", "No webhook set")

        # Telegram configuration
        if alert_manager.telegram_notifier.is_enabled():
            bot_info = alert_manager.telegram_notifier.get_bot_info()
            table.add_row("Telegram", "[green]✓ Configured[/green]", f"Chat ID: {bot_info['chat_id']}")
        else:
            table.add_row("Telegram", "[yellow]✗ Not configured[/yellow]", "Missing bot token or chat ID")

        console.print(table)

        # Test connections
        console.print("\n[bold]Sending Test Messages...[/bold]\n")

        discord_success = False
        telegram_success = False

        # Test Discord
        if alert_manager.discord_webhook:
            try:
                import aiohttp
                test_embed = {
                    "title": "🧪 Test Alert",
                    "description": "Polymarket Insider Bot - Alert System Test",
                    "color": 0x00FF00,  # Green
                    "timestamp": datetime.now().isoformat(),
                    "footer": {"text": "This is a test message"}
                }

                async with aiohttp.ClientSession() as session:
                    payload = {"embeds": [test_embed]}
                    async with session.post(alert_manager.discord_webhook, json=payload, timeout=10) as resp:
                        if resp.status in [200, 204]:
                            console.print("[green]✅ Discord:[/green] Test message sent successfully")
                            discord_success = True
                        else:
                            response_text = await resp.text()
                            console.print(f"[red]❌ Discord:[/red] HTTP {resp.status}")
                            console.print(f"   [dim]{response_text[:200]}[/dim]")
            except Exception as e:
                console.print(f"[red]❌ Discord:[/red] {str(e)}")

        # Test Telegram
        if alert_manager.telegram_notifier.is_enabled():
            try:
                result = await alert_manager.telegram_notifier.test_connection()
                if result:
                    console.print("[green]✅ Telegram:[/green] Test message sent successfully")
                    telegram_success = True
                else:
                    console.print("[red]❌ Telegram:[/red] Test failed (see logs)")
            except Exception as e:
                console.print(f"[red]❌ Telegram:[/red] {str(e)}")

        # Summary
        console.print()
        configured_count = sum([
            bool(alert_manager.discord_webhook),
            alert_manager.telegram_notifier.is_enabled()
        ])
        success_count = sum([discord_success, telegram_success])

        if configured_count == 0:
            console.print("[yellow]⚠️  No alert channels configured![/yellow]")
            console.print("\n[dim]To configure alerts:[/dim]")
            console.print("[dim]  1. Add DISCORD_WEBHOOK to your .env file, or[/dim]")
            console.print("[dim]  2. Add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to your .env file[/dim]")
        elif success_count == configured_count:
            console.print(f"[green bold]✅ All {configured_count} configured channel(s) working![/green bold]")
        elif success_count > 0:
            console.print(f"[yellow]⚠️  {success_count}/{configured_count} channel(s) working[/yellow]")
        else:
            console.print(f"[red]❌ All configured channels failed[/red]")

    except Exception as e:
        console.print(f"\n[red]❌ Error testing alerts: {e}[/red]")
        import traceback
        traceback.print_exc()

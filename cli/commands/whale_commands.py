"""
CLI commands for whale tracking

Usage:
    insider-bot whales list [--limit N] [--exclude-mm] [--min-volume N]
    insider-bot whales show <address>
    insider-bot whales top [--limit N]
"""

import click
import asyncio
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from database import DatabaseManager
from persistence.whale_tracker import WhaleTracker

console = Console()


@click.group()
def whales():
    """Commands for whale address tracking"""
    pass


@whales.command('list')
@click.option('--limit', default=50, help='Maximum number of whales to show')
@click.option('--exclude-mm', is_flag=True, default=True, help='Exclude market makers')
@click.option('--min-volume', default=0, type=float, help='Minimum total volume in USD')
@click.option('--sort-by', default='total_volume_usd', type=click.Choice(['total_volume_usd', 'trade_count', 'last_seen']), help='Sort field')
@click.pass_context
def list_whales(ctx, limit, exclude_mm, min_volume, sort_by):
    """List tracked whale addresses"""
    asyncio.run(_list_whales_async(ctx.obj['DB_PATH'], limit, exclude_mm, min_volume, sort_by))


async def _list_whales_async(db_path, limit, exclude_mm, min_volume, sort_by):
    """Async implementation of list whales"""
    db_manager = DatabaseManager.get_instance(f"sqlite+aiosqlite:///{db_path}")
    await db_manager.init_db()

    whale_tracker = WhaleTracker(db_manager)
    whales = await whale_tracker.get_top_whales(
        limit=limit,
        exclude_mm=exclude_mm,
        min_volume=min_volume,
        sort_by=sort_by
    )

    if not whales:
        console.print("[yellow]No whales found matching criteria[/yellow]")
        return

    # Create rich table
    table = Table(title=f"Top {len(whales)} Whale Addresses", box=box.ROUNDED)
    table.add_column("Address", style="cyan", no_wrap=False)
    table.add_column("Total Volume", justify="right", style="green")
    table.add_column("Trades", justify="right")
    table.add_column("Markets", justify="right")
    table.add_column("MM Score", justify="right")
    table.add_column("Status", justify="center")
    table.add_column("Tags", style="yellow")

    for whale in whales:
        address_short = f"{whale['address'][:10]}...{whale['address'][-8:]}"
        volume_str = f"${whale['total_volume_usd']:,.0f}"
        mm_score = whale.get('market_maker_score', 0)
        mm_status = "🏦 MM" if whale.get('is_market_maker', False) else "🐋 Whale"
        tags_str = ", ".join(whale.get('tags', []))[:30]

        table.add_row(
            address_short,
            volume_str,
            str(whale.get('trade_count', 0)),
            str(len(whale.get('markets_traded', []))),
            str(mm_score),
            mm_status,
            tags_str or "-"
        )

    console.print(table)
    console.print(f"\n[dim]Showing {len(whales)} whale(s)[/dim]")
    if exclude_mm:
        console.print("[dim]Market makers excluded[/dim]")


@whales.command('show')
@click.argument('address')
@click.pass_context
def show_whale(ctx, address):
    """Show detailed information about a specific whale address"""
    asyncio.run(_show_whale_async(ctx.obj['DB_PATH'], address))


async def _show_whale_async(db_path, address):
    """Async implementation of show whale"""
    db_manager = DatabaseManager.get_instance(f"sqlite+aiosqlite:///{db_path}")
    await db_manager.init_db()

    whale_tracker = WhaleTracker(db_manager)
    whale = await whale_tracker.get_whale_by_address(address)

    if not whale:
        console.print(f"[red]Whale not found: {address}[/red]")
        return

    # Create detailed panel
    info = f"""
[cyan]Address:[/cyan] {whale['address']}
[cyan]Total Volume:[/cyan] ${whale['total_volume_usd']:,.2f}
[cyan]Buy Volume:[/cyan] ${whale.get('buy_volume_usd', 0):,.2f}
[cyan]Sell Volume:[/cyan] ${whale.get('sell_volume_usd', 0):,.2f}
[cyan]Trade Count:[/cyan] {whale.get('trade_count', 0)}

[cyan]Markets Traded:[/cyan] {len(whale.get('markets_traded', []))}
[cyan]First Seen:[/cyan] {whale.get('first_seen', 'Unknown')}
[cyan]Last Seen:[/cyan] {whale.get('last_seen', 'Unknown')}

[cyan]Market Maker Score:[/cyan] {whale.get('market_maker_score', 0)}/100
[cyan]Is Market Maker:[/cyan] {'Yes' if whale.get('is_market_maker', False) else 'No'}

[cyan]Tags:[/cyan] {', '.join(whale.get('tags', [])) or 'None'}
    """

    panel = Panel(
        info.strip(),
        title=f"🐋 Whale Details",
        border_style="cyan" if not whale.get('is_market_maker', False) else "yellow"
    )

    console.print(panel)

    # Show metrics if available
    metrics = whale.get('metrics', {})
    if metrics:
        console.print("\n[bold]Additional Metrics:[/bold]")
        for key, value in metrics.items():
            console.print(f"  {key}: {value}")


@whales.command('top')
@click.option('--limit', default=10, help='Number of top whales to show')
@click.pass_context
def top_whales(ctx, limit):
    """Show top whales by volume (quick summary)"""
    asyncio.run(_top_whales_async(ctx.obj['DB_PATH'], limit))


async def _top_whales_async(db_path, limit):
    """Async implementation of top whales"""
    db_manager = DatabaseManager.get_instance(f"sqlite+aiosqlite:///{db_path}")
    await db_manager.init_db()

    whale_tracker = WhaleTracker(db_manager)
    whales = await whale_tracker.get_top_whales(limit=limit, exclude_mm=True)

    if not whales:
        console.print("[yellow]No whales found[/yellow]")
        return

    console.print(f"\n[bold cyan]Top {len(whales)} Whales by Volume[/bold cyan]\n")

    for i, whale in enumerate(whales, 1):
        address_short = f"{whale['address'][:10]}...{whale['address'][-6:]}"
        volume_str = f"${whale['total_volume_usd']:,.0f}"
        console.print(f"{i:2d}. {address_short}  {volume_str:>15s}  ({whale.get('trade_count', 0)} trades)")

    console.print()

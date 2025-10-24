"""
Database management commands for the Insider Bot CLI

Provides commands for database migrations and schema management.
"""

import click
import asyncio
import sys
from pathlib import Path


@click.group()
def db():
    """
    Database management commands

    Manage database schema, run migrations, and perform maintenance tasks.
    """
    pass


@db.command()
@click.pass_context
@click.option('--verify', is_flag=True, help='Verify migration after running')
def migrate(ctx, verify):
    """
    Run database migrations to update schema

    This command runs pending database migrations to ensure the database schema
    matches the current version of the application.

    Example:
        insider-bot db migrate
        insider-bot db migrate --verify
    """
    db_path = ctx.obj.get('DB_PATH')

    # Check if database exists
    if not Path(db_path).exists():
        click.echo(click.style(f"❌ Database not found: {db_path}", fg='red'))
        click.echo("Please run the bot first to create the database, or specify a different path with --db-path")
        sys.exit(1)

    click.echo(click.style(f"🔧 Running database migrations on: {db_path}", fg='cyan'))

    # Run the migration
    asyncio.run(_run_migration_async(db_path, verify))


async def _run_migration_async(db_path: str, verify: bool):
    """Async implementation of migration command"""
    import logging

    # Setup logging to show migration output
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s'  # Simpler format for CLI output
    )

    try:
        # Import and run the migration
        from database.add_fresh_wallet_fields import run_migration, verify_migration

        # Run migration
        await run_migration(db_path)

        # Optionally verify
        if verify:
            click.echo("\n" + "="*50)
            click.echo(click.style("Verifying migration...", fg='cyan'))
            click.echo("="*50)
            await verify_migration(db_path)

        click.echo("\n" + click.style("✅ Migration completed successfully!", fg='green'))

    except Exception as e:
        click.echo(click.style(f"\n❌ Migration failed: {e}", fg='red'))
        import traceback
        traceback.print_exc()
        sys.exit(1)


@db.command()
@click.pass_context
def check_schema(ctx):
    """
    Check current database schema

    Displays the current schema of key database tables to verify structure.

    Example:
        insider-bot db check-schema
    """
    db_path = ctx.obj.get('DB_PATH')

    if not Path(db_path).exists():
        click.echo(click.style(f"❌ Database not found: {db_path}", fg='red'))
        sys.exit(1)

    click.echo(click.style(f"📋 Checking schema for: {db_path}", fg='cyan'))
    asyncio.run(_check_schema_async(db_path))


async def _check_schema_async(db_path: str):
    """Async implementation of schema check"""
    from config.database import get_connection_string
    from database.database import DatabaseManager
    from sqlalchemy import text

    try:
        db_manager = DatabaseManager.get_instance(get_connection_string(db_path))

        async with db_manager.session() as session:
            # Check whale_addresses table
            click.echo("\n" + "="*50)
            click.echo(click.style("whale_addresses table schema:", fg='yellow', bold=True))
            click.echo("="*50)

            result = await session.execute(text("PRAGMA table_info(whale_addresses)"))
            columns = result.fetchall()

            for col in columns:
                col_id, name, col_type, not_null, default, pk = col
                nullable = "NOT NULL" if not_null else "NULL"
                pk_marker = " [PRIMARY KEY]" if pk else ""
                click.echo(f"  {name:<25} {col_type:<15} {nullable}{pk_marker}")

            # Check alerts table
            click.echo("\n" + "="*50)
            click.echo(click.style("alerts table schema:", fg='yellow', bold=True))
            click.echo("="*50)

            result = await session.execute(text("PRAGMA table_info(alerts)"))
            columns = result.fetchall()

            for col in columns:
                col_id, name, col_type, not_null, default, pk = col
                nullable = "NOT NULL" if not_null else "NULL"
                pk_marker = " [PRIMARY KEY]" if pk else ""
                click.echo(f"  {name:<25} {col_type:<15} {nullable}{pk_marker}")

            click.echo("\n" + click.style("✅ Schema check complete", fg='green'))

    except Exception as e:
        click.echo(click.style(f"❌ Schema check failed: {e}", fg='red'))
        sys.exit(1)

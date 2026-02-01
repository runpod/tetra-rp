"""Resource management commands."""

import time
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live

from ...core.resources.resource_manager import ResourceManager

console = Console()


def report_command(
    live: bool = typer.Option(False, "--live", "-l", help="Live updating status"),
    refresh: int = typer.Option(
        2, "--refresh", "-r", help="Refresh interval for live mode"
    ),
):
    """Show resource status dashboard."""

    resource_manager = ResourceManager()

    if live:
        try:
            with Live(
                generate_resource_table(resource_manager),
                console=console,
                refresh_per_second=1 / refresh,
                screen=True,
            ) as live_display:
                while True:
                    time.sleep(refresh)
                    live_display.update(generate_resource_table(resource_manager))
        except KeyboardInterrupt:
            console.print("\n📊 Live monitoring stopped")
    else:
        table = generate_resource_table(resource_manager)
        console.print(table)


def generate_resource_table(resource_manager: ResourceManager) -> Panel:
    """Generate a formatted table of resources."""

    resources = resource_manager._resources

    if not resources:
        return Panel(
            "📊 No resources currently tracked\n\n"
            "Resources will appear here after running your Tetra applications.",
            title="Resource Status Report",
            expand=False,
        )

    table = Table(title="Resource Status Report")
    table.add_column("Resource ID", style="cyan", no_wrap=True)
    table.add_column("Status", justify="center")
    table.add_column("Type", style="magenta")
    table.add_column("URL", style="blue")
    table.add_column("Health", justify="center")

    active_count = 0
    error_count = 0

    for uid, resource in resources.items():
        # Determine status
        try:
            is_deployed = resource.is_deployed()
            if is_deployed:
                status = "🟢 Active"
                active_count += 1
            else:
                status = "🔴 Inactive"
                error_count += 1
        except Exception:
            status = "🟡 Unknown"

        # Get resource info
        resource_type = resource.__class__.__name__

        try:
            url = resource.url if hasattr(resource, "url") else "N/A"
        except Exception:
            url = "N/A"

        # Health check (simplified for now)
        health = "✓" if status == "🟢 Active" else "✗"

        table.add_row(
            uid[:20] + "..." if len(uid) > 20 else uid,
            status,
            resource_type,
            url,
            health,
        )

    # Summary
    total = len(resources)
    idle_count = total - active_count - error_count
    summary = f"Total: {total} resources ({active_count} active"
    if idle_count > 0:
        summary += f", {idle_count} idle"
    if error_count > 0:
        summary += f", {error_count} error"
    summary += ")"

    return Panel(table, subtitle=summary, expand=False)

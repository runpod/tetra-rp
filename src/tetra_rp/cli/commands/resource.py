"""Resource management commands."""

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live
from rich.progress import Progress, SpinnerColumn, TextColumn
import questionary
import time

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


def clean_command(
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Remove all tracked resources after confirmation."""

    resource_manager = ResourceManager()
    resources = resource_manager._resources

    if not resources:
        console.print("🧹 No resources to clean")
        return

    # Show cleanup preview
    console.print(generate_cleanup_preview(resources))

    # Confirmation unless forced
    if not force:
        try:
            confirmed = questionary.confirm(
                "Are you sure you want to clean all resources?"
            ).ask()

            if not confirmed:
                console.print("Cleanup cancelled")
                return
        except KeyboardInterrupt:
            console.print("\nCleanup cancelled")
            return

    # Clean resources with progress
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Cleaning resources...", total=len(resources))

        for uid in list(resources.keys()):
            resource = resources[uid]
            progress.update(
                task, description=f"Removing {resource.__class__.__name__}..."
            )

            # Remove resource (this will also clean up remotely if needed)
            resource_manager.remove_resource(uid)

            progress.advance(task)
            time.sleep(0.1)  # Small delay for visual feedback

    console.print("All resources cleaned successfully")


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


def generate_cleanup_preview(resources: dict) -> Panel:
    """Generate a preview of resources to be cleaned."""

    content = "The following resources will be removed:\n\n"

    for uid, resource in resources.items():
        resource_type = resource.__class__.__name__

        try:
            status = "Active" if resource.is_deployed() else "Inactive"
        except Exception:
            status = "Unknown"

        try:
            url = (
                f" - {resource.url}"
                if hasattr(resource, "url") and resource.url != "N/A"
                else ""
            )
        except Exception:
            url = ""

        content += f"  • {resource_type} ({status}){url}\n"

    content += "\n⚠️  This action cannot be undone!"

    return Panel(content, title="🧹 Cleanup Preview", expand=False)

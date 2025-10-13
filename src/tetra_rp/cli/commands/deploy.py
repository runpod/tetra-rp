"""Deployment environment management commands."""

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
import questionary

from ..utils.deployment import (
    get_deployment_environments,
    create_deployment_environment,
    remove_deployment_environment,
    deploy_to_environment,
    rollback_deployment,
    get_environment_info,
)

console = Console()


def list_command():
    """Show available deployment environments."""

    environments = get_deployment_environments()

    if not environments:
        console.print(
            Panel(
                "📦 No deployment environments found\n\n"
                "Create one with: [bold]runpod remote deploy new <name>[/bold]",
                title="Deployment Environments",
                expand=False,
            )
        )
        return

    table = Table(title="Deployment Environments")
    table.add_column("Environment", style="cyan", no_wrap=True)
    table.add_column("Status", justify="center")
    table.add_column("Current Version", style="magenta")
    table.add_column("Last Deployed", style="yellow")
    table.add_column("URL", style="blue")

    active_count = 0
    idle_count = 0

    for env_name, env_info in environments.items():
        status = env_info.get("status", "Unknown")
        if status == "active":
            status_display = "🟢 Active"
            active_count += 1
        elif status == "idle":
            status_display = "🟡 Idle"
            idle_count += 1
        else:
            status_display = "🔴 Error"

        table.add_row(
            env_name,
            status_display,
            env_info.get("current_version", "N/A"),
            env_info.get("last_deployed", "Never"),
            env_info.get("url", "N/A"),
        )

    console.print(table)

    # Summary
    total = len(environments)
    error_count = total - active_count - idle_count
    summary = f"Total: {total} environments ({active_count} active"
    if idle_count > 0:
        summary += f", {idle_count} idle"
    if error_count > 0:
        summary += f", {error_count} error"
    summary += ")"

    console.print(f"\n{summary}")


def new_command(name: str):
    """Create a new deployment environment."""

    environments = get_deployment_environments()

    if name in environments:
        console.print(f"Environment '{name}' already exists")
        raise typer.Exit(1)

    # Interactive configuration
    config = {}

    try:
        config["region"] = questionary.select(
            "Select region:",
            choices=["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"],
        ).ask()

        config["instance_type"] = questionary.select(
            "Instance type:", choices=["A40", "A100", "H100", "RTX4090"]
        ).ask()

        config["auto_scale"] = questionary.confirm("Enable auto-scaling?").ask()

        if not all([config["region"], config["instance_type"]]):
            console.print("Configuration cancelled")
            raise typer.Exit(1)

    except KeyboardInterrupt:
        console.print("\nEnvironment creation cancelled")
        raise typer.Exit(1)

    # Create environment
    with console.status(f"Creating environment '{name}'..."):
        create_deployment_environment(name, config)

    # Success message
    panel_content = f"Environment '[bold]{name}[/bold]' created successfully\n\n"
    panel_content += f"Region: {config['region']}\n"
    panel_content += f"Instance: {config['instance_type']}\n"
    panel_content += f"Auto-scale: {'Enabled' if config['auto_scale'] else 'Disabled'}"

    console.print(Panel(panel_content, title="🚀 Environment Created", expand=False))

    console.print(f"\nNext: [bold]flash deploy send {name}[/bold]")


def send_command(name: str):
    """Deploy project to deployment environment."""

    environments = get_deployment_environments()

    if name not in environments:
        console.print(f"Environment '{name}' not found")
        console.print("Available environments:")
        for env_name in environments.keys():
            console.print(f"  • {env_name}")
        raise typer.Exit(1)

    # Deploy with mock progress
    console.print(f"🚀 Deploying to '[bold]{name}[/bold]'...")

    try:
        result = deploy_to_environment(name)

        panel_content = f"Deployed to '[bold]{name}[/bold]' successfully\n\n"
        panel_content += f"Version: {result['version']}\n"
        panel_content += f"URL: {result['url']}\n"
        panel_content += "Status: 🟢 Active"

        console.print(
            Panel(panel_content, title="🚀 Deployment Complete", expand=False)
        )

    except Exception as e:
        console.print(f"Deployment failed: {e}")
        raise typer.Exit(1)


def report_command(name: str):
    """Show detailed environment status and metrics."""

    environments = get_deployment_environments()

    if name not in environments:
        console.print(f"Environment '{name}' not found")
        raise typer.Exit(1)

    env_info = get_environment_info(name)

    # Environment status
    status = env_info.get("status", "unknown")
    status_display = {
        "active": "🟢 Active",
        "idle": "🟡 Idle",
        "error": "🔴 Error",
    }.get(status, "❓ Unknown")

    # Main info panel
    main_info = f"Status: {status_display}\n"
    main_info += f"Current Version: {env_info.get('current_version', 'N/A')}\n"
    main_info += f"URL: {env_info.get('url', 'N/A')}\n"
    main_info += f"Last Deployed: {env_info.get('last_deployed', 'Never')}\n"
    main_info += f"Uptime: {env_info.get('uptime', 'N/A')}"

    console.print(
        Panel(main_info, title=f"📊 Environment Report: {name}", expand=False)
    )

    # Version history
    versions = env_info.get("version_history", [])
    if versions:
        version_table = Table(title="Version History")
        version_table.add_column("Version", style="cyan")
        version_table.add_column("Status", justify="center")
        version_table.add_column("Deployed", style="yellow")
        version_table.add_column("Description", style="white")

        for version in versions[:5]:  # Show last 5 versions
            version_status = (
                "🟢 Current" if version.get("is_current") else "📦 Previous"
            )
            version_table.add_row(
                version.get("version", "N/A"),
                version_status,
                version.get("deployed_at", "N/A"),
                version.get("description", "No description"),
            )

        console.print(version_table)

    # Mock metrics
    console.print("\n[bold]Metrics (Last 24h):[/bold]")
    metrics_info = [
        "• Requests: 145,234",
        "• Avg Response Time: 245ms",
        "• Error Rate: 0.02%",
        "• CPU Usage: 45%",
        "• Memory Usage: 62%",
    ]

    for metric in metrics_info:
        console.print(f"  {metric}")


def rollback_command(name: str):
    """Rollback deployment to previous version."""

    environments = get_deployment_environments()

    if name not in environments:
        console.print(f"Environment '{name}' not found")
        raise typer.Exit(1)

    env_info = get_environment_info(name)
    versions = env_info.get("version_history", [])

    if len(versions) < 2:
        console.print("No previous versions available for rollback")
        raise typer.Exit(1)

    # Show available versions (excluding current)
    previous_versions = [v for v in versions if not v.get("is_current")]

    if not previous_versions:
        console.print("No previous versions available for rollback")
        raise typer.Exit(1)

    try:
        version_choices = [
            f"{v['version']} - {v.get('description', 'No description')}"
            for v in previous_versions[:5]
        ]

        selected = questionary.select(
            "Select version to rollback to:", choices=version_choices
        ).ask()

        if not selected:
            console.print("Rollback cancelled")
            raise typer.Exit(1)

        target_version = selected.split(" - ")[0]

        # Confirmation
        confirmed = questionary.confirm(
            f"Rollback environment '{name}' to version {target_version}?"
        ).ask()

        if not confirmed:
            console.print("Rollback cancelled")
            raise typer.Exit(1)

    except KeyboardInterrupt:
        console.print("\nRollback cancelled")
        raise typer.Exit(1)

    # Perform rollback
    with console.status(f"Rolling back to {target_version}..."):
        rollback_deployment(name, target_version)

    console.print(f"Rolled back to version {target_version}")
    console.print(f"Environment '{name}' is now running the previous version.")


def remove_command(name: str):
    """Remove deployment environment."""

    environments = get_deployment_environments()

    if name not in environments:
        console.print(f"Environment '{name}' not found")
        raise typer.Exit(1)

    env_info = get_environment_info(name)

    # Show removal preview
    preview_content = f"Environment: {name}\n"
    preview_content += f"Status: {env_info.get('status', 'unknown')}\n"
    preview_content += f"URL: {env_info.get('url', 'N/A')}\n"
    preview_content += f"Current Version: {env_info.get('current_version', 'N/A')}\n\n"
    preview_content += "⚠️  This will permanently remove:\n"
    preview_content += "  • All deployment history\n"
    preview_content += "  • All associated resources\n"
    preview_content += "  • Environment configuration\n"
    preview_content += "  • Access URLs\n\n"
    preview_content += "🚨 This action cannot be undone!"

    console.print(Panel(preview_content, title="⚠️  Removal Preview", expand=False))

    try:
        # Double confirmation for safety
        confirmed = questionary.confirm(
            f"Are you sure you want to remove environment '{name}'?"
        ).ask()

        if not confirmed:
            console.print("Removal cancelled")
            raise typer.Exit(1)

        # Type confirmation
        typed_name = questionary.text(f"Type '{name}' to confirm removal:").ask()

        if typed_name != name:
            console.print("Confirmation failed - names do not match")
            raise typer.Exit(1)

    except KeyboardInterrupt:
        console.print("\nRemoval cancelled")
        raise typer.Exit(1)

    # Remove environment
    with console.status(f"Removing environment '{name}'..."):
        remove_deployment_environment(name)

    console.print(f"Environment '{name}' removed successfully")

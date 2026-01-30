"""Deployment environment management commands."""

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from pathlib import Path
import questionary
import asyncio

from ..utils.deployment import (
    get_deployment_environments,
    create_deployment_environment,
    remove_deployment_environment,
    deploy_to_environment,
    rollback_deployment,
    get_environment_info,
)

from ..utils.app import discover_flash_project

from tetra_rp.core.resources.app import FlashApp

console = Console()


def _get_resource_manager():
    from tetra_rp.core.resources.resource_manager import ResourceManager

    return ResourceManager()


async def _undeploy_environment_resources(env_name: str, env: dict) -> None:
    """Undeploy resources tied to a flash environment before deletion."""
    endpoints = env.get("endpoints") or []
    network_volumes = env.get("networkVolumes") or []

    if not endpoints and not network_volumes:
        return

    manager = _get_resource_manager()
    failures = []
    undeployed = 0
    seen_resource_ids = set()

    with console.status(f"Undeploying resources for '{env_name}'..."):
        for label, items in (
            ("Endpoint", endpoints),
            ("Network volume", network_volumes),
        ):
            for item in items:
                provider_id = item.get("id") if isinstance(item, dict) else None
                name = item.get("name") if isinstance(item, dict) else None
                if not provider_id:
                    failures.append(f"{label} missing id in environment '{env_name}'")
                    continue

                matches = manager.find_resources_by_provider_id(provider_id)
                if not matches:
                    display_name = name if name else provider_id
                    failures.append(
                        f"{label} '{display_name}' ({provider_id}) not found in local tracking"
                    )
                    continue

                for resource_id, resource in matches:
                    if resource_id in seen_resource_ids:
                        continue
                    seen_resource_ids.add(resource_id)
                    resource_name = getattr(resource, "name", name) or provider_id
                    result = await manager.undeploy_resource(resource_id, resource_name)
                    if result.get("success"):
                        undeployed += 1
                    else:
                        failures.append(
                            result.get(
                                "message",
                                f"Failed to undeploy {label.lower()} '{resource_name}'",
                            )
                        )

    if failures:
        console.print(
            "❌ Failed to undeploy all resources; environment deletion aborted."
        )
        for message in failures:
            console.print(f"  • {message}")
        raise typer.Exit(1)

    if undeployed:
        console.print(f"✅ Undeployed {undeployed} resource(s) for '{env_name}'")


def list_command(
    app_name: str | None = typer.Option(
        None, "--app-name", "-a", help="flash app name to inspect"
    ),
):
    """Show available deployment environments."""
    if not app_name:
        _, app_name = discover_flash_project()
    asyncio.run(list_flash_environments(app_name))


async def new_flash_deployment_environment(app_name: str, env_name: str):
    """
    Create a new flash deployment environment. Creates a flash app if it doesn't already exist.
    """
    app, env = await FlashApp.create_environment_and_app(app_name, env_name)

    panel_content = (
        f"Environment '[bold]{env_name}[/bold]' created successfully\n\n"
        f"App: {app_name}\n"
        f"Environment ID: {env.get('id')}\n"
        f"Status: {env.get('state', 'PENDING')}"
    )
    console.print(Panel(panel_content, title="✅ Environment Created", expand=False))

    table = Table(show_header=True, header_style="bold")
    table.add_column("Name", style="bold")
    table.add_column("ID", overflow="fold")
    table.add_column("Status", overflow="fold")
    table.add_column("Created At", overflow="fold")

    table.add_row(
        env.get("name"),
        env.get("id"),
        env.get("state", "PENDING"),
        env.get("createdAt", "Just now"),
    )
    console.print(table)

    console.print(f"\nNext: [bold]flash deploy send {env_name}[/bold]")


async def info_flash_environment(app_name: str, env_name: str):
    """
    Get detailed information about a flash deployment environment.
    """
    app = await FlashApp.from_name(app_name)
    env = await app.get_environment_by_name(env_name)

    main_info = f"Environment: {env.get('name')}\n"
    main_info += f"ID: {env.get('id')}\n"
    main_info += f"State: {env.get('state', 'UNKNOWN')}\n"
    main_info += f"Active Build: {env.get('activeBuildId', 'None')}\n"

    if env.get("createdAt"):
        main_info += f"Created: {env.get('createdAt')}\n"

    console.print(Panel(main_info, title=f"📊 Environment: {env_name}", expand=False))

    endpoints = env.get("endpoints") or []
    if endpoints:
        endpoint_table = Table(title="Associated Endpoints")
        endpoint_table.add_column("Name", style="cyan")
        endpoint_table.add_column("ID", overflow="fold")

        for endpoint in endpoints:
            endpoint_table.add_row(
                endpoint.get("name", "—"),
                endpoint.get("id", "—"),
            )
        console.print(endpoint_table)

    network_volumes = env.get("networkVolumes") or []
    if network_volumes:
        nv_table = Table(title="Associated Network Volumes")
        nv_table.add_column("Name", style="cyan")
        nv_table.add_column("ID", overflow="fold")

        for nv in network_volumes:
            nv_table.add_row(
                nv.get("name", "—"),
                nv.get("id", "—"),
            )
        console.print(nv_table)


async def list_flash_environments(app_name: str):
    app = await FlashApp.from_name(app_name)
    envs = await app.list_environments()

    if not envs:
        console.print(f"No environments found for '{app_name}'.")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("Name", style="bold")
    table.add_column("ID", overflow="fold")
    table.add_column("Active Build", overflow="fold")
    table.add_column("Created At", overflow="fold")

    for env in envs:
        table.add_row(
            env.get("name"),
            env.get("id"),
            env.get("activeBuildId", "-"),
            env.get("createdAt"),
        )

    console.print(table)


def new_command(
    app_name: str | None = typer.Option(
        None, "--app-name", "-a", help="Flash app name to create a new environment in"
    ),
    name: str = typer.Argument(
        ..., help="Name of the deployment environment to create"
    ),
):
    """Create a new deployment environment."""
    if not app_name:
        _, app_name = discover_flash_project()
    assert app_name is not None
    asyncio.run(new_flash_deployment_environment(app_name, name))
    return

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


def send_command(
    env_name: str = typer.Argument(..., help="Name of the deployment environment"),
    app_name: str = typer.Option(None, "--app-name", "-a", help="Flash app name"),
):
    """Deploy project to deployment environment."""

    if not app_name:
        _, app_name = discover_flash_project()

    build_path = Path(".flash/archive.tar.gz")
    if not build_path.exists():
        console.print(
            "no build path found in current directory. Build your project with flash build first"
        )
        raise typer.Exit(1)

    console.print(f"🚀 Deploying to '[bold]{env_name}[/bold]'...")

    try:
        asyncio.run(deploy_to_environment(app_name, env_name, build_path))

        panel_content = f"Deployed to '[bold]{env_name}[/bold]' successfully\n\n"

        console.print(Panel(panel_content, title="Deployment Complete", expand=False))

    except Exception as e:
        console.print(f"Deployment failed: {e}")
        raise typer.Exit(1)


def info_command(
    env_name: str = typer.Argument(..., help="Name of the deployment environment"),
    app_name: str = typer.Option(None, "--app-name", "-a", help="Flash app name"),
):
    """Show detailed information about a deployment environment."""
    if not app_name:
        _, app_name = discover_flash_project()
    asyncio.run(info_flash_environment(app_name, env_name))


async def _fetch_environment_info(app_name: str, env_name: str) -> dict:
    """Fetch environment information for display.

    Args:
        app_name: Flash application name
        env_name: Environment name to fetch

    Returns:
        Environment dictionary with id, name, activeBuildId, etc.

    Raises:
        Exception: If environment doesn't exist or API call fails
    """
    app = await FlashApp.from_name(app_name)
    env = await app.get_environment_by_name(env_name)
    return env


async def delete_flash_environment(app_name: str, env_name: str):
    """Delete a flash deployment environment.

    Note: User confirmation should be handled by caller before calling this function.
    This function only performs the deletion operation.

    This design ensures questionary prompts run in sync context, avoiding
    event loop conflicts between asyncio.run() and prompt_toolkit's Application.run().

    Args:
        app_name: Flash application name
        env_name: Environment name to delete

    Raises:
        typer.Exit: If deletion fails
    """
    app = await FlashApp.from_name(app_name)
    env = await app.get_environment_by_name(env_name)

    await _undeploy_environment_resources(env_name, env)

    with console.status(f"Deleting environment '{env_name}'..."):
        success = await app.delete_environment(env_name)

    if success:
        console.print(f"✅ Environment '{env_name}' deleted successfully")
    else:
        console.print(f"❌ Failed to delete environment '{env_name}'")
        raise typer.Exit(1)


def delete_command(
    env_name: str = typer.Argument(
        ..., help="Name of the deployment environment to delete"
    ),
    app_name: str = typer.Option(None, "--app-name", "-a", help="Flash app name"),
):
    """Delete a deployment environment."""
    if not app_name:
        _, app_name = discover_flash_project()

    # Fetch environment info in async context for display
    try:
        env = asyncio.run(_fetch_environment_info(app_name, env_name))
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to fetch environment info: {e}")
        raise typer.Exit(1)

    # Display deletion preview in sync context
    panel_content = (
        f"Environment '[bold]{env_name}[/bold]' will be deleted\n\n"
        f"Environment ID: {env.get('id')}\n"
        f"App: {app_name}\n"
        f"Active Build: {env.get('activeBuildId', 'None')}"
    )
    console.print(Panel(panel_content, title="⚠️  Delete Confirmation", expand=False))

    # Get user confirmation in sync context (BEFORE asyncio.run for deletion)
    try:
        confirmed = questionary.confirm(
            f"Are you sure you want to delete environment '{env_name}'? This will delete all resources associated with this environment!"
        ).ask()

        if not confirmed:
            console.print("Deletion cancelled")
            raise typer.Exit(0)
    except KeyboardInterrupt:
        console.print("\nDeletion cancelled")
        raise typer.Exit(0)

    # Perform async deletion after confirmation
    asyncio.run(delete_flash_environment(app_name, env_name))


def report_command(
    name: str = typer.Argument(..., help="Name of the deployment environment"),
):
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


def rollback_command(
    name: str = typer.Argument(..., help="Name of the deployment environment"),
):
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


def remove_command(
    name: str = typer.Argument(
        ..., help="Name of the deployment environment to remove"
    ),
):
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

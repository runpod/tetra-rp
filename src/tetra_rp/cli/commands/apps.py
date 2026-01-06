"""Deployment environment management commands."""

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
import questionary
import asyncio

from tetra_rp.cli.utils.app import discover_flash_project

from ..utils.deployment import (
    get_deployment_environments,
    create_deployment_environment,
    remove_deployment_environment,
    deploy_to_environment,
    rollback_deployment,
    get_environment_info,
)

from tetra_rp.core.resources.app import FlashApp

console = Console()

apps_app = typer.Typer(short_help="Manage existing apps", name="app")

@apps_app.command("ls", short_help="List existing apps under your account.")
@apps_app.command("list", short_help="List existing apps under your account.")
def ls():
    return asyncio.run(list_flash_apps())

@apps_app.command("delete", short_help="Delete an existing flash app and all its associated resources")
def delete(
        app_name: str = typer.Option(..., "--app-name", "-a", help="Flash app name to delete")
        ):
    if not app_name:
        _, app_name = discover_flash_project()
    return asyncio.run(delete_flash_app(app_name))

async def list_flash_apps():
    apps = await FlashApp.list()
    if not apps:
        console.print("No Flash apps found.")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("Name", style="bold")
    table.add_column("ID", overflow="fold")
    table.add_column("Environments", overflow="fold")
    table.add_column("Builds", overflow="fold")

    for app in apps:
        environments = app.get("flashEnvironments") or []
        env_summary = ", ".join(env.get("name", "?") for env in environments) or "—"
        builds = app.get("flashBuilds") or []
        build_summary = ", ".join(build.get("id", "?") for build in builds) or "—"
        table.add_row(
            app.get("name", "(unnamed)"), app.get("id", "—"), env_summary, build_summary
        )

    console.print(table)

async def delete_flash_app(app_name: str):
    with console.status(f"deleting app: {app_name}"):
        await FlashApp.delete(app_name)

@apps_app.callback(invoke_without_command=True)
def apps(ctx: typer.Context) -> None:
  if ctx.invoked_subcommand is None:
      typer.echo(ctx.command.get_help(ctx))
      raise typer.Exit()


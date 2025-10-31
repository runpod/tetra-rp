"""Flash deploy command - Deploy Flash project to production."""
import asyncio
import json
from pathlib import Path
from typing import Optional

from tetra_rp import FlashApp

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

console = Console()
ls_app = typer.Typer()

# flash ls 
# flash ls envs --app-name
# flash ls builds --app-name

@ls_app.callback(invoke_without_command=True)
def list_callback(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        asyncio.run(list_flash_apps())

@ls_app.command("ls")
def ls():
    return asyncio.run(list_flash_apps())

@ls_app.command()
def envs(
    app_name: str = typer.Option(..., "--app-name", "-a", help="Flash app name to inspect"),
):
    return asyncio.run(list_flash_environments(app_name))

@ls_app.command()
def builds(
    app_name: str = typer.Option(..., "--app-name", "-a", help="Flash app name to inspect"),
):
    return asyncio.run(list_flash_builds(app_name))


async def list_flash_builds(app_name: str):
    app = await FlashApp.from_name(app_name)
    builds = await app.list_builds()
    
    if not builds:
        console.print(f"No builds found for '{app_name}'")


    table = Table(show_header=True, header_style="bold")
    table.add_column("ID", overflow="fold")
    table.add_column("Object Key", overflow="fold")
    table.add_column("Created At", overflow="fold")

    for build in builds:
        table.add_row(build.get("id"), build.get("objectKey"), build.get("createdAt"))
    console.print(table)

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
        table.add_row(app.get("name", "(unnamed)"), app.get("id", "—"), env_summary, build_summary)

    console.print(table)

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
        table.add_row(env.get("name"), env.get("id"), env.get("activeBuildId", "-"), env.get("createdAt"))

    console.print(table)

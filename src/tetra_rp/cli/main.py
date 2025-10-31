"""Main CLI entry point for Flash CLI."""

import typer
from importlib import metadata
from rich.console import Console
from rich.panel import Panel

from .commands import (
    init,
    run,
    build,
    resource,
    deploy,
)


def get_version() -> str:
    """Get the package version from metadata."""
    try:
        return metadata.version("tetra_rp")
    except metadata.PackageNotFoundError:
        return "unknown"


console = Console()

# command: flash
app = typer.Typer(
    name="flash",
    help="Runpod Flash CLI - Distributed inference and serving framework",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

# command: flash <command>
app.command("init")(init.init_command)
app.command("run")(run.run_command)
app.command("build")(build.build_command)
app.command("report")(resource.report_command)
app.command("clean")(resource.clean_command)

# command: flash deploy
deploy_app = typer.Typer(
    name="deploy",
    help="Deployment environment management commands",
    no_args_is_help=True,
)

# command: flash deploy *
deploy_app.command("list")(deploy.list_command)
deploy_app.command("new")(deploy.new_command)
deploy_app.command("send")(deploy.send_command)
deploy_app.command("report")(deploy.report_command)
deploy_app.command("rollback")(deploy.rollback_command)
deploy_app.command("remove")(deploy.remove_command)

app.add_typer(deploy_app, name="deploy")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-v", help="Show version"),
):
    """Runpod Flash CLI - Distributed inference and serving framework."""
    if version:
        console.print(f"Runpod Flash CLI v{get_version()}")
        raise typer.Exit()

    if ctx.invoked_subcommand is None:
        console.print(
            Panel(
                "[bold blue]Runpod Flash CLI[/bold blue]\n\n"
                "A framework for distributed inference and serving of ML models.\n\n"
                "Use [bold]flash --help[/bold] to see available commands.",
                title="Welcome",
                expand=False,
            )
        )


if __name__ == "__main__":
    app()

"""Main CLI entry point for Flash CLI."""

import typer
from importlib import metadata
from rich.console import Console
from rich.panel import Panel

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


@app.command("init")
def init_cmd(
    project_name: str = typer.Argument(None, help="Project name (defaults to current directory)"),
    no_env: bool = typer.Option(False, "--no-env", help="Skip conda environment creation"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing files"),
):
    """Create new Flash project with Flash Server and GPU workers."""
    from .commands.init import init_command
    return init_command(project_name, no_env, force)


@app.command("run")
def run_cmd(
    host: str = typer.Option("0.0.0.0", help="Host to bind to"),
    port: int = typer.Option(8000, help="Port to bind to"),
    reload: bool = typer.Option(False, help="Enable auto-reload on code changes"),
):
    """Start local Flash development server."""
    from .commands.run import run_command
    return run_command(host, port, reload)


@app.command("build")
def build_cmd(
    output_dir: str = typer.Option("dist", help="Output directory for build artifacts"),
    clean: bool = typer.Option(False, help="Clean output directory before building"),
):
    """Build Flash application for deployment."""
    from .commands.build import build_command
    return build_command(output_dir, clean)


@app.command("report")
def report_cmd():
    """Show status of all deployed resources."""
    from .commands.resource import report_command
    return report_command()


@app.command("clean")
def clean_cmd(
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
):
    """Remove all tracked resources."""
    from .commands.resource import clean_command
    return clean_command(force)

# command: flash deploy
deploy_app = typer.Typer(
    name="deploy",
    help="Deployment environment management commands",
    no_args_is_help=True,
)

# command: flash deploy *


@deploy_app.command("list")
def deploy_list_cmd():
    """Show available deployment environments."""
    from .commands.deploy import list_command
    return list_command()


@deploy_app.command("new")
def deploy_new_cmd(name: str = typer.Argument(..., help="Environment name")):
    """Create a new deployment environment."""
    from .commands.deploy import new_command
    return new_command(name)


@deploy_app.command("send")
def deploy_send_cmd(name: str = typer.Argument(..., help="Environment name")):
    """Deploy project to deployment environment."""
    from .commands.deploy import send_command
    return send_command(name)


@deploy_app.command("report")
def deploy_report_cmd(name: str = typer.Argument(..., help="Environment name")):
    """Show detailed environment status and metrics."""
    from .commands.deploy import report_command
    return report_command(name)


@deploy_app.command("rollback")
def deploy_rollback_cmd(name: str = typer.Argument(..., help="Environment name")):
    """Rollback deployment to previous version."""
    from .commands.deploy import rollback_command
    return rollback_command(name)


@deploy_app.command("remove")
def deploy_remove_cmd(name: str = typer.Argument(..., help="Environment name")):
    """Remove deployment environment."""
    from .commands.deploy import remove_command
    return remove_command(name)

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

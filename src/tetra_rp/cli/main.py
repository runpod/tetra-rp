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

# command: tetra
app = typer.Typer(
    name="tetra",
    help="Tetra RP CLI - Distributed inference and serving framework",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-v", help="Show version"),
):
    """Tetra RP CLI - Distributed inference and serving framework."""
    if version:
        console.print(f"Tetra RP CLI v{get_version()}")
        raise typer.Exit()

    if ctx.invoked_subcommand is None:
        console.print(
            Panel(
                "[bold blue]Tetra RP CLI[/bold blue]\n\n"
                "A framework for distributed inference and serving of ML models.\n\n"
                "Use [bold]tetra --help[/bold] to see available commands.",
                title="Welcome",
                expand=False,
            )
        )


if __name__ == "__main__":
    app()

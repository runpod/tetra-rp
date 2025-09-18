"""Execute main entry point command."""

import asyncio
import sys
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel

from tetra_rp.config import get_paths

console = Console()


def run_command(
    entry_point: Optional[str] = typer.Option(
        None, "--entry", "-e", help="Entry point file to execute"
    ),
    no_deploy: bool = typer.Option(
        False, "--no-deploy", help="Skip resource deployment"
    ),
):
    """Execute the main entry point of the app."""

    # Discover entry point if not provided
    if not entry_point:
        entry_point = discover_entry_point()
        if not entry_point:
            console.print("No entry point found")
            console.print("Specify entry point with --entry or create main.py")
            raise typer.Exit(1)

    # Validate entry point exists
    entry_path = Path(entry_point)
    if not entry_path.exists():
        console.print(f"Entry point not found: {entry_point}")
        raise typer.Exit(1)

    console.print(f"🚀 Executing entry point: [bold]{entry_point}[/bold]")

    # Run the entry point
    try:
        asyncio.run(execute_entry_point(entry_path, no_deploy))
    except KeyboardInterrupt:
        console.print("\nExecution interrupted by user")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"Execution failed: {e}")
        raise typer.Exit(1)


def discover_entry_point() -> Optional[str]:
    """Discover the main entry point file."""
    # Check common entry point names
    candidates = ["main.py", "app.py", "run.py", "__main__.py"]

    for candidate in candidates:
        if Path(candidate).exists():
            return candidate

    # Check for .tetra/config.json entry point
    paths = get_paths()
    config_path = paths.config_file
    if config_path.exists():
        try:
            import json

            with open(config_path) as f:
                config = json.load(f)
            return config.get("entry_point")
        except (json.JSONDecodeError, KeyError):
            pass

    return None


async def execute_entry_point(entry_path: Path, no_deploy: bool = False):
    """Execute the entry point with progress tracking."""

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        if not no_deploy:
            # Deployment phase
            deploy_task = progress.add_task("Preparing resources...", total=None)
            await asyncio.sleep(1)  # Mock deployment time
            progress.update(deploy_task, description="Resources ready")
            progress.stop_task(deploy_task)

        # Execution phase
        exec_task = progress.add_task("Executing...", total=None)

        # Execute the Python file
        try:
            # Import and run the module
            spec = __import__("importlib.util").util.spec_from_file_location(
                entry_path.stem, entry_path
            )
            module = __import__("importlib.util").util.module_from_spec(spec)

            # Add the directory to sys.path so imports work
            sys.path.insert(0, str(entry_path.parent))

            spec.loader.exec_module(module)

            progress.update(exec_task, description="Complete!")
            await asyncio.sleep(0.5)  # Brief pause to show completion

        except Exception as e:
            progress.update(exec_task, description=f"Failed: {e}")
            raise
        finally:
            progress.stop_task(exec_task)

    # Success message
    console.print(
        Panel("Execution completed successfully", title="Success", expand=False)
    )

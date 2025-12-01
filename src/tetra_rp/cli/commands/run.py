"""Run Flash development server."""

import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

console = Console()


def run_command(
    host: str = typer.Option("localhost", "--host", help="Host to bind to"),
    port: int = typer.Option(8888, "--port", "-p", help="Port to bind to"),
    reload: bool = typer.Option(
        True, "--reload/--no-reload", help="Enable auto-reload"
    ),
):
    """Run Flash development server with uvicorn."""

    # Discover entry point
    entry_point = discover_entry_point()
    if not entry_point:
        console.print("[red]Error:[/red] No entry point found")
        console.print("Create main.py with a FastAPI app")
        raise typer.Exit(1)

    # Check if entry point has FastAPI app
    app_location = check_fastapi_app(entry_point)
    if not app_location:
        console.print(f"[red]Error:[/red] No FastAPI app found in {entry_point}")
        console.print("Make sure your main.py contains: app = FastAPI()")
        raise typer.Exit(1)

    console.print("[green]Starting Flash Server[/green]")
    console.print(f"Entry point: [bold]{app_location}[/bold]")
    console.print(f"Server: [bold]http://{host}:{port}[/bold]")
    console.print(f"Auto-reload: [bold]{'enabled' if reload else 'disabled'}[/bold]")
    console.print("\nPress CTRL+C to stop\n")

    # Build uvicorn command
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        app_location,
        "--host",
        host,
        "--port",
        str(port),
    ]

    if reload:
        cmd.append("--reload")

    # Run uvicorn with proper process group handling
    process = None
    try:
        # Create new process group to ensure all child processes can be killed together
        # On Unix systems, use process group; on Windows, CREATE_NEW_PROCESS_GROUP
        if sys.platform == "win32":
            process = subprocess.Popen(
                cmd, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )
        else:
            process = subprocess.Popen(cmd, preexec_fn=os.setsid)

        # Wait for process to complete
        process.wait()

    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping server and cleaning up processes...[/yellow]")

        # Kill the entire process group to ensure all child processes are terminated
        if process:
            try:
                if sys.platform == "win32":
                    # Windows: send CTRL_BREAK_EVENT to process group
                    process.send_signal(signal.CTRL_BREAK_EVENT)
                    process.terminate()
                else:
                    # Unix: kill entire process group
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)

                # Wait briefly for graceful shutdown
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    # Force kill if didn't terminate gracefully
                    if sys.platform == "win32":
                        process.kill()
                    else:
                        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                    process.wait()

            except (ProcessLookupError, OSError):
                # Process already terminated
                pass

        console.print("[green]Server stopped[/green]")
        raise typer.Exit(0)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        if process:
            try:
                if sys.platform == "win32":
                    process.terminate()
                else:
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            except (ProcessLookupError, OSError):
                pass
        raise typer.Exit(1)


def discover_entry_point() -> Optional[str]:
    """Discover the main entry point file."""
    candidates = ["main.py", "app.py", "server.py"]

    for candidate in candidates:
        if Path(candidate).exists():
            return candidate

    return None


def check_fastapi_app(entry_point: str) -> Optional[str]:
    """
    Check if entry point has a FastAPI app and return the app location.

    Returns:
        App location in format "module:app" or None
    """
    try:
        # Read the file
        content = Path(entry_point).read_text()

        # Check for FastAPI app
        if "app = FastAPI(" in content or "app=FastAPI(" in content:
            # Extract module name from file path
            module = entry_point.replace(".py", "").replace("/", ".")
            return f"{module}:app"

        return None

    except Exception:
        return None

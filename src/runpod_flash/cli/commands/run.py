"""Run Flash development server."""

import logging
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Optional

import questionary
import typer
from rich.console import Console

logger = logging.getLogger(__name__)
console = Console()


def run_command(
    host: str = typer.Option(
        "localhost",
        "--host",
        envvar="FLASH_HOST",
        help="Host to bind to (env: FLASH_HOST)",
    ),
    port: int = typer.Option(
        8888,
        "--port",
        "-p",
        envvar="FLASH_PORT",
        help="Port to bind to (env: FLASH_PORT)",
    ),
    reload: bool = typer.Option(
        True, "--reload/--no-reload", help="Enable auto-reload"
    ),
    auto_provision: bool = typer.Option(
        False,
        "--auto-provision",
        help="Auto-provision deployable resources on startup",
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

    # Set flag for all flash run sessions to ensure both auto-provisioned
    # and on-the-fly provisioned resources get the live- prefix
    if not _is_reload():
        os.environ["FLASH_IS_LIVE_PROVISIONING"] = "true"

    # Auto-provision resources if flag is set and not a reload
    if auto_provision and not _is_reload():
        try:
            resources = _discover_resources(entry_point)

            if resources:
                # If many resources found, ask for confirmation
                if len(resources) > 5:
                    if not _confirm_large_provisioning(resources):
                        console.print("[yellow]Auto-provisioning cancelled[/yellow]\n")
                    else:
                        _provision_resources(resources)
                else:
                    _provision_resources(resources)
        except Exception as e:
            logger.error("Auto-provisioning failed", exc_info=True)
            console.print(
                f"[yellow]Warning:[/yellow] Resource provisioning failed: {e}"
            )
            console.print(
                "[yellow]Note:[/yellow] Resources will be deployed on-demand when first called"
            )

    console.print("\n[green]Starting Flash Server[/green]")
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
        "--log-level",
        "warning",
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
                    # Windows: terminate the process
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


def _is_reload() -> bool:
    """Check if running in uvicorn reload subprocess.

    Returns:
        True if running in a reload subprocess
    """
    return "UVICORN_RELOADER_PID" in os.environ


def _discover_resources(entry_point: str):
    """Discover deployable resources in entry point.

    Args:
        entry_point: Path to entry point file

    Returns:
        List of discovered DeployableResource instances
    """
    from ...core.discovery import ResourceDiscovery

    try:
        discovery = ResourceDiscovery(entry_point, max_depth=2)
        resources = discovery.discover()

        # Debug: Log what was discovered
        if resources:
            console.print(f"\n[dim]Discovered {len(resources)} resource(s):[/dim]")
            for res in resources:
                res_name = getattr(res, "name", "Unknown")
                res_type = res.__class__.__name__
                console.print(f"  [dim]• {res_name} ({res_type})[/dim]")
            console.print()

        return resources
    except Exception as e:
        console.print(f"[yellow]Warning:[/yellow] Resource discovery failed: {e}")
        return []


def _confirm_large_provisioning(resources) -> bool:
    """Show resources and prompt user for confirmation.

    Args:
        resources: List of resources to provision

    Returns:
        True if user confirms, False otherwise
    """
    try:
        console.print(
            f"\n[yellow]Found {len(resources)} resources to provision:[/yellow]"
        )

        for resource in resources:
            name = getattr(resource, "name", "Unknown")
            resource_type = resource.__class__.__name__
            console.print(f"  • {name} ({resource_type})")

        console.print()

        confirmed = questionary.confirm(
            "This may take several minutes. Do you want to proceed?"
        ).ask()

        return confirmed if confirmed is not None else False

    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]Cancelled[/yellow]")
        return False
    except Exception as e:
        console.print(f"[yellow]Warning:[/yellow] Confirmation failed: {e}")
        return False


def _provision_resources(resources):
    """Provision resources and wait for completion.

    Args:
        resources: List of resources to provision
    """
    import asyncio
    from ...core.deployment import DeploymentOrchestrator

    try:
        console.print(f"\n[bold]Provisioning {len(resources)} resource(s)...[/bold]")
        orchestrator = DeploymentOrchestrator(max_concurrent=3)

        # Run provisioning with progress shown
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(orchestrator.deploy_all(resources, show_progress=True))
        loop.close()

    except Exception as e:
        console.print(f"[yellow]Warning:[/yellow] Provisioning failed: {e}")

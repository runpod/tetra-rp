"""Flash deploy command - Deploy Flash project to production."""

import asyncio
import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


def deploy_flash_command(
    project_dir: Optional[Path] = typer.Option(
        None, "--dir", "-d", help="Project directory (default: current directory)"
    ),
):
    """
    Deploy Flash project to RunPod.

    Deploys Flash Server (CPU) with Load Balancer endpoint.
    GPU workers auto-deploy on first request to @remote endpoints.

    Examples:
      flash deploy              # Deploy to production
      flash deploy --dir ./app  # Deploy from specific directory
    """
    # Resolve project directory
    if project_dir is None:
        project_dir = Path.cwd()
    else:
        project_dir = Path(project_dir).resolve()

    # Check for build artifacts
    artifacts_file = project_dir / ".tetra" / "build_artifacts.json"
    if not artifacts_file.exists():
        console.print(
            "[red]Error:[/red] Build artifacts not found. Run [bold]flash build[/bold] first."
        )
        raise typer.Exit(1)

    # Load build artifacts
    try:
        artifacts = json.loads(artifacts_file.read_text())
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to read build artifacts: {e}")
        raise typer.Exit(1)

    # Display deployment configuration
    _display_deploy_config(artifacts)

    # Run deployment
    try:
        asyncio.run(_execute_deployment(artifacts, project_dir))
    except KeyboardInterrupt:
        console.print("\n[yellow]Deployment cancelled by user[/yellow]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"\n[red]Deployment failed:[/red] {e}")
        import traceback

        console.print(traceback.format_exc())
        raise typer.Exit(1)


def _display_deploy_config(artifacts: dict):
    """Display deployment configuration."""
    project_name = artifacts.get("project_name", "unknown")
    worker_count = len(artifacts.get("workers", []))

    console.print(
        Panel(
            f"[bold]Project:[/bold] {project_name}\n"
            f"[bold]Flash Server:[/bold] {artifacts['flash_server']['base_image']}\n"
            f"[bold]GPU Workers:[/bold] {worker_count} worker(s)\n"
            f"[bold]Build Time:[/bold] {artifacts.get('build_time', 'unknown')}",
            title="Flash Deployment Configuration",
            expand=False,
        )
    )


async def _execute_deployment(artifacts: dict, project_dir: Path):
    """Execute deployment process."""
    from tetra_rp.core.resources import CpuLiveServerless, ServerlessType

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # Deploy Flash Server
        server_task = progress.add_task("[green]Deploying to RunPod...")

        try:
            flash_server_config = artifacts["flash_server"]

            # Create CPU Live Serverless with Load Balancer type
            import os

            endpoint = CpuLiveServerless(
                name=f"{artifacts['project_name']}-flash-server",
                imageName=flash_server_config["base_image"],
                env={
                    # Enable production mode for GPU worker deployment
                    "TETRA_PROD_MODE": "true",
                    # Flash Server baked mode configuration
                    "TETRA_BAKED_MODE": "true",
                    "TETRA_CODE_TARBALL": flash_server_config["tarball_s3_key"],
                    # Network volume configuration for GPU workers
                    "RUNPOD_VOLUME_ID": os.getenv("RUNPOD_VOLUME_ID", ""),
                    "RUNPOD_VOLUME_ENDPOINT": os.getenv("RUNPOD_VOLUME_ENDPOINT", ""),
                    "RUNPOD_VOLUME_ACCESS_KEY": os.getenv(
                        "RUNPOD_VOLUME_ACCESS_KEY", ""
                    ),
                    "RUNPOD_VOLUME_SECRET_KEY": os.getenv(
                        "RUNPOD_VOLUME_SECRET_KEY", ""
                    ),
                    "RUNPOD_VOLUME_BUCKET": os.getenv(
                        "RUNPOD_VOLUME_BUCKET", "tetra-code"
                    ),
                    # GPU worker image configuration
                    "TETRA_GPU_IMAGE": os.getenv(
                        "TETRA_GPU_IMAGE", "runpod/tetra-rp:latest"
                    ),
                    # RunPod API key for GPU worker deployment
                    "RUNPOD_API_KEY": os.getenv("RUNPOD_API_KEY", ""),
                },
                type=ServerlessType.LB,
                workersMin=1,
                workersMax=3,
                idleTimeout=30,
            )

            # Deploy endpoint
            deployed_endpoint = await endpoint.deploy()
            endpoint_id = deployed_endpoint.id

            progress.update(
                server_task,
                description="[green]✓ Deployed",
            )
            progress.stop_task(server_task)

        except Exception as e:
            progress.update(server_task, description=f"[red]✗ Failed: {e}")
            progress.stop_task(server_task)
            raise

    # Display deployment summary
    console.print("\n")
    _display_deployment_summary(artifacts, endpoint_id)


def _display_deployment_summary(artifacts: dict, endpoint_id: str):
    """Display deployment summary."""
    project_name = artifacts.get("project_name", "unknown")
    endpoint_url = f"https://{endpoint_id}.api.runpod.ai"
    worker_count = len(artifacts.get("workers", []))

    # Success panel
    console.print(
        Panel(
            f"[bold]{project_name}[/bold] deployed successfully!\n\n"
            f"[bold cyan]URL:[/bold cyan] {endpoint_url}",
            title="✓ Live",
            expand=False,
            border_style="green",
        )
    )

    # Test command
    console.print("\n[bold]Test your endpoint:[/bold]")
    console.print(f"[dim]curl {endpoint_url}/<your-endpoint>[/dim]")

    if worker_count > 0:
        console.print(
            f"\n[dim]GPU workers ({worker_count}) will deploy on first request[/dim]"
        )

"""Flash deploy command - build and deploy in one step."""

import asyncio
import logging
import shutil

import typer
from rich.console import Console
from rich.panel import Panel

from ..utils.app import discover_flash_project
from ..utils.deployment import deploy_to_environment
from .build import run_build

from runpod_flash.core.resources.app import FlashApp

logger = logging.getLogger(__name__)
console = Console()


def deploy_command(
    env_name: str | None = typer.Option(
        None, "--env", "-e", help="Target environment name"
    ),
    app_name: str | None = typer.Option(None, "--app", "-a", help="Flash app name"),
    no_deps: bool = typer.Option(
        False, "--no-deps", help="Skip transitive dependencies during pip install"
    ),
    exclude: str | None = typer.Option(
        None,
        "--exclude",
        help="Comma-separated packages to exclude (e.g., 'torch,torchvision')",
    ),
    use_local_flash: bool = typer.Option(
        False,
        "--use-local-flash",
        help="Bundle local runpod_flash source instead of PyPI version (for development/testing)",
    ),
    output_name: str | None = typer.Option(
        None, "--output", "-o", help="Custom archive name (default: artifact.tar.gz)"
    ),
    preview: bool = typer.Option(
        False,
        "--preview",
        help="Build and launch local preview environment instead of deploying",
    ),
):
    """
    Build and deploy Flash application.

    Builds the project and deploys to the target environment in one step.
    If only one environment exists, it is used automatically.

    Examples:
      flash deploy                              # build + deploy (auto-selects env)
      flash deploy --env staging                # build + deploy to staging
      flash deploy --app my-app --env prod      # deploy a different app
      flash deploy --preview                    # build + launch local preview
      flash deploy --exclude torch,torchvision  # exclude packages from build
    """
    try:
        project_dir, discovered_app_name = discover_flash_project()
        if not app_name:
            app_name = discovered_app_name

        archive_path = run_build(
            project_dir=project_dir,
            app_name=app_name,
            no_deps=no_deps,
            output_name=output_name,
            exclude=exclude,
            use_local_flash=use_local_flash,
        )

        if preview:
            _launch_preview(project_dir)
            return

        asyncio.run(_resolve_and_deploy(app_name, env_name, archive_path))

        build_dir = project_dir / ".flash" / ".build"
        if build_dir.exists():
            shutil.rmtree(build_dir)

    except KeyboardInterrupt:
        console.print("\n[yellow]Deploy cancelled by user[/yellow]")
        raise typer.Exit(1)
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"\n[red]Deploy failed:[/red] {e}")
        logger.exception("Deploy failed")
        raise typer.Exit(1)


def _launch_preview(project_dir):
    build_dir = project_dir / ".flash" / ".build"
    console.print("\n[bold cyan]Launching multi-container preview...[/bold cyan]")
    console.print("[dim]Starting all endpoints locally in Docker...[/dim]\n")

    try:
        from .preview import launch_preview

        manifest_path = project_dir / ".flash" / "flash_manifest.json"
        launch_preview(build_dir=build_dir, manifest_path=manifest_path)
    except KeyboardInterrupt:
        console.print("\n[yellow]Preview stopped by user[/yellow]")
    except Exception as e:
        console.print(f"[red]Preview error:[/red] {e}")
        logger.exception("Preview launch failed")
        raise typer.Exit(1)


async def _resolve_and_deploy(
    app_name: str, env_name: str | None, archive_path
) -> None:
    resolved_env_name = await _resolve_environment(app_name, env_name)

    console.print(f"\nDeploying to '[bold]{resolved_env_name}[/bold]'...")

    await deploy_to_environment(app_name, resolved_env_name, archive_path)

    console.print(
        Panel(
            f"Deployed to '[bold]{resolved_env_name}[/bold]' successfully\n\n"
            f"App: {app_name}",
            title="Deployment Complete",
            expand=False,
        )
    )


async def _resolve_environment(app_name: str, env_name: str | None) -> str:
    try:
        app = await FlashApp.from_name(app_name)
    except Exception as exc:
        if "app not found" not in str(exc).lower():
            raise
        target = env_name or "production"
        console.print(
            f"[dim]No app '{app_name}' found. Creating app and '{target}' environment...[/dim]"
        )
        await FlashApp.create_environment_and_app(app_name, target)
        return target

    if env_name:
        envs = await app.list_environments()
        existing = {e.get("name") for e in envs}
        if env_name not in existing:
            console.print(
                f"[dim]Environment '{env_name}' not found. Creating it...[/dim]"
            )
            await app.create_environment(env_name)
        return env_name

    envs = await app.list_environments()

    if len(envs) == 1:
        resolved = envs[0].get("name")
        console.print(f"[dim]Auto-selected environment: {resolved}[/dim]")
        return resolved

    if len(envs) == 0:
        console.print(
            "[dim]No environments found. Creating 'production' environment...[/dim]"
        )
        await app.create_environment("production")
        return "production"

    env_names = [e.get("name", "?") for e in envs]
    console.print(
        f"[red]Error:[/red] Multiple environments found: {', '.join(env_names)}\n"
        f"Please specify with [bold]--env <name>[/bold]"
    )
    raise typer.Exit(1)

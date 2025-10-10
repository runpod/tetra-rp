"""Flash build command - Build and package Flash Server and GPU workers for production."""

import ast
import asyncio
import importlib.util
import json
import os
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from tetra_rp.build.gpu_workers.strategies import TarballStrategyConfig
from tetra_rp.build.gpu_workers.strategies.tarball_strategy import TarballStrategy
from tetra_rp.build.shared.code_extractor import CodeExtractor

console = Console()


# Data classes for clean type safety
@dataclass
class WorkerArtifact:
    """Information about a built GPU worker."""

    name: str
    tarball_s3_key: str
    code_hash: str
    dependencies: List[str]
    system_dependencies: List[str]
    base_image: str


@dataclass
class FlashServerArtifact:
    """Information about built Flash Server."""

    tarball_s3_key: str
    base_image: str
    port: int


@dataclass
class BuildArtifacts:
    """Complete build artifacts for a Flash project."""

    project_name: str
    flash_server: FlashServerArtifact
    workers: List[WorkerArtifact]
    build_time: str


def build_command(
    project_dir: Optional[Path] = typer.Option(
        None, "--dir", "-d", help="Project directory (default: current directory)"
    ),
    name: Optional[str] = typer.Option(
        None, "--name", "-n", help="Project name (auto-detected if not provided)"
    ),
    upload_to_s3: bool = typer.Option(
        True, "--upload/--no-upload", help="Upload tarballs to S3/Network Volume"
    ),
    flash_server_only: bool = typer.Option(
        False, "--flash-server-only", help="Build only Flash Server (skip GPU workers)"
    ),
    workers_only: bool = typer.Option(
        False, "--workers-only", help="Build only GPU workers (skip Flash Server)"
    ),
):
    """
    Build Flash project for production deployment.

    Packages Flash Server and GPU workers, uploads to S3-compatible storage.

    Examples:
      flash build --upload        # Build and upload to S3
      flash build --no-upload     # Build locally only
      flash build --workers-only  # Build only GPU workers
    """
    # Validate options
    if flash_server_only and workers_only:
        console.print(
            "[red]Error:[/red] Cannot use --flash-server-only and --workers-only together"
        )
        raise typer.Exit(1)

    # Validate project structure
    project_dir = _resolve_project_dir(project_dir)
    name = name or project_dir.name
    _validate_project_structure(project_dir, flash_server_only)

    # Display configuration
    _display_build_config(name, project_dir, upload_to_s3)

    # Run build
    try:
        asyncio.run(
            _execute_build(
                project_dir=project_dir,
                name=name,
                upload_to_s3=upload_to_s3,
                build_flash_server=not workers_only,
                build_workers=not flash_server_only,
            )
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Build cancelled by user[/yellow]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"\n[red]Build failed:[/red] {e}")
        import traceback

        console.print(traceback.format_exc())
        raise typer.Exit(1)


def _resolve_project_dir(project_dir: Optional[Path]) -> Path:
    """Resolve and validate project directory."""
    if project_dir is None:
        project_dir = Path.cwd()
    else:
        project_dir = Path(project_dir).resolve()

    if not project_dir.exists():
        console.print(f"[red]Error:[/red] Directory not found: {project_dir}")
        raise typer.Exit(1)

    return project_dir


def _validate_project_structure(project_dir: Path, skip_workers: bool = False):
    """Validate Flash project structure."""
    main_py = project_dir / "main.py"
    workers_dir = project_dir / "workers"

    if not main_py.exists():
        console.print(f"[red]Error:[/red] main.py not found in {project_dir}")
        console.print("Run [bold]flash init[/bold] to create a Flash project")
        raise typer.Exit(1)

    if not skip_workers and not workers_dir.exists():
        console.print(
            f"[red]Error:[/red] workers/ directory not found in {project_dir}"
        )
        console.print("Run [bold]flash init[/bold] to create a Flash project")
        raise typer.Exit(1)


def _display_build_config(name: str, project_dir: Path, upload_to_s3: bool):
    """Display build configuration."""
    console.print(
        Panel(
            f"[bold]Project:[/bold] {name}\n"
            f"[bold]Directory:[/bold] {project_dir}\n"
            f"[bold]Strategy:[/bold] tarball (Network Volume)\n"
            f"[bold]Upload to S3:[/bold] {upload_to_s3}",
            title="Flash Build Configuration",
            expand=False,
        )
    )


async def _execute_build(
    project_dir: Path,
    name: str,
    upload_to_s3: bool,
    build_flash_server: bool,
    build_workers: bool,
):
    """Execute build process with progress tracking."""

    # Check S3 configuration if upload is requested
    if upload_to_s3:
        storage_endpoint = os.getenv("RUNPOD_S3_ENDPOINT")
        storage_bucket = os.getenv("RUNPOD_S3_BUCKET")

        if not storage_endpoint or not storage_bucket:
            console.print(
                "[yellow]Warning:[/yellow] S3 not configured (RUNPOD_S3_ENDPOINT, RUNPOD_S3_BUCKET). "
                "Building locally..."
            )
            upload_to_s3 = False

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        worker_artifacts = []
        flash_server_artifact = None

        # Build GPU Workers
        if build_workers:
            worker_artifacts = await _build_gpu_workers(
                progress, project_dir, name, upload_to_s3
            )

        # Build Flash Server
        if build_flash_server:
            flash_server_artifact = await _build_flash_server(
                progress, project_dir, name, upload_to_s3
            )

        # Save build artifacts
        if build_flash_server and flash_server_artifact:
            await _save_build_artifacts(
                project_dir, name, flash_server_artifact, worker_artifacts
            )

    # Display summary
    console.print("\n")
    _display_build_summary(name, flash_server_artifact, worker_artifacts)


async def _build_gpu_workers(
    progress: Progress, project_dir: Path, name: str, upload_to_s3: bool
) -> List[WorkerArtifact]:
    """Build GPU worker packages."""
    workers_task = progress.add_task("[blue]Preparing GPU workers...")
    worker_artifacts = []

    try:
        workers_dir = project_dir / "workers"

        # Find @remote decorated workers
        remote_workers = WorkerDiscovery.find_remote_decorated_workers(workers_dir)

        if not remote_workers:
            progress.update(workers_task, description="[yellow]No GPU workers found")
            progress.stop_task(workers_task)
            return []

        # Create builder
        builder = WorkerTarballBuilder(
            upload_to_s3=upload_to_s3,
            storage_endpoint=os.getenv("RUNPOD_S3_ENDPOINT"),
            storage_bucket=os.getenv("RUNPOD_S3_BUCKET", "tetra-code"),
            storage_access_key=os.getenv("RUNPOD_VOLUME_ACCESS_KEY", ""),
            storage_secret_key=os.getenv("RUNPOD_VOLUME_SECRET_KEY", ""),
        )

        # Build each worker
        for worker_file, class_name in remote_workers:
            artifact = await builder.build_worker(
                workers_dir, worker_file, class_name, name
            )
            if artifact:
                worker_artifacts.append(artifact)

        if worker_artifacts:
            progress.update(
                workers_task,
                description=f"[green]✓ {len(worker_artifacts)} GPU worker(s) ready",
            )
        else:
            progress.update(
                workers_task,
                description="[yellow]No GPU workers built",
            )
        progress.stop_task(workers_task)

    except Exception as e:
        progress.update(workers_task, description=f"[red]✗ Failed: {e}")
        progress.stop_task(workers_task)
        raise

    return worker_artifacts


async def _build_flash_server(
    progress: Progress, project_dir: Path, name: str, upload_to_s3: bool
) -> FlashServerArtifact:
    """Build Flash Server package."""
    server_task = progress.add_task("[green]Preparing Flash Server...")

    try:
        builder = FlashServerTarballBuilder(
            upload_to_s3=upload_to_s3,
            storage_endpoint=os.getenv("RUNPOD_S3_ENDPOINT"),
            storage_bucket=os.getenv("RUNPOD_S3_BUCKET", "tetra-code"),
        )

        artifact = await builder.build_server(project_dir, name)

        progress.update(server_task, description="[green]✓ Flash Server ready")
        progress.stop_task(server_task)

        return artifact

    except Exception as e:
        progress.update(server_task, description=f"[red]✗ Flash Server failed: {e}")
        progress.stop_task(server_task)
        raise


async def _save_build_artifacts(
    project_dir: Path,
    name: str,
    flash_server: FlashServerArtifact,
    workers: List[WorkerArtifact],
):
    """Save build artifacts to .tetra/build_artifacts.json."""
    tetra_dir = project_dir / ".tetra"
    tetra_dir.mkdir(exist_ok=True)

    artifacts = BuildArtifacts(
        project_name=name,
        flash_server=flash_server,
        workers=workers,
        build_time=datetime.utcnow().isoformat() + "Z",
    )

    artifacts_file = tetra_dir / "build_artifacts.json"
    artifacts_file.write_text(json.dumps(asdict(artifacts), indent=2))

    console.print(f"[dim]Build artifacts saved to {artifacts_file}[/dim]")


def _display_build_summary(
    project_name: str,
    flash_server: Optional[FlashServerArtifact],
    workers: List[WorkerArtifact],
):
    """Display build results summary."""

    summary_table = Table(show_header=False, box=None)
    summary_table.add_column("Component", style="bold")
    summary_table.add_column("Count", style="cyan")

    # GPU Workers
    if workers:
        worker_names = ", ".join([w.name for w in workers])
        summary_table.add_row("GPU Workers", f"{len(workers)} ({worker_names})")
    else:
        summary_table.add_row("GPU Workers", "[dim]None[/dim]")

    # Flash Server
    if flash_server:
        summary_table.add_row("Flash Server", "✓")

    console.print("\n")
    console.print(summary_table)

    # Next steps
    console.print("\n[bold]Ready to deploy![/bold]")
    console.print("[dim]Run:[/dim] [bold cyan]flash deploy[/bold cyan]")

    # Success
    console.print(
        Panel(
            f"Build complete for [bold]{project_name}[/bold]",
            title="✓ Success",
            expand=False,
            border_style="green",
        )
    )


# ============================================================================
# Worker Discovery - Finds @remote decorated classes
# ============================================================================


class WorkerDiscovery:
    """Discovers @remote decorated worker classes in project."""

    @staticmethod
    def find_remote_decorated_workers(workers_dir: Path) -> List[Tuple[str, str]]:
        """
        Find all @remote decorated classes in workers/ directory.

        Returns:
            List of (filename, class_name) tuples
        """
        remote_workers = []

        for py_file in workers_dir.glob("*.py"):
            if py_file.name == "__init__.py":
                continue

            try:
                source = py_file.read_text()
                tree = ast.parse(source)

                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        if WorkerDiscovery._has_remote_decorator(node):
                            remote_workers.append((py_file.name, node.name))

            except Exception as e:
                console.print(
                    f"[yellow]Warning:[/yellow] Failed to parse {py_file.name}: {e}"
                )

        return remote_workers

    @staticmethod
    def _has_remote_decorator(class_node: ast.ClassDef) -> bool:
        """Check if class has @remote decorator."""
        for decorator in class_node.decorator_list:
            # @remote
            if isinstance(decorator, ast.Name) and decorator.id == "remote":
                return True
            # @remote(...) or @remote(config)
            elif isinstance(decorator, ast.Call):
                if (
                    isinstance(decorator.func, ast.Name)
                    and decorator.func.id == "remote"
                ):
                    return True
        return False


# ============================================================================
# Decorator Config Extractor - Extracts deps from @remote()
# ============================================================================


class DecoratorConfigExtractor:
    """Extracts configuration from @remote decorator."""

    @staticmethod
    def extract_config(
        file_path: Path, class_name: str
    ) -> Tuple[Optional[List[str]], Optional[List[str]]]:
        """
        Extract dependencies and system_dependencies from @remote decorator.

        Returns:
            Tuple of (dependencies, system_dependencies)
        """
        try:
            source = file_path.read_text()
            tree = ast.parse(source)

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == class_name:
                    for decorator in node.decorator_list:
                        if isinstance(decorator, ast.Call):
                            if (
                                isinstance(decorator.func, ast.Name)
                                and decorator.func.id == "remote"
                            ):
                                return DecoratorConfigExtractor._extract_deps(decorator)

        except Exception as e:
            console.print(
                f"[yellow]Warning:[/yellow] Failed to extract decorator config: {e}"
            )

        return (None, None)

    @staticmethod
    def _extract_deps(
        call_node: ast.Call,
    ) -> Tuple[Optional[List[str]], Optional[List[str]]]:
        """Extract dependencies from decorator call node."""
        dependencies = None
        system_deps = None

        for keyword in call_node.keywords:
            if keyword.arg == "dependencies":
                dependencies = DecoratorConfigExtractor._extract_list(keyword.value)
            elif keyword.arg == "system_dependencies":
                system_deps = DecoratorConfigExtractor._extract_list(keyword.value)

        return (dependencies, system_deps)

    @staticmethod
    def _extract_list(node) -> Optional[List[str]]:
        """Extract list of strings from AST node."""
        if isinstance(node, ast.List):
            items = []
            for elt in node.elts:
                if isinstance(elt, ast.Constant):
                    items.append(elt.value)
                elif isinstance(elt, ast.Str):  # Older Python versions
                    items.append(elt.s)
            return items
        return None


# ============================================================================
# Worker Tarball Builder - Builds GPU worker tarballs
# ============================================================================


class WorkerTarballBuilder:
    """Builds tarball packages for GPU workers."""

    def __init__(
        self,
        upload_to_s3: bool,
        storage_endpoint: str,
        storage_bucket: str,
        storage_access_key: str,
        storage_secret_key: str,
    ):
        self.upload_to_s3 = upload_to_s3
        self.storage_endpoint = storage_endpoint
        self.storage_bucket = storage_bucket
        self.storage_access_key = storage_access_key
        self.storage_secret_key = storage_secret_key

    async def build_worker(
        self, workers_dir: Path, filename: str, class_name: str, project_name: str
    ) -> Optional[WorkerArtifact]:
        """Build tarball for a single worker."""
        try:
            # Import worker class
            worker_class = self._import_worker_class(workers_dir, filename, class_name)
            if not worker_class:
                return None

            # Extract decorator config
            file_path = workers_dir / filename
            dependencies, system_deps = DecoratorConfigExtractor.extract_config(
                file_path, class_name
            )

            # Get GPU image from environment
            import os

            gpu_image = os.getenv("TETRA_GPU_IMAGE", "runpod/worker-tetra:latest")

            # Create tarball strategy
            strategy_config = TarballStrategyConfig(
                base_image=gpu_image,
                upload_to_storage=self.upload_to_s3,
                storage_endpoint=self.storage_endpoint,
                storage_bucket=self.storage_bucket,
                storage_access_key=self.storage_access_key,
                storage_secret_key=self.storage_secret_key,
                dependencies=dependencies or [],
            )
            strategy = TarballStrategy(config=strategy_config)

            # Build tarball
            artifact = await strategy.prepare_deployment(
                func_or_class=worker_class, name=f"{project_name}-{class_name}"
            )

            # Extract code hash
            extractor = CodeExtractor()
            extracted = extractor.extract(worker_class)

            return WorkerArtifact(
                name=class_name,
                tarball_s3_key=artifact.artifact_reference,
                code_hash=extracted.code_hash,
                dependencies=dependencies or [],
                system_dependencies=system_deps or [],
                base_image=gpu_image,
            )

        except Exception as e:
            console.print(
                f"[yellow]Warning:[/yellow] Failed to build {class_name}: {e}"
            )
            return None

    def _import_worker_class(self, workers_dir: Path, filename: str, class_name: str):
        """Dynamically import worker class."""
        try:
            sys.path.insert(0, str(workers_dir.parent))

            module_path = workers_dir / filename
            spec = importlib.util.spec_from_file_location(
                f"workers.{filename[:-3]}", module_path
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            return getattr(module, class_name)

        except Exception as e:
            console.print(
                f"[yellow]Warning:[/yellow] Failed to import {class_name}: {e}"
            )
            return None


# ============================================================================
# Flash Server Tarball Builder - Builds Flash Server tarball
# ============================================================================


class FlashServerTarballBuilder:
    """Builds tarball package for Flash Server."""

    def __init__(self, upload_to_s3: bool, storage_endpoint: str, storage_bucket: str):
        self.upload_to_s3 = upload_to_s3
        self.storage_endpoint = storage_endpoint
        self.storage_bucket = storage_bucket

    async def build_server(
        self, project_dir: Path, project_name: str
    ) -> FlashServerArtifact:
        """Build Flash Server tarball containing full project."""
        import hashlib
        import tarfile
        import tempfile

        # Create temporary tarball
        with tempfile.TemporaryDirectory() as tmpdir:
            tarball_path = Path(tmpdir) / f"{project_name}-flash-server.tar.gz"

            # Create tarball with project contents
            with tarfile.open(tarball_path, "w:gz") as tar:
                # Add all project files
                for item in project_dir.rglob("*"):
                    if self._should_include(item, project_dir):
                        arcname = item.relative_to(project_dir)
                        tar.add(item, arcname=arcname)

            # Calculate hash
            with open(tarball_path, "rb") as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()[:8]

            # Upload to S3 if configured
            if self.upload_to_s3:
                from tetra_rp.build.gpu_workers.volume_manager import VolumeManager

                volume_manager = VolumeManager()
                storage_key = (
                    f"tetra/code/{project_name}-flash-server-{file_hash}.tar.gz"
                )

                upload_result = volume_manager.upload_tarball(
                    tarball_path=tarball_path,
                    s3_key=storage_key,
                )

                if upload_result.success:
                    s3_key = upload_result.s3_key
                else:
                    # Fallback to local if upload fails
                    console.print(
                        "[yellow]Warning:[/yellow] S3 upload failed, using local tarball"
                    )
                    s3_key = str(tarball_path)
            else:
                # Local mode - use file path
                s3_key = str(tarball_path)

            return FlashServerArtifact(
                tarball_s3_key=s3_key,
                base_image="mwiki/flash-server:latest",
                port=8888,
            )

    def _should_include(self, path: Path, project_dir: Path) -> bool:
        """Determine if file should be included in tarball."""
        # Exclude patterns
        exclude_patterns = [
            "__pycache__",
            "*.pyc",
            ".git",
            ".tetra",
            "*.egg-info",
            ".venv",
            "venv",
            ".env",
            ".DS_Store",
            "node_modules",
        ]

        # Check if path matches any exclude pattern
        path_str = str(path.relative_to(project_dir))
        for pattern in exclude_patterns:
            if pattern in path_str or path.name == pattern:
                return False

        return path.is_file()

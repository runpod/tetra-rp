"""Flash build command - Package Flash applications for deployment."""

import ast
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from ..utils.ignore import get_file_tree, load_ignore_patterns

console = Console()

# Constants
PIP_INSTALL_TIMEOUT_SECONDS = 600  # 10 minute timeout for pip install


def build_command(
    no_deps: bool = typer.Option(
        False, "--no-deps", help="Skip transitive dependencies during pip install"
    ),
    keep_build: bool = typer.Option(
        False, "--keep-build", help="Keep .build directory after creating archive"
    ),
    output_name: str | None = typer.Option(
        None, "--output", "-o", help="Custom archive name (default: archive.tar.gz)"
    ),
):
    """
    Build Flash application for deployment.

    Packages the application code and dependencies into a self-contained tarball,
    similar to AWS Lambda packaging. All pip packages are installed as local modules.

    Examples:
      flash build                  # Build with all dependencies
      flash build --no-deps        # Skip transitive dependencies
      flash build --keep-build     # Keep temporary build directory
      flash build -o my-app.tar.gz # Custom archive name
    """
    try:
        # Validate project structure
        project_dir, app_name = discover_flash_project()

        if not validate_project_structure(project_dir):
            console.print("[red]Error:[/red] Not a valid Flash project")
            console.print("Run [bold]flash init[/bold] to create a Flash project")
            raise typer.Exit(1)

        # Display configuration
        _display_build_config(project_dir, app_name, no_deps, keep_build, output_name)

        # Execute build
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            # Load ignore patterns
            ignore_task = progress.add_task("Loading ignore patterns...")
            spec = load_ignore_patterns(project_dir)
            progress.update(ignore_task, description="[green]✓ Loaded ignore patterns")
            progress.stop_task(ignore_task)

            # Collect files
            collect_task = progress.add_task("Collecting project files...")
            files = get_file_tree(project_dir, spec)
            progress.update(
                collect_task,
                description=f"[green]✓ Found {len(files)} files to package",
            )
            progress.stop_task(collect_task)

            # Create build directory
            build_task = progress.add_task("Creating build directory...")
            build_dir = create_build_directory(project_dir, app_name)
            progress.update(
                build_task,
                description=f"[green]✓ Created .tetra/.build/{app_name}/",
            )
            progress.stop_task(build_task)

            # Copy files
            copy_task = progress.add_task("Copying project files...")
            copy_project_files(files, project_dir, build_dir)
            progress.update(
                copy_task, description=f"[green]✓ Copied {len(files)} files"
            )
            progress.stop_task(copy_task)

            # Install dependencies
            deps_task = progress.add_task("Installing dependencies...")
            requirements = collect_requirements(project_dir, build_dir)

            if not requirements:
                progress.update(
                    deps_task,
                    description="[yellow]⚠ No dependencies found",
                )
            else:
                progress.update(
                    deps_task,
                    description=f"Installing {len(requirements)} packages...",
                )

                success = install_dependencies(build_dir, requirements, no_deps)

                if not success:
                    progress.stop_task(deps_task)
                    console.print("[red]Error:[/red] Failed to install dependencies")
                    raise typer.Exit(1)

                progress.update(
                    deps_task,
                    description=f"[green]✓ Installed {len(requirements)} packages",
                )

            progress.stop_task(deps_task)

            # Create archive
            archive_task = progress.add_task("Creating archive...")
            archive_name = output_name or "archive.tar.gz"
            archive_path = project_dir / ".tetra" / archive_name

            create_tarball(build_dir, archive_path, app_name)

            # Get archive size
            size_mb = archive_path.stat().st_size / (1024 * 1024)

            progress.update(
                archive_task,
                description=f"[green]✓ Created {archive_name} ({size_mb:.1f} MB)",
            )
            progress.stop_task(archive_task)

            # Cleanup
            if not keep_build:
                cleanup_task = progress.add_task("Cleaning up...")
                cleanup_build_directory(build_dir.parent)
                progress.update(
                    cleanup_task, description="[green]✓ Removed .build directory"
                )
                progress.stop_task(cleanup_task)

        # Success summary
        _display_build_summary(archive_path, app_name, len(files), len(requirements))

    except KeyboardInterrupt:
        console.print("\n[yellow]Build cancelled by user[/yellow]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"\n[red]Build failed:[/red] {e}")
        import traceback

        console.print(traceback.format_exc())
        raise typer.Exit(1)


def discover_flash_project() -> tuple[Path, str]:
    """
    Discover Flash project directory and app name.

    Returns:
        Tuple of (project_dir, app_name)

    Raises:
        typer.Exit: If not in a Flash project directory
    """
    project_dir = Path.cwd()
    app_name = project_dir.name

    return project_dir, app_name


def validate_project_structure(project_dir: Path) -> bool:
    """
    Validate that directory is a Flash project.

    Args:
        project_dir: Directory to validate

    Returns:
        True if valid Flash project
    """
    main_py = project_dir / "main.py"

    if not main_py.exists():
        console.print(f"[red]Error:[/red] main.py not found in {project_dir}")
        return False

    # Check if main.py has FastAPI app
    try:
        content = main_py.read_text(encoding="utf-8")
        if "FastAPI" not in content:
            console.print(
                "[yellow]Warning:[/yellow] main.py does not appear to have a FastAPI app"
            )
    except Exception:
        pass

    return True


def create_build_directory(project_dir: Path, app_name: str) -> Path:
    """
    Create .tetra/.build/{app_name}/ directory.

    Args:
        project_dir: Flash project directory
        app_name: Application name

    Returns:
        Path to build directory
    """
    tetra_dir = project_dir / ".tetra"
    tetra_dir.mkdir(exist_ok=True)

    build_base = tetra_dir / ".build"
    build_dir = build_base / app_name

    # Remove existing build directory
    if build_dir.exists():
        shutil.rmtree(build_dir)

    build_dir.mkdir(parents=True, exist_ok=True)

    return build_dir


def copy_project_files(files: list[Path], source_dir: Path, dest_dir: Path) -> None:
    """
    Copy project files to build directory.

    Args:
        files: List of files to copy
        source_dir: Source directory
        dest_dir: Destination directory
    """
    for file_path in files:
        # Get relative path
        rel_path = file_path.relative_to(source_dir)

        # Create destination path
        dest_path = dest_dir / rel_path

        # Create parent directories
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        # Copy file
        shutil.copy2(file_path, dest_path)


def collect_requirements(project_dir: Path, build_dir: Path) -> list[str]:
    """
    Collect all requirements from requirements.txt and @remote decorators.

    Args:
        project_dir: Flash project directory
        build_dir: Build directory (to check for workers)

    Returns:
        List of requirement strings
    """
    requirements = []

    # Load requirements.txt
    req_file = project_dir / "requirements.txt"
    if req_file.exists():
        try:
            content = req_file.read_text(encoding="utf-8")
            for line in content.splitlines():
                line = line.strip()
                # Skip empty lines and comments
                if line and not line.startswith("#"):
                    requirements.append(line)
        except Exception as e:
            console.print(
                f"[yellow]Warning:[/yellow] Failed to read requirements.txt: {e}"
            )

    # Extract dependencies from @remote decorators
    workers_dir = build_dir / "workers"
    if workers_dir.exists():
        remote_deps = extract_remote_dependencies(workers_dir)
        requirements.extend(remote_deps)

    # Remove duplicates while preserving order
    seen = set()
    unique_requirements = []
    for req in requirements:
        if req not in seen:
            seen.add(req)
            unique_requirements.append(req)

    return unique_requirements


def extract_remote_dependencies(workers_dir: Path) -> list[str]:
    """
    Extract dependencies from @remote decorators in worker files.

    Args:
        workers_dir: Path to workers directory

    Returns:
        List of dependency strings
    """
    dependencies = []

    for py_file in workers_dir.glob("*.py"):
        if py_file.name == "__init__.py":
            continue

        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))

            for node in ast.walk(tree):
                if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
                    for decorator in node.decorator_list:
                        if isinstance(decorator, ast.Call):
                            func_name = None
                            if isinstance(decorator.func, ast.Name):
                                func_name = decorator.func.id
                            elif isinstance(decorator.func, ast.Attribute):
                                func_name = decorator.func.attr

                            if func_name == "remote":
                                # Extract dependencies keyword argument
                                for keyword in decorator.keywords:
                                    if keyword.arg == "dependencies":
                                        if isinstance(keyword.value, ast.List):
                                            for elt in keyword.value.elts:
                                                if isinstance(elt, ast.Constant):
                                                    dependencies.append(elt.value)

        except Exception as e:
            console.print(
                f"[yellow]Warning:[/yellow] Failed to parse {py_file.name}: {e}"
            )

    return dependencies


def install_dependencies(
    build_dir: Path, requirements: list[str], no_deps: bool
) -> bool:
    """
    Install dependencies to build directory using pip.

    Args:
        build_dir: Build directory (pip --target)
        requirements: List of requirements to install
        no_deps: If True, skip transitive dependencies

    Returns:
        True if successful
    """
    if not requirements:
        return True

    # Use only sys.executable -m pip to ensure correct environment
    pip_cmd = [sys.executable, "-m", "pip"]

    # Check if pip is available
    try:
        result = subprocess.run(
            pip_cmd + ["--version"],
            capture_output=True,
            timeout=5,
        )
        if result.returncode != 0:
            console.print(
                "[red]Error:[/red] pip not found in current Python environment"
            )
            return False
    except (subprocess.SubprocessError, FileNotFoundError):
        console.print("[red]Error:[/red] pip not found in current Python environment")
        return False

    cmd = pip_cmd + [
        "install",
        "--target",
        str(build_dir),
        "--upgrade",
    ]

    if no_deps:
        cmd.append("--no-deps")

    cmd.extend(requirements)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=PIP_INSTALL_TIMEOUT_SECONDS,
        )

        if result.returncode != 0:
            console.print(f"[red]pip install failed:[/red]\n{result.stderr}")
            return False

        return True

    except subprocess.TimeoutExpired:
        console.print(
            f"[red]pip install timed out ({PIP_INSTALL_TIMEOUT_SECONDS} seconds)[/red]"
        )
        return False
    except Exception as e:
        console.print(f"[red]pip install error:[/red] {e}")
        return False


def create_tarball(build_dir: Path, output_path: Path, app_name: str) -> None:
    """
    Create gzipped tarball of build directory.

    Args:
        build_dir: Build directory to archive
        output_path: Output archive path
        app_name: Application name (used as archive root)
    """
    # Remove existing archive
    if output_path.exists():
        output_path.unlink()

    # Create tarball with app_name as root directory
    with tarfile.open(output_path, "w:gz") as tar:
        tar.add(build_dir, arcname=app_name)


def cleanup_build_directory(build_base: Path) -> None:
    """
    Remove build directory.

    Args:
        build_base: .build directory to remove
    """
    if build_base.exists():
        shutil.rmtree(build_base)


def _display_build_config(
    project_dir: Path,
    app_name: str,
    no_deps: bool,
    keep_build: bool,
    output_name: str | None,
):
    """Display build configuration."""
    archive_name = output_name or "archive.tar.gz"

    console.print(
        Panel(
            f"[bold]Project:[/bold] {app_name}\n"
            f"[bold]Directory:[/bold] {project_dir}\n"
            f"[bold]Archive:[/bold] .tetra/{archive_name}\n"
            f"[bold]Skip transitive deps:[/bold] {no_deps}\n"
            f"[bold]Keep build dir:[/bold] {keep_build}",
            title="Flash Build Configuration",
            expand=False,
        )
    )


def _display_build_summary(
    archive_path: Path, app_name: str, file_count: int, dep_count: int
):
    """Display build summary."""
    size_mb = archive_path.stat().st_size / (1024 * 1024)

    summary = Table(show_header=False, box=None)
    summary.add_column("Item", style="bold")
    summary.add_column("Value", style="cyan")

    summary.add_row("Application", app_name)
    summary.add_row("Files packaged", str(file_count))
    summary.add_row("Dependencies", str(dep_count))
    summary.add_row("Archive", str(archive_path.relative_to(Path.cwd())))
    summary.add_row("Size", f"{size_mb:.1f} MB")

    console.print("\n")
    console.print(summary)

    console.print(
        Panel(
            f"[bold]{app_name}[/bold] built successfully!\n\n"
            f"Archive ready for deployment.",
            title="✓ Build Complete",
            expand=False,
            border_style="green",
        )
    )

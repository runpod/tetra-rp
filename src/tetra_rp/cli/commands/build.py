"""Flash build command - Package Flash applications for deployment."""

import ast
import importlib.util
import json
import logging
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

try:
    import tomllib  # Python 3.11+
except ImportError:
    import tomli as tomllib  # Python 3.9-3.10

from ..utils.ignore import get_file_tree, load_ignore_patterns
from .build_utils.handler_generator import HandlerGenerator
from .build_utils.lb_handler_generator import LBHandlerGenerator
from .build_utils.manifest import ManifestBuilder
from .build_utils.mothership_handler_generator import generate_mothership_handler
from .build_utils.scanner import RemoteDecoratorScanner

logger = logging.getLogger(__name__)

console = Console()

# Constants
# Timeout for pip install operations (large packages like torch can take 5-10 minutes)
PIP_INSTALL_TIMEOUT_SECONDS = 600
# Timeout for ensurepip (lightweight operation, typically completes in <10 seconds)
ENSUREPIP_TIMEOUT_SECONDS = 30
# Timeout for version checks (should be instant)
VERSION_CHECK_TIMEOUT_SECONDS = 5

# RunPod serverless deployment limit (hard limit enforced by platform)
RUNPOD_MAX_ARCHIVE_SIZE_MB = 500

# RunPod Serverless platform specifications
# RunPod serverless runs on x86_64 Linux, regardless of build platform
# Support multiple manylinux versions (newer versions are backward compatible)
RUNPOD_PLATFORMS = [
    "manylinux_2_28_x86_64",  # glibc 2.28+ (newest, for Python 3.13+)
    "manylinux_2_17_x86_64",  # glibc 2.17+ (covers most modern packages)
    "manylinux2014_x86_64",  # glibc 2.17 (legacy compatibility)
]
RUNPOD_PYTHON_IMPL = "cp"  # CPython implementation

# Pip command identifiers
UV_COMMAND = "uv"
PIP_MODULE = "pip"


def _find_local_tetra_rp() -> Optional[Path]:
    """Find local tetra_rp source directory if available.

    Returns:
        Path to tetra_rp package directory, or None if not found or installed from PyPI
    """
    try:
        spec = importlib.util.find_spec("tetra_rp")

        if not spec or not spec.origin:
            return None

        # Get package directory (spec.origin is __init__.py path)
        pkg_dir = Path(spec.origin).parent

        # Skip if installed in site-packages (PyPI install)
        if "site-packages" in str(pkg_dir):
            return None

        # Must be development install
        return pkg_dir

    except Exception:
        return None


def _bundle_local_tetra_rp(build_dir: Path) -> bool:
    """Copy local tetra_rp source into build directory.

    Args:
        build_dir: Target build directory

    Returns:
        True if bundled successfully, False otherwise
    """
    tetra_pkg = _find_local_tetra_rp()

    if not tetra_pkg:
        console.print(
            "[yellow]⚠ Local tetra_rp not found or using PyPI install[/yellow]"
        )
        return False

    # Copy tetra_rp to build
    dest = build_dir / "tetra_rp"
    if dest.exists():
        shutil.rmtree(dest)

    shutil.copytree(
        tetra_pkg,
        dest,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"),
    )

    console.print(f"[cyan]✓ Bundled local tetra_rp from {tetra_pkg}[/cyan]")
    return True


def _extract_tetra_rp_dependencies(tetra_pkg_dir: Path) -> list[str]:
    """Extract runtime dependencies from tetra_rp's pyproject.toml.

    When bundling local tetra_rp source, we need to also install its dependencies
    so they're available in the build environment.

    Args:
        tetra_pkg_dir: Path to tetra_rp package directory (src/tetra_rp)

    Returns:
        List of dependency strings, empty list if parsing fails
    """
    try:
        # Navigate from tetra_rp package to project root
        # tetra_pkg_dir is src/tetra_rp, need to go up 2 levels to reach project root
        project_root = tetra_pkg_dir.parent.parent
        pyproject_path = project_root / "pyproject.toml"

        if not pyproject_path.exists():
            console.print(
                "[yellow]⚠ tetra_rp pyproject.toml not found, "
                "dependencies may be missing[/yellow]"
            )
            return []

        # Parse TOML
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)

        # Extract dependencies from [project.dependencies]
        dependencies = data.get("project", {}).get("dependencies", [])

        if dependencies:
            console.print(
                f"[dim]Found {len(dependencies)} tetra_rp dependencies to install[/dim]"
            )

        return dependencies

    except Exception as e:
        console.print(f"[yellow]⚠ Failed to parse tetra_rp dependencies: {e}[/yellow]")
        return []


def _remove_tetra_from_requirements(build_dir: Path) -> None:
    """Remove tetra_rp from requirements.txt and clean up dist-info since we bundled source."""
    req_file = build_dir / "requirements.txt"

    if not req_file.exists():
        return

    lines = req_file.read_text().splitlines()
    filtered = [
        line
        for line in lines
        if not line.strip().startswith("tetra_rp")
        and not line.strip().startswith("tetra-rp")
    ]

    req_file.write_text("\n".join(filtered) + "\n")

    # Remove tetra_rp dist-info directory to avoid conflicts with bundled source
    # dist-info is created by pip install and can confuse Python's import system
    for dist_info in build_dir.glob("tetra_rp-*.dist-info"):
        if dist_info.is_dir():
            shutil.rmtree(dist_info)


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
    exclude: str | None = typer.Option(
        None,
        "--exclude",
        help="Comma-separated packages to exclude (e.g., 'torch,torchvision')",
    ),
    use_local_tetra: bool = typer.Option(
        False,
        "--use-local-tetra",
        help="Bundle local tetra_rp source instead of PyPI version (for development/testing)",
    ),
):
    """
    Build Flash application for deployment.

    Packages the application code and dependencies into a self-contained tarball,
    similar to AWS Lambda packaging. All pip packages are installed as local modules.

    Examples:
      flash build                              # Build with all dependencies
      flash build --no-deps                    # Skip transitive dependencies
      flash build --keep-build                 # Keep temporary build directory
      flash build -o my-app.tar.gz             # Custom archive name
      flash build --exclude torch,torchvision  # Exclude large packages (assume in base image)
    """
    try:
        # Validate project structure
        project_dir, app_name = discover_flash_project()

        if not validate_project_structure(project_dir):
            console.print("[red]Error:[/red] Not a valid Flash project")
            console.print("Run [bold]flash init[/bold] to create a Flash project")
            raise typer.Exit(1)

        # Create build directory first to ensure clean state before collecting files
        build_dir = create_build_directory(project_dir, app_name)

        # Parse exclusions
        excluded_packages = []
        if exclude:
            excluded_packages = [pkg.strip().lower() for pkg in exclude.split(",")]

        # Display configuration
        _display_build_config(
            project_dir, app_name, no_deps, keep_build, output_name, excluded_packages
        )

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

            # Note: build directory already created before progress tracking
            build_task = progress.add_task("Creating build directory...")
            progress.update(
                build_task,
                description="[green]✓ Created .flash/.build/",
            )
            progress.stop_task(build_task)

            try:
                # Copy files
                copy_task = progress.add_task("Copying project files...")
                copy_project_files(files, project_dir, build_dir)
                progress.update(
                    copy_task, description=f"[green]✓ Copied {len(files)} files"
                )
                progress.stop_task(copy_task)

                # Generate handlers and manifest
                manifest_task = progress.add_task("Generating service manifest...")
                try:
                    scanner = RemoteDecoratorScanner(build_dir)
                    remote_functions = scanner.discover_remote_functions()

                    # Always build manifest (includes mothership even without @remote functions)
                    manifest_builder = ManifestBuilder(
                        app_name, remote_functions, scanner, build_dir=build_dir
                    )
                    manifest = manifest_builder.build()
                    manifest_path = build_dir / "flash_manifest.json"
                    manifest_path.write_text(json.dumps(manifest, indent=2))

                    # Copy manifest to .flash/ directory for deployment reference
                    # This avoids needing to extract from tarball during deploy
                    flash_dir = project_dir / ".flash"
                    deployment_manifest_path = flash_dir / "flash_manifest.json"
                    shutil.copy2(manifest_path, deployment_manifest_path)

                    # Generate handler files if there are resources
                    handler_paths = []
                    manifest_resources = manifest.get("resources", {})

                    if manifest_resources:
                        # Separate resources by type
                        # Use flag determined by isinstance() at scan time
                        lb_resources = {
                            name: data
                            for name, data in manifest_resources.items()
                            if data.get("is_load_balanced", False)
                        }
                        qb_resources = {
                            name: data
                            for name, data in manifest_resources.items()
                            if not data.get("is_load_balanced", False)
                        }

                        # Generate LB handlers
                        if lb_resources:
                            lb_gen = LBHandlerGenerator(manifest, build_dir)
                            handler_paths.extend(lb_gen.generate_handlers())

                        # Generate QB handlers
                        if qb_resources:
                            qb_gen = HandlerGenerator(manifest, build_dir)
                            handler_paths.extend(qb_gen.generate_handlers())

                        # Generate mothership handler if present in manifest
                        mothership_resources = {
                            name: data
                            for name, data in manifest_resources.items()
                            if data.get("is_mothership", False)
                        }
                        if mothership_resources:
                            for (
                                resource_name,
                                resource_data,
                            ) in mothership_resources.items():
                                mothership_handler_path = (
                                    build_dir / "handlers" / "handler_mothership.py"
                                )
                                generate_mothership_handler(
                                    main_file=resource_data.get("main_file", "main.py"),
                                    app_variable=resource_data.get(
                                        "app_variable", "app"
                                    ),
                                    output_path=mothership_handler_path,
                                )
                                handler_paths.append(str(mothership_handler_path))

                    if handler_paths:
                        progress.update(
                            manifest_task,
                            description=f"[green]✓ Generated {len(handler_paths)} handlers and manifest",
                        )
                    elif manifest_resources:
                        progress.update(
                            manifest_task,
                            description=f"[green]✓ Generated manifest with {len(manifest_resources)} resources",
                        )
                    else:
                        progress.update(
                            manifest_task,
                            description="[yellow]⚠ No resources detected",
                        )

                except (ImportError, SyntaxError) as e:
                    progress.stop_task(manifest_task)
                    console.print(f"[red]Error:[/red] Code analysis failed: {e}")
                    logger.exception("Code analysis failed")
                    raise typer.Exit(1)
                except ValueError as e:
                    progress.stop_task(manifest_task)
                    console.print(f"[red]Error:[/red] {e}")
                    logger.exception("Handler generation validation failed")
                    raise typer.Exit(1)
                except Exception as e:
                    progress.stop_task(manifest_task)
                    logger.exception("Handler generation failed")
                    console.print(
                        f"[yellow]Warning:[/yellow] Handler generation failed: {e}"
                    )

                progress.stop_task(manifest_task)

            except typer.Exit:
                # Clean up on fatal errors (ImportError, SyntaxError, ValueError)
                if build_dir.exists():
                    shutil.rmtree(build_dir)
                raise
            except Exception as e:
                # Clean up on unexpected errors
                if build_dir.exists():
                    shutil.rmtree(build_dir)
                console.print(f"[red]Error:[/red] Build failed: {e}")
                logger.exception("Build failed")
                raise typer.Exit(1)

            # Extract tetra_rp dependencies if bundling local version
            tetra_deps = []
            if use_local_tetra:
                tetra_pkg = _find_local_tetra_rp()
                if tetra_pkg:
                    tetra_deps = _extract_tetra_rp_dependencies(tetra_pkg)

            # Install dependencies
            deps_task = progress.add_task("Installing dependencies...")
            requirements = collect_requirements(project_dir, build_dir)

            # Add tetra_rp dependencies if bundling local version
            # This ensures all tetra_rp runtime dependencies are available in the build
            requirements.extend(tetra_deps)

            # Filter out excluded packages
            if excluded_packages:
                original_count = len(requirements)
                matched_exclusions = set()
                filtered_requirements = []

                for req in requirements:
                    if should_exclude_package(req, excluded_packages):
                        # Extract which exclusion matched
                        pkg_name = extract_package_name(req)
                        if pkg_name in excluded_packages:
                            matched_exclusions.add(pkg_name)
                    else:
                        filtered_requirements.append(req)

                requirements = filtered_requirements
                excluded_count = original_count - len(requirements)

                if excluded_count > 0:
                    console.print(
                        f"[yellow]Excluded {excluded_count} package(s) "
                        f"(assumed in base image)[/yellow]"
                    )

                # Warn about exclusions that didn't match any packages
                unmatched = set(excluded_packages) - matched_exclusions
                if unmatched:
                    console.print(
                        f"[yellow]Warning: No packages matched exclusions: "
                        f"{', '.join(sorted(unmatched))}[/yellow]"
                    )

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

            # Bundle local tetra_rp if requested
            if use_local_tetra:
                tetra_task = progress.add_task("Bundling local tetra_rp...")
                if _bundle_local_tetra_rp(build_dir):
                    _remove_tetra_from_requirements(build_dir)
                    progress.update(
                        tetra_task,
                        description="[green]✓ Bundled local tetra_rp",
                    )
                else:
                    progress.update(
                        tetra_task,
                        description="[yellow]⚠ Using PyPI tetra_rp",
                    )
                progress.stop_task(tetra_task)

            # Clean up Python bytecode before archiving
            cleanup_python_bytecode(build_dir)

            # Create archive
            archive_task = progress.add_task("Creating archive...")
            archive_name = output_name or "archive.tar.gz"
            archive_path = project_dir / ".flash" / archive_name

            create_tarball(build_dir, archive_path, app_name)

            # Get archive size
            size_mb = archive_path.stat().st_size / (1024 * 1024)

            progress.update(
                archive_task,
                description=f"[green]✓ Created {archive_name} ({size_mb:.1f} MB)",
            )
            progress.stop_task(archive_task)

            # Warning for size limit
            if size_mb > RUNPOD_MAX_ARCHIVE_SIZE_MB:
                console.print()
                console.print(
                    Panel(
                        f"[yellow bold]⚠ WARNING: Archive exceeds RunPod limit[/yellow bold]\n\n"
                        f"[yellow]Archive size:[/yellow] {size_mb:.1f} MB\n"
                        f"[yellow]RunPod limit:[/yellow] {RUNPOD_MAX_ARCHIVE_SIZE_MB} MB\n"
                        f"[yellow]Over by:[/yellow] {size_mb - RUNPOD_MAX_ARCHIVE_SIZE_MB:.1f} MB\n\n"
                        f"[dim]Use --exclude to skip packages in base image:\n"
                        f"  flash build --exclude torch,torchvision,torchaudio[/dim]",
                        title="Deployment Size Warning",
                        border_style="yellow",
                    )
                )
                console.print()

            # Cleanup
            if not keep_build:
                cleanup_task = progress.add_task("Cleaning up...")
                cleanup_build_directory(build_dir)
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
    Create .flash/.build/ directory.

    Args:
        project_dir: Flash project directory
        app_name: Application name (used for archive naming, not directory structure)

    Returns:
        Path to build directory
    """
    flash_dir = project_dir / ".flash"
    flash_dir.mkdir(exist_ok=True)

    build_dir = flash_dir / ".build"

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


def cleanup_python_bytecode(build_dir: Path) -> None:
    """
    Remove Python bytecode files and __pycache__ directories from build directory.

    These files are generated during the build process when Python imports modules
    for validation. They are platform-specific and will be regenerated on the
    deployment platform, so including them is unnecessary.

    Args:
        build_dir: Build directory to clean up
    """
    # Remove all __pycache__ directories
    for pycache_dir in build_dir.rglob("__pycache__"):
        if pycache_dir.is_dir():
            shutil.rmtree(pycache_dir)

    # Remove any stray .pyc, .pyo, .pyd files
    for bytecode_pattern in ["*.pyc", "*.pyo", "*.pyd"]:
        for bytecode_file in build_dir.rglob(bytecode_pattern):
            if bytecode_file.is_file():
                bytecode_file.unlink()


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


def extract_package_name(requirement: str) -> str:
    """
    Extract the package name from a requirement specification.

    Handles version specifiers, extras, and other pip requirement syntax.

    Args:
        requirement: Requirement string (e.g., "torch>=2.0.0", "numpy[extra]")

    Returns:
        Package name in lowercase (e.g., "torch", "numpy")

    Examples:
        >>> extract_package_name("torch>=2.0.0")
        "torch"
        >>> extract_package_name("numpy[extra]")
        "numpy"
        >>> extract_package_name("my-package==1.0.0")
        "my-package"
    """
    # Split on version specifiers, extras, and environment markers
    # This regex matches: < > = ! [ ; (common pip requirement delimiters)
    package_name = re.split(r"[<>=!\[;]", requirement)[0].strip().lower()
    return package_name


def should_exclude_package(requirement: str, exclusions: list[str]) -> bool:
    """
    Check if a requirement should be excluded based on package name matching.

    Uses exact package name matching (after normalization) to avoid false positives.

    Args:
        requirement: Requirement string (e.g., "torch>=2.0.0")
        exclusions: List of package names to exclude (lowercase)

    Returns:
        True if package should be excluded, False otherwise

    Examples:
        >>> should_exclude_package("torch>=2.0.0", ["torch", "numpy"])
        True
        >>> should_exclude_package("torch-vision==0.15.0", ["torch"])
        False  # torch-vision is different from torch
    """
    package_name = extract_package_name(requirement)
    return package_name in exclusions


def extract_remote_dependencies(workers_dir: Path) -> list[str]:
    """
    Extract dependencies from @remote decorators in worker files.

    Args:
        workers_dir: Path to workers directory

    Returns:
        List of dependency strings
    """
    dependencies = []

    for py_file in workers_dir.glob("**/*.py"):
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
    Install dependencies to build directory using pip or uv pip.

    Installs packages for Linux x86_64 platform to ensure compatibility with
    RunPod serverless, regardless of the build platform (macOS, Windows, Linux).

    Auto-installation behavior:
    - If standard pip is not available, it will be automatically installed via ensurepip
    - This modifies the current virtual environment (persists after build completes)
    - Standard pip is strongly preferred for cross-platform builds due to better
      manylinux compatibility (uv pip has known issues with manylinux_2_27+)

    Args:
        build_dir: Build directory (pip --target)
        requirements: List of requirements to install
        no_deps: If True, skip transitive dependencies

    Returns:
        True if successful
    """
    if not requirements:
        return True

    # Prefer standard pip over uv pip for cross-platform builds
    # Standard pip's --platform flag works correctly with manylinux tags
    # uv pip has known issues with manylinux_2_27/2_28 detection (uv issue #5106)
    pip_cmd = [sys.executable, "-m", PIP_MODULE]
    pip_available = False

    try:
        result = subprocess.run(
            pip_cmd + ["--version"],
            capture_output=True,
            text=True,
            timeout=VERSION_CHECK_TIMEOUT_SECONDS,
        )
        if result.returncode == 0:
            pip_available = True
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    # If pip not available, install it using ensurepip
    # This modifies the current virtual environment
    if not pip_available:
        console.print(
            "[yellow]Standard pip not found. Installing pip for reliable cross-platform builds...[/yellow]"
        )
        try:
            result = subprocess.run(
                [sys.executable, "-m", "ensurepip", "--upgrade"],
                capture_output=True,
                text=True,
                timeout=ENSUREPIP_TIMEOUT_SECONDS,
            )
            if result.returncode == 0:
                # Verify pip is now available
                result = subprocess.run(
                    pip_cmd + ["--version"],
                    capture_output=True,
                    text=True,
                    timeout=VERSION_CHECK_TIMEOUT_SECONDS,
                )
                if result.returncode == 0:
                    pip_available = True
                    console.print(
                        "[green]✓[/green] Standard pip installed successfully"
                    )
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            console.print(f"[yellow]Warning:[/yellow] Failed to install pip: {e}")

    # If pip still not available, try uv pip (less reliable for cross-platform)
    if not pip_available:
        try:
            result = subprocess.run(
                [UV_COMMAND, PIP_MODULE, "--version"],
                capture_output=True,
                text=True,
                timeout=VERSION_CHECK_TIMEOUT_SECONDS,
            )
            if result.returncode == 0:
                pip_cmd = [UV_COMMAND, PIP_MODULE]
                pip_available = True
                console.print(
                    f"[yellow]Warning:[/yellow] Using '{UV_COMMAND} {PIP_MODULE}' which has known issues "
                    f"with newer manylinux tags (manylinux_2_27+)"
                )
                console.print(
                    "[yellow]This may fail for Python 3.13+ with newer packages (e.g., numpy 2.4+)[/yellow]"
                )
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

    # If neither available, error out
    if not pip_available:
        console.print(
            f"[red]Error:[/red] Neither {PIP_MODULE} nor {UV_COMMAND} {PIP_MODULE} found"
        )
        console.print(f"\n[yellow]Install {PIP_MODULE} with one of:[/yellow]")
        console.print("  • python -m ensurepip --upgrade")
        console.print(f"  • {UV_COMMAND} {PIP_MODULE} install {PIP_MODULE}")
        return False

    # Get current Python version for compatibility
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}"

    # Determine if using uv pip or standard pip (different flag formats)
    is_uv_pip = pip_cmd[0] == UV_COMMAND

    # Build pip command with platform-specific flags for RunPod serverless
    cmd = pip_cmd + [
        "install",
        "--target",
        str(build_dir),
        "--python-version",
        python_version,
        "--upgrade",
    ]

    # Add platform-specific flags based on pip variant
    if is_uv_pip:
        # uv pip uses --python-platform with simpler values
        # Note: uv has known issues with manylinux_2_27+ detection (issue #5106)
        cmd.extend(
            [
                "--python-platform",
                "x86_64-unknown-linux-gnu",
                "--no-build",  # Don't build from source, use binary wheels only
            ]
        )
    else:
        # Standard pip uses --platform with manylinux tags
        # Specify multiple platforms for broader compatibility
        for platform in RUNPOD_PLATFORMS:
            cmd.extend(["--platform", platform])
        cmd.extend(
            [
                "--implementation",
                RUNPOD_PYTHON_IMPL,
                "--only-binary=:all:",
            ]
        )

    if no_deps:
        cmd.append("--no-deps")

    cmd.extend(requirements)

    # Log platform targeting info
    if is_uv_pip:
        platform_str = "x86_64-unknown-linux-gnu"
    else:
        platform_str = f"{len(RUNPOD_PLATFORMS)} manylinux variants"
    console.print(f"[dim]Installing for: {platform_str}, Python {python_version}[/dim]")

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
        app_name: Application name (unused, for compatibility)
    """
    # Remove existing archive
    if output_path.exists():
        output_path.unlink()

    # Create tarball with build directory contents at root level
    with tarfile.open(output_path, "w:gz") as tar:
        tar.add(build_dir, arcname=".")


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
    excluded_packages: list[str],
):
    """Display build configuration."""
    archive_name = output_name or "archive.tar.gz"

    config_text = (
        f"[bold]Project:[/bold] {app_name}\n"
        f"[bold]Directory:[/bold] {project_dir}\n"
        f"[bold]Archive:[/bold] .flash/{archive_name}\n"
        f"[bold]Skip transitive deps:[/bold] {no_deps}\n"
        f"[bold]Keep build dir:[/bold] {keep_build}"
    )

    if excluded_packages:
        config_text += (
            f"\n[bold]Excluded packages:[/bold] {', '.join(excluded_packages)}"
        )

    console.print(
        Panel(
            config_text,
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

    archive_rel = archive_path.relative_to(Path.cwd())

    next_steps = (
        f"[bold]{app_name}[/bold] built successfully!\n\n"
        f"[bold]Archive:[/bold] {archive_rel}\n\n"
        f"Next: Use [cyan]flash deploy[/cyan] to deploy to RunPod."
    )

    console.print(
        Panel(
            next_steps,
            title="✓ Build Complete",
            expand=False,
            border_style="green",
        )
    )

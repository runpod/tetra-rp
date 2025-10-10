"""
Code packaging for tarball-based deployment.

Creates tarball packages of source code for fast deployment to workers.
"""

import json
import logging
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List

from ..shared.code_extractor import ExtractedCode

log = logging.getLogger(__name__)


@dataclass
class PackageInfo:
    """Information about a code package."""

    tarball_path: Path  # Path to the created tarball
    tarball_name: str  # Name of the tarball file
    package_name: str
    version: str
    callable_name: str
    callable_type: str
    code_hash: str
    size_bytes: int


class CodePackager:
    """
    Package source code into tarballs for deployment.

    Creates tarball packages containing:
    - Cleaned source code in baked_code/ directory
    - Package metadata (registry.json)
    - Dependencies information
    """

    def create_package(
        self,
        extracted_code: ExtractedCode,
        dependencies: Optional[List[str]] = None,
        system_dependencies: Optional[List[str]] = None,
        output_dir: Optional[Path] = None,
    ) -> PackageInfo:
        """
        Create a tarball package from extracted code.

        Args:
            extracted_code: Extracted code information
            dependencies: Python dependencies
            system_dependencies: System packages
            output_dir: Directory to save tarball (defaults to temp)

        Returns:
            PackageInfo with package details
        """
        # Use temp directory if no output specified
        if output_dir is None:
            output_dir = Path(tempfile.gettempdir()) / "tetra_packages"
            output_dir.mkdir(exist_ok=True)

        # Generate package name and version
        package_name = extracted_code.callable_name.lower().replace("_", "-")
        version = extracted_code.code_hash
        tarball_name = f"{package_name}_{version}.tar.gz"
        package_path = output_dir / tarball_name

        log.info(f"Creating package: {tarball_name}")

        # Create temporary staging directory
        with tempfile.TemporaryDirectory() as tmpdir:
            staging_dir = Path(tmpdir) / "package"
            staging_dir.mkdir()

            # Create baked_code directory structure (same as Docker image layout)
            baked_code_dir = staging_dir / "baked_code"
            baked_code_dir.mkdir()

            # Write cleaned code to module file
            module_file = baked_code_dir / f"{extracted_code.callable_name}.py"
            module_file.write_text(extracted_code.cleaned_code)
            log.debug(f"   Added code: {module_file.name}")

            # Create __init__.py
            init_file = baked_code_dir / "__init__.py"
            init_file.write_text("")

            # Create registry.json (same format as baked executor expects)
            registry = {
                extracted_code.callable_name: {
                    "module": f"baked_code.{extracted_code.callable_name}",
                    "name": extracted_code.callable_name,
                    "type": extracted_code.callable_type,
                }
            }
            registry_file = baked_code_dir / "registry.json"
            registry_file.write_text(json.dumps(registry, indent=2))
            log.debug(f"   Added registry: {registry_file.name}")

            # Create package metadata
            metadata = {
                "package_name": package_name,
                "version": version,
                "callable_name": extracted_code.callable_name,
                "callable_type": extracted_code.callable_type,
                "code_hash": extracted_code.code_hash,
                "dependencies": dependencies or [],
                "system_dependencies": system_dependencies or [],
            }
            metadata_file = staging_dir / "package_metadata.json"
            metadata_file.write_text(json.dumps(metadata, indent=2))
            log.debug(f"   Added metadata: {metadata_file.name}")

            # Create tarball
            self._create_tarball(staging_dir, package_path)

        # Get package size
        size_bytes = package_path.stat().st_size
        size_kb = size_bytes / 1024
        log.info(f"Package created: {package_path.name} ({size_kb:.1f} KB)")

        return PackageInfo(
            tarball_path=package_path,
            tarball_name=tarball_name,
            package_name=package_name,
            version=version,
            callable_name=extracted_code.callable_name,
            callable_type=extracted_code.callable_type,
            code_hash=extracted_code.code_hash,
            size_bytes=size_bytes,
        )

    def _create_tarball(self, source_dir: Path, output_path: Path) -> None:
        """
        Create gzipped tarball from directory.

        Args:
            source_dir: Directory to archive
            output_path: Output tarball path
        """
        with tarfile.open(output_path, "w:gz") as tar:
            # Add all files in source directory
            for item in source_dir.rglob("*"):
                if item.is_file():
                    # Add with relative path
                    arcname = item.relative_to(source_dir)
                    tar.add(item, arcname=arcname)
                    log.debug(f"      Archived: {arcname}")

    def extract_package(self, package_path: Path, output_dir: Path) -> Path:
        """
        Extract tarball package.

        Args:
            package_path: Path to tarball
            output_dir: Directory to extract to

        Returns:
            Path to extracted directory
        """
        log.info(f"📂 Extracting package: {package_path.name}")

        output_dir.mkdir(parents=True, exist_ok=True)

        with tarfile.open(package_path, "r:gz") as tar:
            tar.extractall(output_dir)

        log.info(f"Extracted to: {output_dir}")
        return output_dir

    def verify_package(self, package_path: Path) -> dict:
        """
        Verify package integrity and read metadata.

        Args:
            package_path: Path to tarball

        Returns:
            Package metadata dictionary

        Raises:
            ValueError: If package is invalid
        """
        if not package_path.exists():
            raise ValueError(f"Package not found: {package_path}")

        try:
            with tarfile.open(package_path, "r:gz") as tar:
                # Check for required files
                members = tar.getnames()

                if "package_metadata.json" not in members:
                    raise ValueError("Missing package_metadata.json in tarball")

                if "baked_code/registry.json" not in members:
                    raise ValueError("Missing baked_code/registry.json in tarball")

                # Extract and read metadata
                metadata_file = tar.extractfile("package_metadata.json")
                if metadata_file is None:
                    raise ValueError("Could not read package_metadata.json")

                metadata = json.load(metadata_file)

                log.debug(f"Package verified: {metadata.get('package_name')}")
                return metadata

        except (tarfile.TarError, json.JSONDecodeError) as e:
            raise ValueError(f"Invalid package: {e}") from e

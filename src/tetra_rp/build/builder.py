"""
Production builder orchestrator.

Main class that coordinates the entire production build process.
"""

import json
import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional

from .code_extractor import CodeExtractor, ExtractedCode
from .dockerfile_generator import DockerfileConfig, DockerfileGenerator
from .image_builder import BuildResult, ImageBuildConfig, ImageBuilder
from .registry_manager import RegistryManager

log = logging.getLogger(__name__)


@dataclass
class BuildConfig:
    """Complete build configuration."""

    func_or_class: Any
    resource_config: Any
    dependencies: Optional[List[str]] = None
    system_dependencies: Optional[List[str]] = None
    platform: str = "linux/amd64"


@dataclass
class BuildOutput:
    """Output from production build."""

    success: bool
    image_name: str
    local_image: str
    full_image: str
    extracted_code: ExtractedCode
    build_result: BuildResult
    message: str


class ProductionBuilder:
    """
    Orchestrate the entire production build process.

    This class coordinates:
    1. Code extraction and cleaning
    2. Dockerfile generation
    3. Docker image building
    4. Registry pushing
    5. Resource configuration updates
    """

    def __init__(
        self,
        code_extractor: Optional[CodeExtractor] = None,
        dockerfile_generator: Optional[DockerfileGenerator] = None,
        image_builder: Optional[ImageBuilder] = None,
        registry_manager: Optional[RegistryManager] = None,
    ):
        """
        Initialize production builder with component classes.

        Args:
            code_extractor: Code extraction handler
            dockerfile_generator: Dockerfile generation handler
            image_builder: Docker build handler
            registry_manager: Registry operations handler
        """
        self.code_extractor = code_extractor or CodeExtractor()
        self.dockerfile_generator = dockerfile_generator or DockerfileGenerator()
        self.image_builder = image_builder or ImageBuilder()
        self.registry_manager = registry_manager or RegistryManager()

    def build(self, config: BuildConfig) -> BuildOutput:
        """
        Execute complete production build pipeline.

        Args:
            config: Build configuration

        Returns:
            BuildOutput with results and status

        Raises:
            RuntimeError: If build fails at any stage
        """
        log.info("🔨 Building production image")

        # Step 1: Extract and process source code
        extracted = self.code_extractor.extract(config.func_or_class)
        log.info(f"   Callable: {extracted.callable_name} ({extracted.callable_type})")

        # Step 2: Get base image from resource config
        worker_base_image = getattr(
            config.resource_config, "imageName", "mwiki/tetra-worker:v1"
        )
        log.info(f"   Base: {worker_base_image}")

        # Step 3: Generate image name and tag
        image_name = extracted.callable_name.lower().replace("_", "-")
        image_tag = f"prod-{extracted.code_hash}"

        local_image = f"{image_name}:{image_tag}"
        full_image = self.registry_manager.get_full_image_name(image_name, image_tag)

        log.info(f"   Local image: {local_image}")
        if full_image != local_image:
            log.info(f"   Registry image: {full_image}")

        # Step 4: Create temporary build directory with baked code
        with tempfile.TemporaryDirectory() as tmpdir:
            build_dir = Path(tmpdir)
            baked_code_dir = build_dir / "baked_code"
            baked_code_dir.mkdir()

            # Write cleaned code to module file
            module_file = baked_code_dir / f"{extracted.callable_name}.py"
            module_file.write_text(extracted.cleaned_code)

            # Create __init__.py
            init_file = baked_code_dir / "__init__.py"
            init_file.write_text("")

            # Create registry.json
            registry = {
                extracted.callable_name: {
                    "module": f"baked_code.{extracted.callable_name}",
                    "type": extracted.callable_type,
                }
            }
            registry_file = baked_code_dir / "registry.json"
            registry_file.write_text(json.dumps(registry, indent=2))

            # Step 5: Generate Dockerfile
            dockerfile_config = DockerfileConfig(
                worker_base_image=worker_base_image,
                callable_name=extracted.callable_name,
                dependencies=config.dependencies or [],
                system_dependencies=config.system_dependencies or [],
            )
            dockerfile = self.dockerfile_generator.generate(dockerfile_config)
            dockerfile_path = build_dir / "Dockerfile"
            dockerfile_path.write_text(dockerfile)

            log.info(f"   Build dir: {build_dir}")

            # Step 6: Build Docker image
            build_config = ImageBuildConfig(
                build_dir=build_dir,
                image_name=image_name,
                image_tag=image_tag,
                platform=config.platform,
            )
            build_result = self.image_builder.build(build_config)

            if not build_result.success:
                raise RuntimeError(
                    f"Failed to build production image: {build_result.stderr}"
                )

        # Step 7: Tag for registry if needed
        if full_image != local_image:
            if not self.image_builder.tag_image(local_image, full_image):
                raise RuntimeError("Failed to tag image for registry")

        # Step 8: Push to registry if configured
        push_result = self.registry_manager.push_image(full_image)

        # Step 9: Update resource configuration
        self._update_resource_config(config.resource_config, full_image)

        log.info("✅ Production build complete")
        log.info(f"   Image: {full_image}")

        return BuildOutput(
            success=True,
            image_name=image_name,
            local_image=local_image,
            full_image=full_image,
            extracted_code=extracted,
            build_result=build_result,
            message=push_result.message or "Build successful",
        )

    def _update_resource_config(self, resource_config: Any, image: str) -> None:
        """
        Update resource configuration with production image.

        Args:
            resource_config: Resource configuration object
            image: Full image name to use
        """
        # Update image name
        resource_config.imageName = image

        # Set TETRA_BAKED_MODE environment variable
        if not hasattr(resource_config, "env") or resource_config.env is None:
            resource_config.env = {}
        resource_config.env["TETRA_BAKED_MODE"] = "true"

        log.info("Resource configured to use production image")
        log.info(f"   Image: {image}")
        log.info("   TETRA_BAKED_MODE=true")


def build_production_image(
    func_or_class: Any,
    resource_config: Any,
    dependencies: Optional[List[str]] = None,
    system_dependencies: Optional[List[str]] = None,
) -> BuildOutput:
    """
    Convenience function to build production image.

    This is the main entry point for production builds.

    Args:
        func_or_class: Function or class to build image for
        resource_config: Resource configuration object
        dependencies: List of Python dependencies
        system_dependencies: List of system packages

    Returns:
        BuildOutput with results

    Example:
        >>> @remote(LiveServerless(...), mode="prod")
        >>> def my_function():
        >>>     pass
    """
    builder = ProductionBuilder()

    config = BuildConfig(
        func_or_class=func_or_class,
        resource_config=resource_config,
        dependencies=dependencies,
        system_dependencies=system_dependencies,
    )

    return builder.build(config)

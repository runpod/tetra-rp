"""
Tetra Production Build System.

This module provides a modular, class-based architecture for building
production Docker images with baked code.

Main Components:
    - CodeExtractor: Extract and clean source code
    - DockerfileGenerator: Generate Dockerfiles
    - ImageBuilder: Execute Docker builds
    - RegistryManager: Handle registry operations
    - ProductionBuilder: Orchestrate the build process

Usage:
    # From decorator
    from tetra_rp.build import build_production_image

    result = build_production_image(
        func_or_class=my_function,
        resource_config=config,
        dependencies=["numpy"],
        system_dependencies=["git"]
    )

    # From CLI or custom scripts
    from tetra_rp.build import ProductionBuilder, BuildConfig

    builder = ProductionBuilder()
    config = BuildConfig(
        func_or_class=my_function,
        resource_config=config,
        dependencies=["numpy"]
    )
    result = builder.build(config)
"""

from .builder import (
    BuildConfig,
    BuildOutput,
    ProductionBuilder,
    build_production_image,
)
from .code_extractor import CodeExtractor, ExtractedCode
from .dockerfile_generator import DockerfileConfig, DockerfileGenerator
from .image_builder import BuildResult, ImageBuildConfig, ImageBuilder
from .registry_manager import PushResult, RegistryConfig, RegistryManager

__all__ = [
    # Main entry point
    "build_production_image",
    # Core classes
    "ProductionBuilder",
    "CodeExtractor",
    "DockerfileGenerator",
    "ImageBuilder",
    "RegistryManager",
    # Configuration classes
    "BuildConfig",
    "DockerfileConfig",
    "ImageBuildConfig",
    "RegistryConfig",
    # Result classes
    "BuildOutput",
    "ExtractedCode",
    "BuildResult",
    "PushResult",
]

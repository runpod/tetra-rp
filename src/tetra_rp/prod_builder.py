"""
Automatic production image builder for @remote decorated code.

DEPRECATED: This module now acts as a thin wrapper around the new
modular build system in tetra_rp.build.

For new code, import directly from tetra_rp.build:
    from tetra_rp.build import build_production_image

This module is maintained for backward compatibility.
"""

import logging
from typing import List, Optional

from .build import build_production_image as _build_production_image

log = logging.getLogger(__name__)


def build_and_deploy_prod_image(
    func_or_class,
    resource_config,
    dependencies: Optional[List[str]],
    system_dependencies: Optional[List[str]],
):
    """
    Build production Docker image and configure resource to use it.

    This is called automatically when mode="prod" is set on @remote decorator.

    DEPRECATED: This function now delegates to the new modular build system.
    For new code, use: from tetra_rp.build import build_production_image

    Args:
        func_or_class: Function or class to build
        resource_config: Resource configuration object
        dependencies: List of Python dependencies
        system_dependencies: List of system packages
    """
    # Delegate to new modular build system
    result = _build_production_image(
        func_or_class=func_or_class,
        resource_config=resource_config,
        dependencies=dependencies,
        system_dependencies=system_dependencies,
    )

    if not result.success:
        raise RuntimeError(f"Production build failed: {result.message}")

    return result

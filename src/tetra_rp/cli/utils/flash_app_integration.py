"""Integration helpers for FlashApp state manager and handler registration.

This module provides interfaces for registering discovered handlers with the FlashApp
state manager. Once FlashApp is implemented, these functions will integrate with the
actual state management system.
"""

from pathlib import Path

from tetra_rp.cli.utils.handler_discovery import DiscoveryResult, HandlerMetadata


async def register_handlers_with_state_manager(
    app_name: str, discovery_result: DiscoveryResult, tarball_path: Path
) -> None:
    """Register discovered handlers with FlashApp state manager.

    This function will integrate with the FlashApp class once it's implemented.
    For now, handlers are stored in .flash_handlers.json within the tarball.

    Args:
        app_name: Name of the Flash application
        discovery_result: Handler discovery results
        tarball_path: Path to the built tarball

    Example integration (future):
        ```python
        from tetra_rp.core.resources.app import FlashApp

        async def register_handlers_with_state_manager(app_name, discovery_result, tarball_path):
            app = await FlashApp.from_name(app_name)
            for handler in discovery_result.handlers:
                await app.register_handler(
                    handler_id=handler.handler_id,
                    handler_type=handler.handler_type,
                    serverless_config=handler.serverless_config,
                    routes=handler.routes,
                )
            await app.upload_build(tarball_path)
        ```
    """
    # TODO: Implement when FlashApp state manager is available
    # For now, handlers are embedded in .flash_handlers.json in the tarball
    pass


def create_handler_deployment_config(handler: HandlerMetadata) -> dict:
    """Create deployment configuration for a handler.

    Generates the configuration needed to deploy a handler as a serverless function
    or load-balanced service based on its type and routes.

    Args:
        handler: Handler metadata

    Returns:
        Deployment configuration dictionary for Runpod/orchestration
    """
    base_config = {
        "handler_id": handler.handler_id,
        "handler_type": handler.handler_type,
        "routes": handler.routes,
    }

    # Merge with serverless configuration
    if handler.serverless_config:
        base_config.update(handler.serverless_config)

    return base_config


def validate_handler_for_deployment(handler: HandlerMetadata) -> tuple[bool, list[str]]:
    """Validate that a handler is ready for deployment.

    Args:
        handler: Handler metadata to validate

    Returns:
        Tuple of (is_valid, list of validation errors)
    """
    errors = []

    if not handler.routes:
        errors.append(f"Handler '{handler.handler_id}' has no routes defined")

    if not handler.handler_id:
        errors.append("Handler ID is required")

    if handler.handler_type not in ("queue", "load_balancer"):
        errors.append(f"Invalid handler type: {handler.handler_type}")

    # Validate serverless config if present
    if handler.serverless_config:
        serverless = handler.serverless_config.get("serverless", {})
        if serverless:
            if "scalerType" in serverless and serverless["scalerType"] not in (
                "QUEUE_DELAY",
                "REQUEST_COUNT",
            ):
                errors.append(f"Invalid scalerType: {serverless['scalerType']}")

            if "type" in serverless and serverless["type"] not in ("QB", "LB"):
                errors.append(f"Invalid type: {serverless['type']}")

            if "workersMin" in serverless and "workersMax" in serverless:
                if serverless["workersMin"] > serverless["workersMax"]:
                    errors.append("workersMin cannot exceed workersMax")

    return (len(errors) == 0, errors)

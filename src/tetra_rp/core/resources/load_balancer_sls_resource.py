"""
LoadBalancerSlsResource - Resource type for RunPod Load-Balanced Serverless endpoints.

Load-balanced endpoints expose HTTP servers directly to clients without the queue-based
processing model of standard serverless endpoints. They're ideal for REST APIs, webhooks,
and real-time communication patterns.

Key differences from standard serverless (QB):
- Requests route directly to healthy workers via HTTP
- No automatic retries (client responsible)
- Lower latency but less fault tolerance
- Requires HTTP application, not a function handler
- Health checks via /ping endpoint
"""

import asyncio
import logging
from typing import Optional

import httpx
from pydantic import model_validator

from .serverless import ServerlessResource, ServerlessType, ServerlessScalerType

log = logging.getLogger(__name__)

# Configuration constants
DEFAULT_HEALTH_CHECK_RETRIES = 10
DEFAULT_HEALTH_CHECK_INTERVAL = 5  # seconds between retries
DEFAULT_PING_REQUEST_TIMEOUT = 5.0  # seconds
HEALTHY_STATUS_CODES = (200, 204)


class LoadBalancerSlsResource(ServerlessResource):
    """
    Resource configuration for RunPod Load-Balanced Serverless endpoints.

    Load-balanced endpoints expose HTTP servers directly, making them suitable for:
    - REST APIs
    - WebSocket servers
    - Real-time streaming
    - Custom HTTP protocols

    Configuration example:
        mothership = LoadBalancerSlsResource(
            name="mothership",
            imageName="my-mothership:latest",
            env={"FLASH_APP": "my_app"},
            workersMin=1,
            workersMax=3,
        )
        await mothership.deploy()
    """

    # Override default type to LB
    type: Optional[ServerlessType] = ServerlessType.LB

    def __init__(self, **data):
        """Initialize LoadBalancerSlsResource with LB-specific defaults."""
        # Ensure type is always LB
        data["type"] = ServerlessType.LB

        # LB endpoints shouldn't use queue-based scaling
        if "scalerType" not in data:
            data["scalerType"] = ServerlessScalerType.REQUEST_COUNT

        super().__init__(**data)

    @model_validator(mode="after")
    def set_serverless_template(self):
        """Create template from imageName if not provided.

        Must run after sync_input_fields to ensure all input fields are synced.
        """
        if not any([self.imageName, self.template, self.templateId]):
            raise ValueError(
                "Either imageName, template, or templateId must be provided"
            )

        if not self.templateId and not self.template:
            self.template = self._create_new_template()
        elif self.template:
            self._configure_existing_template()

        return self

    def _validate_lb_configuration(self) -> None:
        """
        Validate LB-specific configuration constraints.

        Raises:
            ValueError: If configuration violates LB requirements
        """
        # LB must use REQUEST_COUNT scaler, not QUEUE_DELAY
        if self.scalerType == ServerlessScalerType.QUEUE_DELAY:
            raise ValueError(
                f"LoadBalancerSlsResource requires REQUEST_COUNT scaler, "
                f"not {self.scalerType.value}. "
                "Load-balanced endpoints don't support queue-based scaling."
            )

        # Type must always be LB
        if self.type != ServerlessType.LB:
            raise ValueError(
                f"LoadBalancerSlsResource type must be LB, got {self.type.value}"
            )

    async def is_deployed_async(self) -> bool:
        """
        Check if LB endpoint is deployed and /ping endpoint is responding.

        For LB endpoints, we verify:
        1. Endpoint ID exists (created in RunPod)
        2. /ping endpoint returns 200 or 204
        3. Endpoint is in healthy state

        Returns:
            True if endpoint is deployed and healthy, False otherwise
        """
        try:
            if not self.id:
                return False

            # Use async health check for LB endpoints
            return await self._check_ping_endpoint()

        except Exception as e:
            log.debug(f"Error checking {self}: {e}")
            return False

    async def _check_ping_endpoint(self) -> bool:
        """
        Check if /ping endpoint is accessible and healthy.

        RunPod load-balancer endpoints require a /ping endpoint that returns:
        - 200 OK: Worker is healthy and ready
        - 204 No Content: Worker is initializing
        - Other status: Worker is unhealthy

        Returns:
            True if /ping endpoint responds with 200 or 204
        """
        try:
            if not self.id:
                return False

            ping_url = f"{self.endpoint_url}/ping"

            async with httpx.AsyncClient(
                timeout=DEFAULT_PING_REQUEST_TIMEOUT
            ) as client:
                response = await client.get(ping_url)
                return response.status_code in HEALTHY_STATUS_CODES
        except Exception as e:
            log.debug(f"Ping check failed for {self.name}: {e}")
            return False

    async def _wait_for_health(
        self,
        max_retries: int = DEFAULT_HEALTH_CHECK_RETRIES,
        retry_interval: int = DEFAULT_HEALTH_CHECK_INTERVAL,
    ) -> bool:
        """
        Poll /ping endpoint until endpoint is healthy or timeout.

        Args:
            max_retries: Number of health check attempts
            retry_interval: Seconds between health check attempts

        Returns:
            True if endpoint became healthy, False if timeout

        Raises:
            ValueError: If endpoint ID not set
        """
        if not self.id:
            raise ValueError("Cannot wait for health: endpoint not deployed")

        log.info(
            f"Waiting for LB endpoint {self.name} ({self.id}) to become healthy... "
            f"(max {max_retries} retries, {retry_interval}s interval)"
        )

        for attempt in range(max_retries):
            try:
                if await self._check_ping_endpoint():
                    log.info(
                        f"LB endpoint {self.name} is healthy (attempt {attempt + 1})"
                    )
                    return True

                log.debug(
                    f"Health check attempt {attempt + 1}/{max_retries} - "
                    f"endpoint not ready yet"
                )

            except Exception as e:
                log.debug(f"Health check attempt {attempt + 1} failed: {e}")

            # Wait before next attempt (except on last attempt)
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_interval)

        log.error(
            f"LB endpoint {self.name} failed to become healthy after "
            f"{max_retries} attempts"
        )
        return False

    async def _do_deploy(self) -> "LoadBalancerSlsResource":
        """
        Deploy LB endpoint and wait for health.

        Deployment flow:
        1. Validate LB configuration
        2. Call parent deploy (creates endpoint in RunPod)
        3. Poll /ping endpoint until healthy or timeout
        4. Return deployed resource

        Returns:
            Deployed LoadBalancerSlsResource instance

        Raises:
            ValueError: If LB configuration invalid or deployment fails
            TimeoutError: If /ping endpoint doesn't respond in time
        """
        # Validate before deploying
        self._validate_lb_configuration()

        # Check if already deployed
        if self.is_deployed():
            log.debug(f"{self} already deployed")
            return self

        try:
            # Call parent deploy (creates endpoint via RunPod API)
            log.info(f"Deploying LB endpoint {self.name}...")
            deployed = await super()._do_deploy()

            # Wait for /ping endpoint to become available
            timeout_seconds = (
                DEFAULT_HEALTH_CHECK_RETRIES * DEFAULT_HEALTH_CHECK_INTERVAL
            )
            log.info(
                f"Endpoint created, waiting for /ping to respond "
                f"({timeout_seconds}s timeout)..."
            )

            healthy = await self._wait_for_health(
                max_retries=DEFAULT_HEALTH_CHECK_RETRIES,
                retry_interval=DEFAULT_HEALTH_CHECK_INTERVAL,
            )

            if not healthy:
                raise TimeoutError(
                    f"LB endpoint {self.name} ({deployed.id}) failed to become "
                    f"healthy within {timeout_seconds}s"
                )

            log.info(f"LB endpoint {self.name} ({deployed.id}) deployed and healthy")
            return deployed

        except Exception as e:
            log.error(f"Failed to deploy LB endpoint {self.name}: {e}")
            raise

    def is_deployed(self) -> bool:
        """
        Override is_deployed to use async health check.

        Note: This is a synchronous wrapper around the async health check.
        Prefer is_deployed_async() in async contexts.

        Returns:
            True if endpoint is deployed and /ping responds
        """
        if not self.id:
            return False

        try:
            # Try the RunPod SDK health check (works for basic connectivity)
            response = self.endpoint.health()
            return response is not None
        except Exception as e:
            log.debug(f"RunPod health check failed for {self.name}: {e}")
            return False

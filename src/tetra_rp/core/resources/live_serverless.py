# Ship serverless code as you write it. No builds, no deploys — just run.
import os

from pydantic import model_validator

from .load_balancer_sls_resource import (
    CpuLoadBalancerSlsResource,
    LoadBalancerSlsResource,
)
from .serverless import ServerlessEndpoint
from .serverless_cpu import CpuServerlessEndpoint

TETRA_IMAGE_TAG = os.environ.get("TETRA_IMAGE_TAG", "latest")
TETRA_GPU_IMAGE = os.environ.get(
    "TETRA_GPU_IMAGE", f"runpod/tetra-rp:{TETRA_IMAGE_TAG}"
)
TETRA_CPU_IMAGE = os.environ.get(
    "TETRA_CPU_IMAGE", f"runpod/tetra-rp-cpu:{TETRA_IMAGE_TAG}"
)
TETRA_LB_IMAGE = os.environ.get(
    "TETRA_LB_IMAGE", f"runpod/tetra-rp-lb:{TETRA_IMAGE_TAG}"
)
TETRA_CPU_LB_IMAGE = os.environ.get(
    "TETRA_CPU_LB_IMAGE", f"runpod/tetra-rp-lb-cpu:{TETRA_IMAGE_TAG}"
)


class LiveServerlessMixin:
    """Common mixin for live serverless endpoints that locks the image."""

    @property
    def _live_image(self) -> str:
        """Override in subclasses to specify the locked image."""
        raise NotImplementedError("Subclasses must define _live_image")

    @property
    def imageName(self):
        # Lock imageName to specific image
        return self._live_image

    @imageName.setter
    def imageName(self, value):
        # Prevent manual setting of imageName
        pass


class LiveServerless(LiveServerlessMixin, ServerlessEndpoint):
    """GPU-only live serverless endpoint."""

    @property
    def _live_image(self) -> str:
        return TETRA_GPU_IMAGE

    @model_validator(mode="before")
    @classmethod
    def set_live_serverless_template(cls, data: dict):
        """Set default GPU image for Live Serverless."""
        data["imageName"] = TETRA_GPU_IMAGE
        return data


class CpuLiveServerless(LiveServerlessMixin, CpuServerlessEndpoint):
    """CPU-only live serverless endpoint with automatic disk sizing."""

    @property
    def _live_image(self) -> str:
        return TETRA_CPU_IMAGE

    @model_validator(mode="before")
    @classmethod
    def set_live_serverless_template(cls, data: dict):
        """Set default CPU image for Live Serverless."""
        data["imageName"] = TETRA_CPU_IMAGE
        return data


class LiveLoadBalancer(LiveServerlessMixin, LoadBalancerSlsResource):
    """Live load-balanced endpoint for local development and testing.

    Similar to LiveServerless but for HTTP-based load-balanced endpoints.
    Enables local testing of @remote decorated functions with LB endpoints
    before deploying to production.

    Features:
    - Locks to Tetra LB image (tetra-rp-lb)
    - Direct HTTP execution (not queue-based)
    - Local development with flash run
    - Same @remote decorator pattern as LoadBalancerSlsResource

    Usage:
        from tetra_rp import LiveLoadBalancer, remote

        api = LiveLoadBalancer(name="api-service")

        @remote(api, method="POST", path="/api/process")
        async def process_data(x: int, y: int):
            return {"result": x + y}

        # Test locally
        result = await process_data(5, 3)

    Local Development Flow:
        1. Create LiveLoadBalancer with routing
        2. Decorate functions with @remote(lb_resource, method=..., path=...)
        3. Run with `flash run` to start local endpoint
        4. Call functions directly in tests or scripts
        5. Deploy to production with `flash build` and `flash deploy`

    Note:
        The endpoint_url is configured by the Flash runtime when the
        endpoint is deployed locally. For true local testing without
        deployment, use the functions directly or mock the HTTP layer.
    """

    @property
    def _live_image(self) -> str:
        return TETRA_LB_IMAGE

    @model_validator(mode="before")
    @classmethod
    def set_live_lb_template(cls, data: dict):
        """Set default image for Live Load-Balanced endpoint."""
        data["imageName"] = TETRA_LB_IMAGE
        return data


class CpuLiveLoadBalancer(LiveServerlessMixin, CpuLoadBalancerSlsResource):
    """CPU-only live load-balanced endpoint for local development and testing.

    Similar to LiveLoadBalancer but configured for CPU instances with
    automatic disk sizing and validation.

    Features:
    - Locks to CPU Tetra LB image (tetra-rp-lb-cpu)
    - CPU instance support with automatic disk sizing
    - Direct HTTP execution (not queue-based)
    - Local development with flash run
    - Same @remote decorator pattern as CpuLoadBalancerSlsResource

    Usage:
        from tetra_rp import CpuLiveLoadBalancer, remote

        api = CpuLiveLoadBalancer(name="api-service")

        @remote(api, method="POST", path="/api/process")
        async def process_data(x: int, y: int):
            return {"result": x + y}

        # Test locally
        result = await process_data(5, 3)

    Local Development Flow:
        1. Create CpuLiveLoadBalancer with routing
        2. Decorate functions with @remote(lb_resource, method=..., path=...)
        3. Run with `flash run` to start local endpoint
        4. Call functions directly in tests or scripts
        5. Deploy to production with `flash build` and `flash deploy`
    """

    @property
    def _live_image(self) -> str:
        return TETRA_CPU_LB_IMAGE

    @model_validator(mode="before")
    @classmethod
    def set_live_cpu_lb_template(cls, data: dict):
        """Set default CPU image for Live Load-Balanced endpoint."""
        data["imageName"] = TETRA_CPU_LB_IMAGE
        return data

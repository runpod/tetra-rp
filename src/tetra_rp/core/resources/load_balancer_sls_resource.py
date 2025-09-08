"""
LoadBalancerSls Resource Configuration

This module provides the LoadBalancerSlsResource class for configuring 
Load Balancer serverless endpoints with dual HTTP/remote execution capabilities.
"""

import os
from pydantic import model_validator
from .serverless import ServerlessResource

TETRA_IMAGE_TAG = os.environ.get("TETRA_IMAGE_TAG", "latest")
TETRA_GPU_IMAGE = os.environ.get(
    "TETRA_GPU_IMAGE", f"runpod/tetra-rp:{TETRA_IMAGE_TAG}"
)
TETRA_CPU_IMAGE = os.environ.get(
    "TETRA_CPU_IMAGE", f"runpod/tetra-rp-cpu:{TETRA_IMAGE_TAG}"
)


class LoadBalancerSlsResource(ServerlessResource):
    """
    LoadBalancerSls resource configuration for dual-capability endpoints.
    
    This class extends ServerlessResource to provide Load Balancer functionality
    that supports both HTTP endpoints (@endpoint methods) and remote execution.
    """

    @model_validator(mode="before")
    @classmethod
    def set_load_balancer_defaults(cls, data: dict):
        """Set default configuration for LoadBalancerSls resources."""
        # Always set type to LB for Load Balancer mode
        data["type"] = "LB"
        
        # Set default image based on instanceIds presence
        data["imageName"] = (
            TETRA_CPU_IMAGE if data.get("instanceIds") else TETRA_GPU_IMAGE
        )
        
        return data

    @property
    def imageName(self):
        """Lock imageName to always reflect instanceIds."""
        return (
            TETRA_CPU_IMAGE if getattr(self, "instanceIds", None) else TETRA_GPU_IMAGE
        )

    @property
    def type(self):
        """Always return 'LB' for LoadBalancerSls resources."""
        return "LB"
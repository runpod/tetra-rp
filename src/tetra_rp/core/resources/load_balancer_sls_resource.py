"""
LoadBalancerSls Resource Configuration

This module provides the LoadBalancerSlsResource class for configuring 
Load Balancer serverless endpoints with dual HTTP/remote execution capabilities.
"""

import os
from pydantic import model_validator
from .serverless import ServerlessResource
from .template import PodTemplate, KeyValuePair
from .serverless import get_env_vars

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
        # This ensures imageName is available for template creation
        if not data.get("imageName"):
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

    @model_validator(mode="after")
    def ensure_template_creation(self):
        """Ensure template is created for LoadBalancerSls deployment."""
        # Call the parent class template creation logic
        if not self.templateId and not self.template and self.imageName:
            self.template = PodTemplate(
                name=self.resource_id,
                imageName=self.imageName,
                env=KeyValuePair.from_dict(self.env or get_env_vars()),
            )
        elif self.template:
            self.template.name = f"{self.resource_id}__{self.template.resource_id}"
            if self.imageName:
                self.template.imageName = self.imageName
            if self.env:
                self.template.env = KeyValuePair.from_dict(self.env)
        
        return self
    
    def model_dump(self, **kwargs):
        """Override model_dump to ensure type='LB' is included."""
        data = super().model_dump(**kwargs)
        data["type"] = "LB"  # Ensure type is always included in serialization
        return data
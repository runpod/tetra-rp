from typing import Dict, List, Optional, Any
from pydantic import BaseModel, model_validator
from .base import BaseResource


class KeyValuePair(BaseModel):
    key: str
    value: str

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "List[KeyValuePair]":
        """
        Create a list of KeyValuePair instances from a dictionary.
        """
        if not isinstance(data, dict):
            raise ValueError("Input must be a dictionary.")

        return [cls(key=key, value=value) for key, value in data.items()]


class PodTemplate(BaseResource):
    advancedStart: Optional[bool] = False
    config: Optional[Dict[str, Any]] = {}
    containerDiskInGb: Optional[int] = 64
    containerRegistryAuthId: Optional[str] = ""
    dockerArgs: Optional[str] = ""
    env: Optional[List[KeyValuePair]] = []
    imageName: Optional[str] = ""
    name: Optional[str] = ""
    ports: Optional[str] = ""
    startScript: Optional[str] = ""

    @model_validator(mode="after")
    def sync_input_fields(self):
        self.name = f"{self.name}__{self.resource_id}"
        return self

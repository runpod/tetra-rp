from typing import Dict, List, Optional, Any
from pydantic import BaseModel


class KeyValuePair(BaseModel):
    key: str
    value: str


class TemplateResource(BaseModel):
    advancedStart: bool
    boundEndpointId: Optional[str] = None
    category: str
    config: Dict[str, Any]
    containerDiskInGb: int
    containerRegistryAuthId: Optional[str] = None
    dockerArgs: str
    earned: int
    env: Optional[List[KeyValuePair]] = []
    id: str
    imageName: str
    isPublic: bool
    isRunpod: bool
    isServerless: bool
    name: str
    ports: str
    readme: str
    runtimeInMin: int
    startJupyter: bool
    startScript: str
    startSsh: bool
    userId: str
    volumeInGb: int
    volumeMountPath: str

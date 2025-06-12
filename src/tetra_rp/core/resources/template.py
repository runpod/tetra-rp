import requests
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


def update_system_dependencies(template_id, token, system_dependencies, base_entry_cmd=None):
    """
    Updates RunPod template with system dependencies installed via apt-get,
    and appends the app start command.

    Args:
        template_id (str): RunPod template ID.
        token (str): RunPod API token.
        system_dependencies (List[str]): List of apt packages to install.
        base_entry_cmd (List[str]): The default command to run the app, e.g. ["uv", "run", "handler.py"]
    Returns:
        dict: API response JSON or error info.
    """

    # Compose apt-get install command if any packages specified
    apt_cmd = ""
    if system_dependencies:
        joined_pkgs = " ".join(system_dependencies)
        apt_cmd = f"apt-get update && apt-get install -y {joined_pkgs} && "

    # Default start command if not provided
    app_cmd = base_entry_cmd or ["uv", "run", "handler.py"]
    app_cmd_str = " ".join(app_cmd)

    # Full command to run in entrypoint shell
    full_cmd = f"{apt_cmd}exec {app_cmd_str}"

    payload = {
        # other required fields like disk, env, image, etc, should be fetched or passed in real usage
        "dockerEntrypoint": ["/bin/bash", "-c", full_cmd],
        "dockerStartCmd": [],
        # placeholder values, replace as needed or fetch from current template state
        "containerDiskInGb": 50,
        "containerRegistryAuthId": "",
        "env": {},
        "imageName": "your-image-name",
        "isPublic": False,
        "name": "your-template-name",
        "ports": ["8888/http", "22/tcp"],
        "readme": "",
        "volumeInGb": 20,
        "volumeMountPath": "/workspace"
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    url = f"https://rest.runpod.io/v1/templates/{template_id}/update"
    response = requests.post(url, json=payload, headers=headers)

    try:
        return response.json()
    except Exception:
        return {"error": "Invalid JSON response", "text": response.text}


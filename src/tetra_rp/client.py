import logging
from functools import wraps
from typing import List, Dict, Optional
from .core.resources import ServerlessResource, ResourceManager
from .stubs import stub_resource
from .core.api import RunpodRestClient


log = logging.getLogger(__name__)


# Funtion to create network volume
async def create_network_volume(datacenter_id: str, name: str, size: int) -> str:
    """
    Creates a network volume using the Runpod REST API.

    Args:
        datacenter_id (str): The ID of the datacenter where the network volume will be created.
        name (str): Name of the network volume.
        size (int): Size of the network volume in GB.

    Returns:
        str: The ID of the created network volume.
    """
    async with RunpodRestClient() as client:
        # Create the network volume
        volume = await client.create_network_volume(
            datacenter_id=datacenter_id, name=name, size=size
        )
        log.info(f"Created network volume: {volume['id']}")
        return volume["id"]


def remote(
    resource_config: ServerlessResource,
    dependencies: List[str] = None,
    system_dependencies: List[str] = None,
    mount_volume: Optional[Dict[str, str]] = None,
    **extra,
):
    """
    Decorator to enable dynamic resource provisioning and dependency management for serverless functions.

    This decorator allows a function to be executed in a remote serverless environment, with support for
    dynamic resource provisioning and installation of required dependencies.

        resource_config (ServerlessResource): Configuration object specifying the serverless resource
            to be provisioned or used.
        dependencies (List[str], optional): A list of pip package names to be installed in the remote
            environment before executing the function. Defaults to None.
        mount_volume (Dict[str, str], optional): Configuration for creating and mounting a network volume.
            Should contain 'size', 'datacenter_id', and 'name' keys. Defaults to None.
        extra (dict, optional): Additional parameters for the execution of the resource. Defaults to an empty dict.

    Returns:
        Callable: A decorator that wraps the target function, enabling remote execution with the
        specified resource configuration and dependencies.

    Example:
    ```python
        @remote(
            resource_config=my_resource_config,
            dependencies=["numpy", "pandas"],
            sync=True  # Optional, to run synchronously
        )
        async def my_function(data):
            # Function logic here
            pass
    ```
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Create netowrk volume if mount_volume is provided
            if mount_volume:
                try:
                    size = int(mount_volume.get("size", 10))  # Default size to 10GB
                    datacenter_id = mount_volume.get("datacenter_id")
                    name = mount_volume.get("name", "tetra-network-volume")
                    if not datacenter_id:
                        raise ValueError(
                            "datacenter_id is required for mounting volume"
                        )
                    network_volume_id = await create_network_volume(
                        datacenter_id=datacenter_id, name=name, size=size
                    )
                    resource_config.networkVolumeId = network_volume_id
                    log.info(
                        f"Updated resource config with network volume: {network_volume_id}"
                    )
                except Exception as e:
                    log.error(f"Failed to create or mount network volume: {e}")
                    raise

            resource_manager = ResourceManager()
            remote_resource = await resource_manager.get_or_deploy_resource(
                resource_config
            )

            stub = stub_resource(remote_resource, **extra)
            return await stub(func, dependencies, system_dependencies, *args, **kwargs)

        return wrapper

    return decorator

import pathlib
import requests
import asyncio
from typing import Dict, Callable, TYPE_CHECKING

from ..api.runpod import RunpodGraphQLClient
from ..resources.resource_manager import ResourceManager
from ..resources.serverless import ServerlessResource

if TYPE_CHECKING:
    from . import ServerlessResource

class FlashApp:
    def __init__(self, name: str):
        self.name: str = name
        self.id: str = ""
        self.resources: Dict[str, "ServerlessResource"] = {}
        with asyncio.Runner() as runner:
            runner.run(self._get_or_create_self())

    def remote(self, *args, **kwargs):
        from tetra_rp.client import remote as remote_decorator

        resource_config = kwargs.get("resource_config")

        if resource_config is None and args:
            candidate = args[0]
            if hasattr(candidate, "resource_id"):
                self.resources[candidate.resource_id] = candidate

        return remote_decorator(*args, **kwargs)

    async def _get_or_create_self(self):
        async with RunpodGraphQLClient() as client:
            try:
                result = await client.get_flash_app_by_name(self.name)
                self.id = result["flashAppByName"]["id"]
                return result
            except Exception as exc:
                if not "app not found" in str(exc).lower():
                    raise
            result = await client.create_flash_app({"name": self.name})

        self.id = result["createFlashApp"]["id"]
        return result

    async def _get_id_by_name(self):
        async with RunpodGraphQLClient() as client:
            result = await client.get_flash_app_by_name(self.name)
        if not result.get("flashAppByName"):
            raise ValueError("flash app not found", self.name)
        return result["flashAppByName"]["id"]

    async def create_environment(self, environment_name: str):
        async with RunpodGraphQLClient() as client:
            result = await client.create_flash_environment({"flashAppId": self.id, "name": environment_name})
        return result["createFlashEnvironment"]


    @staticmethod
    async def list():
        async with RunpodGraphQLClient() as client:
            return await client.list_flash_apps()
    
    async def _get_tarball_upload_url(self, tarball_size: int):
        async with RunpodGraphQLClient() as client:
            return await client.prepare_artifact_upload(
                {"flashAppId": self.id, "tarballSize": tarball_size}
            )
    
    async def _get_active_artifact(self, environment_id: str):
        async with RunpodGraphQLClient() as client:
            result = await client.get_flash_artifact_url(environment_id)
            if not result["flashEnvironment"].get("activeArtifact"):
                raise ValueError("No active artifact for environment id found", environment_id)
            return result["flashEnvironment"]["activeArtifact"]

    async def deploy_build_to_environment(self, environment_id: str, build_id: str):
        async with RunpodGraphQLClient() as client:
            result = await client.deploy_build_to_environment({"flashEnvironmentId": environment_id, "flashBuildId": build_id})
            return result

    async def download_tarball(self, environment_id: str, dest_file: str):
        result = await self._get_active_artifact(environment_id)
        url = result["downloadUrl"]
        with open(dest_file, "wb") as stream:
            with requests.get(url, stream=True) as resp:
                resp.raise_for_status()
                for chunk in resp.iter_content():
                    if chunk:
                        stream.write(chunk)
    
    async def _finalize_upload_build(self, object_key: str):
        async with RunpodGraphQLClient() as client:
            result = await client.finalize_artifact_upload(
                    {"flashAppId": self.id, "objectKey": object_key}
            )
            return result["finalizeFlashArtifactUpload"]
    
    async def upload_build(self, tar_path: str):
        path = pathlib.Path(tar_path)
        tarball_size = path.stat().st_size

        result = await self._get_tarball_upload_url(tarball_size)
        url = result["prepareFlashArtifactUpload"]["uploadUrl"]
        object_key = result["prepareFlashArtifactUpload"]["objectKey"]

        headers = {"Content-Type": "application/x-tar"}
        
        with path.open("rb") as fh:
            resp = requests.put(url, data=fh, headers=headers)
        
        resp.raise_for_status()
        resp = await self._finalize_upload_build(object_key)
        return resp

    async def _deploy_in_environment(self, environment: str):
        """
        Entrypoint for cpu sls endpoint to execute provisioning its registered resources.
        Goes through all registered resources and gets or deploys them
        Should update app env state as Ready at the end
        TODO(jhcipar) should add flash env into resource identifiers
        """
    async def _get_environment_by_name(self, environment_name: str):
        async with RunpodGraphQLClient() as client:
            result = await client.get_flash_environment_by_name({"flashAppId": self.id, "name": environment_name})
            return result["flashEnvironmentByName"]
        resource_manager = ResourceManager()
        for resource_id, resource in self.resources.items():
            await resource_manager.get_or_deploy_resource(resource)

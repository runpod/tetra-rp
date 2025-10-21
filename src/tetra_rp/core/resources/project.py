import pathlib
import requests
import asyncio
from typing import Dict, Callable, TYPE_CHECKING

from ..api.runpod import RunpodGraphQLClient
from ..resources.resource_manager import ResourceManager

if TYPE_CHECKING:
    from . import ServerlessResource

class FlashProject:
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
                result = await client.get_flash_project_by_name(self.name)
                self.id = result["flashProjectByName"]["id"]
                return result
            except Exception as exc:
                if not "project not found" in str(exc).lower():
                    raise
            result = await client.create_flash_project({"name": self.name})

        self.id = result["createFlashProject"]["id"]
        return result

    async def _get_id_by_name(self):
        async with RunpodGraphQLClient() as client:
            result = await client.get_flash_project_by_name(self.name)
        if not result.get("flashProjectByName"):
            raise ValueError("flash project not found", self.name)
        return result["flashProjectByName"]["id"]

    async def create_environment(self, environment_name: str):
        async with RunpodGraphQLClient() as client:
            result = await client.create_flash_environment({"flashProjectId": self.id, "name": environment_name})
        return result["createFlashEnvironment"]


    @staticmethod
    async def list():
        async with RunpodGraphQLClient() as client:
            return await client.list_flash_projects()
    
    async def _get_tarball_upload_url(self):
        async with RunpodGraphQLClient() as client:
            return await client.prepare_artifact_upload({"projectId": self.id})
    
    async def _get_active_artifact(self, environment_id: str):
        async with RunpodGraphQLClient() as client:
            result = await client.get_flash_artifact_url(environment_id)
            if not result["flashEnvironment"].get("activeArtifact"):
                raise ValueError("No active artifact for environment id found", environment_id)
            return result["flashEnvironment"]["activeArtifact"]

    async def deploy_build_to_environment(self, environment_id: str, build_id: str):
        async with RunpodGraphQLClient() as client:
            result = await client.deploy_build_to_environment({"environmentId": environment_id, "flashBuildId": build_id})
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
    
    async def _finalize_tarball_upload(self, object_key: str):
        async with RunpodGraphQLClient() as client:
            result = await client.finalize_artifact_upload(
                {"projectId": self.id, "objectKey": object_key}
            )
            return result["finalizeFlashArtifactUpload"]
    
    async def upload_tarball(self, tar_path: str):
        result = await self._get_tarball_upload_url()
        url = result["prepareFlashArtifactUpload"]["uploadUrl"]
        object_key = result["prepareFlashArtifactUpload"]["objectKey"]
        
        path = pathlib.Path(tar_path)
        headers = {"Content-Type": "application/x-tar"}
        
        with path.open("rb") as fh:
            resp = requests.put(url, data=fh, headers=headers)
        
        resp.raise_for_status()
        resp = await self._finalize_tarball_upload(object_key)
        return resp

    async def _deploy_in_environment(self, environment: str):
        """
        Entrypoint for cpu sls endpoint to execute provisioning its registered resources.
        Goes through all registered resources and gets or deploys them
        Should update app env state as Ready at the end
        TODO(jhcipar) should add flash env into resource identifiers
        """
        resource_manager = ResourceManager()
        for resource_id, resource in self.resources.items():
            await resource_manager.get_or_deploy_resource(resource)

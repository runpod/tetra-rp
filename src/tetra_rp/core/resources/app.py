from pathlib import Path
import requests
import asyncio
from typing import Dict, Optional, Union, TYPE_CHECKING
import logging

from ..api.runpod import RunpodGraphQLClient
from ..resources.resource_manager import ResourceManager
from ..resources.serverless import ServerlessEndpoint, NetworkVolume

if TYPE_CHECKING:
    from . import ServerlessResource

log = logging.getLogger(__name__)


class FlashApp:
    """
    A flash app serves as the entrypoint for interacting with and managing Flash applications.
    The primary entrypoint that it's used is to run a script using the Flash library.
    An instance of this class will eagerly create an application in Runpod by creating an async event loop.
    To create a flash app from an async event loop, use FlashApp.create()


    to limit how much we query our gql, follow this philosophy:
        list requests fetch only top-level attributes, no child resources
        child resources can be descriptively fetched by querying them by id (or name, in some cases)
        except in special cases, direct resource queries only fetch one level deeper than the parent
        (eg flashAppById will fetch an app and its environments and builds, but not resources for all envs)
    """

    def __init__(self, name: str, id: Optional[str] = "", eager_hydrate: bool = True):
        self.name: str = name
        self.id: Optional[str] = id
        self.resources: Dict[str, "ServerlessResource"] = {}
        self._hydrated = False
        if eager_hydrate:
            asyncio.run(self._hydrate())

    def remote(self, *args, **kwargs):
        from tetra_rp.client import remote as remote_decorator

        resource_config = kwargs.get("resource_config")

        if resource_config is None and args:
            candidate = args[0]
            if hasattr(candidate, "resource_id"):
                self.resources[candidate.resource_id] = candidate

        return remote_decorator(*args, **kwargs)

    async def _hydrate(self):
        if self._hydrated:
            log.debug("App is already hydrated while calling hydrate. Returning")
            self._hydrated = True
            return

        log.debug("Hydrating app")
        async with RunpodGraphQLClient() as client:
            try:
                result = await client.get_flash_app_by_name(self.name)
                found_id = result["id"]

                # if an id is attached to instance check if it makes sense
                if self.id:
                    if self.id != found_id:
                        raise ValueError(
                            "provided id for app class does not match existing app resource."
                        )
                    self._hydrated = True
                    return self
                self.id = found_id
                self._hydrated = True
                return self

            except Exception as exc:
                if "app not found" not in str(exc).lower():
                    raise
            result = await client.create_flash_app({"name": self.name})
            self.id = result["id"]

        self._hydrated = True

    async def _get_id_by_name(self):
        async with RunpodGraphQLClient() as client:
            result = await client.get_flash_app_by_name(self.name)
        if not result.get("id"):
            raise ValueError("flash app not found", self.name)
        return result["id"]

    async def create_environment(self, environment_name: str):
        await self._hydrate()
        async with RunpodGraphQLClient() as client:
            result = await client.create_flash_environment(
                {"flashAppId": self.id, "name": environment_name}
            )
        return result

    async def _get_tarball_upload_url(self, tarball_size: int):
        await self._hydrate()
        async with RunpodGraphQLClient() as client:
            return await client.prepare_artifact_upload(
                {"flashAppId": self.id, "tarballSize": tarball_size}
            )

    async def _get_active_artifact(self, environment_id: str):
        await self._hydrate()
        async with RunpodGraphQLClient() as client:
            result = await client.get_flash_artifact_url(environment_id)
            if not result.get("activeArtifact"):
                raise ValueError(
                    "No active artifact for environment id found", environment_id
                )
            return result["activeArtifact"]

    async def deploy_build_to_environment(
        self,
        build_id: str,
        environment_id: Optional[str] = "",
        environment_name: Optional[str] = "",
    ):
        if (not environment_id and not environment_name) or (
            environment_name and environment_id
        ):
            raise ValueError(
                "One of environment name or environment id must be provided."
            )

        await self._hydrate()
        async with RunpodGraphQLClient() as client:
            if not environment_id:
                environment = await client.get_flash_environment_by_name(
                    {"flashAppId": self.id, "name": environment_name}
                )
                environment_id = environment["id"]
            result = await client.deploy_build_to_environment(
                {"flashEnvironmentId": environment_id, "flashBuildId": build_id}
            )
            return result

    async def download_tarball(self, environment_id: str, dest_file: str):
        await self._hydrate()
        result = await self._get_active_artifact(environment_id)
        url = result["downloadUrl"]
        with open(dest_file, "wb") as stream:
            with requests.get(url, stream=True) as resp:
                resp.raise_for_status()
                for chunk in resp.iter_content():
                    if chunk:
                        stream.write(chunk)

    async def _finalize_upload_build(self, object_key: str):
        await self._hydrate()
        async with RunpodGraphQLClient() as client:
            result = await client.finalize_artifact_upload(
                {"flashAppId": self.id, "objectKey": object_key}
            )
            return result

    async def _register_endpoint_to_environment(
        self, environment_id: str, endpoint_id: str
    ):
        await self._hydrate()
        async with RunpodGraphQLClient() as client:
            result = await client.register_endpoint_to_environment(
                {"flashEnvironmentId": environment_id, "endpointId": endpoint_id}
            )
            return result

    async def _register_network_volume_to_environment(
        self, environment_id: str, network_volume_id: str
    ):
        await self._hydrate()
        async with RunpodGraphQLClient() as client:
            result = await client.register_network_volume_to_environment(
                {
                    "flashEnvironmentId": environment_id,
                    "networkVolumeId": network_volume_id,
                }
            )
            return result

    async def upload_build(self, tar_path: Union[str, Path]):
        await self._hydrate()
        if isinstance(tar_path, str):
            tar_path = Path(tar_path)
        tarball_size = tar_path.stat().st_size

        result = await self._get_tarball_upload_url(tarball_size)
        url = result["uploadUrl"]
        object_key = result["objectKey"]

        headers = {"Content-Type": "application/gzip"}

        with tar_path.open("rb") as fh:
            resp = requests.put(url, data=fh, headers=headers)

        resp.raise_for_status()
        resp = await self._finalize_upload_build(object_key)
        return resp

    async def _set_environment_state(self, environment_id: str, status: str):
        await self._hydrate()
        async with RunpodGraphQLClient() as client:
            await client.set_environment_state(
                {"flashEnvironmentId": environment_id, "status": status}
            )

    async def _get_environment_by_name(self, environment_name: str):
        await self._hydrate()
        async with RunpodGraphQLClient() as client:
            result = await client.get_flash_environment_by_name(
                {"flashAppId": self.id, "name": environment_name}
            )
            return result["flashEnvironmentByName"]

    async def deploy_resources(self, environment_name: str):
        await self._hydrate()
        resource_manager = ResourceManager()
        environment = await self._get_environment_by_name(environment_name)

        # NOTE(jhcipar) it's pretty fragile to have client managed state like this
        # we should enforce this on the server side eventually and either debounce or not allow subsequent deploys
        await self._set_environment_state(environment["id"], "DEPLOYING")

        for resource_id, resource in self.resources.items():
            deployed_resource = await resource_manager.get_or_deploy_resource(resource)
            if isinstance(deployed_resource, ServerlessEndpoint):
                await self._register_endpoint_to_environment(
                    environment["id"], deployed_resource.id
                )
            if isinstance(deployed_resource, NetworkVolume):
                await self._register_network_volume_to_environment(
                    environment["id"], deployed_resource.id
                )

        # NOTE(jhcipar) we should healthcheck endpoints after provisioning them, for right now we just
        # assume this is healthy
        await self._set_environment_state(environment["id"], "HEALTHY")

    @classmethod
    async def from_name(cls, app_name: str) -> "FlashApp":
        async with RunpodGraphQLClient() as client:
            result = await client.get_flash_app_by_name(app_name)
        return cls(app_name, id=result["id"], eager_hydrate=False)

    @classmethod
    async def create(cls, app_name: str) -> "FlashApp":
        async with RunpodGraphQLClient() as client:
            result = await client.create_flash_app({"name": app_name})
        return cls(app_name, id=result["id"], eager_hydrate=False)

    @classmethod
    async def list(cls):
        async with RunpodGraphQLClient() as client:
            return await client.list_flash_apps()

    async def get_build(self, build_id: str):
        await self._hydrate()
        async with RunpodGraphQLClient() as client:
            return await client.get_flash_build({"flashBuildId": build_id})

    async def list_builds(self):
        await self._hydrate()
        async with RunpodGraphQLClient() as client:
            result = await client.get_flash_app_by_name(self.name)
            return result["flashBuilds"]

    async def list_environments(self):
        await self._hydrate()
        async with RunpodGraphQLClient() as client:
            result = await client.get_flash_app_by_name(self.name)
            return result["flashEnvironments"]

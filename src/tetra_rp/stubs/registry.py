import logging
from functools import singledispatch

from ..core.resources import (
    CpuLiveServerless,
    CpuServerlessEndpoint,
    LiveServerless,
    ServerlessEndpoint,
)
from .live_serverless import LiveServerlessStub
from .serverless import ServerlessEndpointStub

log = logging.getLogger(__name__)


@singledispatch
def stub_resource(resource, **extra):
    async def fallback(*args, **kwargs):
        return {"error": f"Cannot stub {resource.__class__.__name__}."}

    return fallback


def _create_live_serverless_stub(resource, **extra):
    """Create a live serverless stub for both LiveServerless and CpuLiveServerless."""
    stub = LiveServerlessStub(resource)

    # Function execution
    async def stubbed_resource(
        func,
        dependencies,
        system_dependencies,
        accelerate_downloads,
        *args,
        **kwargs,
    ) -> dict:
        if args == (None,):
            args = []

        request = stub.prepare_request(
            func,
            dependencies,
            system_dependencies,
            accelerate_downloads,
            *args,
            **kwargs,
        )
        response = await stub.ExecuteFunction(request)
        return stub.handle_response(response)

    # Class method execution
    async def execute_class_method(request):
        response = await stub.ExecuteFunction(request)
        return stub.handle_response(response)

    # Attach the method to the function
    stubbed_resource.execute_class_method = execute_class_method

    return stubbed_resource


@stub_resource.register(LiveServerless)
def _(resource, **extra):
    return _create_live_serverless_stub(resource, **extra)


@stub_resource.register(CpuLiveServerless)
def _(resource, **extra):
    return _create_live_serverless_stub(resource, **extra)


@stub_resource.register(ServerlessEndpoint)
def _(resource, **extra):
    async def stubbed_resource(
        func,
        dependencies,
        system_dependencies,
        accelerate_downloads,
        *args,
        **kwargs,
    ) -> dict:
        if dependencies or system_dependencies:
            log.warning(
                "Dependencies are not supported for ServerlessEndpoint. "
                "They will be ignored."
            )

        stub = ServerlessEndpointStub(resource)
        payload = stub.prepare_payload(func, *args, **kwargs)
        response = await stub.execute(payload, sync=extra.get("sync", False))
        return stub.handle_response(response)

    return stubbed_resource


@stub_resource.register(CpuServerlessEndpoint)
def _(resource, **extra):
    async def stubbed_resource(
        func,
        dependencies,
        system_dependencies,
        accelerate_downloads,
        *args,
        **kwargs,
    ) -> dict:
        if dependencies or system_dependencies:
            log.warning(
                "Dependencies are not supported for CpuServerlessEndpoint. "
                "They will be ignored."
            )

        stub = ServerlessEndpointStub(resource)
        payload = stub.prepare_payload(func, *args, **kwargs)
        response = await stub.execute(payload, sync=extra.get("sync", False))
        return stub.handle_response(response)

    return stubbed_resource

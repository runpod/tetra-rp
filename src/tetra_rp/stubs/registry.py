from functools import singledispatch
from .live_serverless import LiveServerlessStub
from ..core.resources import LiveServerless
from tetra_rp import get_logger


log = get_logger("stubs")


@singledispatch
async def stub_resource(resource):
    return {"error": f"Cannot stub {resource.__class__.__name__}."}


@stub_resource.register(LiveServerless)
def _(resource):
    async def stubbed_resource(func, dependencies, *args, **kwargs) -> dict:
        if args == (None,):
            # cleanup: when the function is called with no args
            args = []

        stub = LiveServerlessStub(resource)
        request = stub.prepare_request(func, dependencies, *args, **kwargs)
        response = await stub.ExecuteFunction(request)
        return stub.handle_response(response)

    return stubbed_resource

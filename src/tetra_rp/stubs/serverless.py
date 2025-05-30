from typing import Any, Union
from ..core.resources import ServerlessEndpoint, JobOutput

class ServerlessEndpointStub:
    """Adapter class to make RunPod endpoints requests."""

    def __init__(self, server: ServerlessEndpoint):
        self.server = server

    def prepare_payload(self, func, *args, **kwargs) -> dict:
        return func(*args, **kwargs)

    async def execute(self, payload: dict, sync: bool = False) -> Union[JobOutput, Any]:
        """
        Executes a serverless endpoint request with the payload.
        Returns a JobOutput object or raw response.
        """
        if sync:
            return await self.server.run_sync(payload)
        else:
            return await self.server.run(payload)

    def handle_response(self, response: Union[JobOutput, Any]):
        if not isinstance(response, JobOutput):
            return response
        
        if response.output:
            return response.output

        if response.error:
            raise Exception(f"Remote execution failed: {response.error}")

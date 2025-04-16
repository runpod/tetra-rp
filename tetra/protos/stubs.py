import base64
import cloudpickle
import traceback
from ..core.resources import ServerlessResource
from .remote_execution import (
    FunctionRequest,
    FunctionResponse,
    RemoteExecutorStub,
)


class TetraServerlessStub(RemoteExecutorStub):
    """Adapter class to make RunPod endpoints look like gRPC stubs."""

    def __init__(self, server: ServerlessResource):
        self.server = server

    async def ExecuteFunction(self, request: FunctionRequest) -> FunctionResponse:
        """
        Execute function on RunPod serverless endpoint using the RunPod SDK.
        Waits for the job to complete using the SDK's built-in timeout mechanism.
        """
        try:
            # Convert the gRPC request to RunPod format
            payload = request.model_dump(exclude_none=True)

            output = await self.server.execute(payload)

            # Process the output
            if isinstance(output, dict) and "success" in output:
                return FunctionResponse(**output)

            else:
                # Direct output from RunPod
                serialized_result = base64.b64encode(cloudpickle.dumps(output)).decode(
                    "utf-8"
                )
                return FunctionResponse(success=True, result=serialized_result)

        except Exception as e:
            error_traceback = traceback.format_exc()
            return FunctionResponse(
                success=False,
                error=f"Tetra request failed: {str(e)}\n{error_traceback}",
            )

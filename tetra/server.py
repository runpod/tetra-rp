import grpc.aio
from tetra import remote_execution_pb2
from tetra import remote_execution_pb2_grpc
import base64
import cloudpickle
import asyncio
import traceback


class RemoteExecutor(remote_execution_pb2_grpc.RemoteExecutorServicer):
    async def ExecuteFunction(self, request, context):
        try:
            namespace = {}
            exec(request.function_code, namespace)
            func = namespace[request.function_name]

            # Deserialize arguments using cloudpickle
            args = [cloudpickle.loads(base64.b64decode(arg)) for arg in request.args]
            kwargs = {
                k: cloudpickle.loads(base64.b64decode(v))
                for k, v in request.kwargs.items()
            }

            result = func(*args, **kwargs)

            # Serialize result using cloudpickle
            serialized_result = base64.b64encode(cloudpickle.dumps(result)).decode(
                "utf-8"
            )

            return remote_execution_pb2.FunctionResponse(
                result=serialized_result, success=True
            )
        except Exception as e:
            traceback_str = traceback.format_exc()
            error_message = f"{str(e)}\n{traceback_str}"
            print(f"Error executing function: {error_message}")
            return remote_execution_pb2.FunctionResponse(
                success=False, error=error_message
            )


async def serve():
    server = grpc.aio.server()
    remote_execution_pb2_grpc.add_RemoteExecutorServicer_to_server(
        RemoteExecutor(), server
    )
    server.add_insecure_port("[::]:50052")
    print(f"Starting the server on 50052...")
    await server.start()
    print(f"Server started on 50052")
    await server.wait_for_termination()


if __name__ == "__main__":
    asyncio.run(serve())

import grpc.aio
import random
import logging
import time
from typing import Union, List, Dict, Optional
from ..utils.singleton import SingletonMixin
from ..resources.resource_manager import ResourceManager
from ..utils.terminal import (
    Spinner, print_tetra, print_success, print_error, print_warning, 
    style_text, print_timestamp, print_step, TetraNotifier
)
from ... import remote_execution_pb2_grpc, remote_execution_pb2


class RemoteExecutionClient(SingletonMixin):
    def __init__(self):
        self.servers = {}
        self.stubs = {}
        self.pools = {}
        self.resource_manager = ResourceManager()

    async def add_server(self, name: str, address: str):
        """Register a new server"""
        self.servers[name] = address
        channel = grpc.aio.insecure_channel(address)
        self.stubs[name] = remote_execution_pb2_grpc.RemoteExecutorStub(channel)

    async def add_runpod_server(self, name: str, endpoint_url: str):
        """Register a RunPod serverless endpoint"""
        # For RunPod, we'll store the endpoint URL in a format that indicates it's a RunPod endpoint
        self.servers[name] = f"runpod:{endpoint_url}"

        # Create a custom stub for RunPod that will handle the different protocol
        self.stubs[name] = RunPodServerlessStub(endpoint_url)

    def create_pool(self, pool_name: str, server_names: List[str]):
        if not all(name in self.servers for name in server_names):
            raise ValueError("All servers must be registered first")
        self.pools[pool_name] = server_names

    def get_stub(
        self,
        server_spec: Union[str, List[str]],
        fallback: Union[None, str, List[str]] = None,
    ):
        if isinstance(server_spec, list):
            return self._get_pool_stub(server_spec)
        elif server_spec in self.pools:
            return self._get_pool_stub(self.pools[server_spec])
        elif server_spec in self.stubs:
            stub = self.stubs[server_spec]
            if fallback:
                return StubWithFallback(stub, self, fallback)
            return stub
        else:
            raise ValueError(f"Unknown server or pool: {server_spec}")

    def _get_pool_stub(self, server_names: List[str]):
        if not server_names:
            raise ValueError("Server pool is empty")
        server_name = random.choice(server_names)
        return self.stubs[server_name]

    # Get resources in the pool
    def get_pool(self, pool_name: str):
        return self.pools[pool_name]

    def get_server(self, server_name: str):
        return self.servers[server_name]


class RunPodServerlessStub:
    """Adapter class to make RunPod endpoints look like gRPC stubs."""

    def __init__(self, endpoint_url):
        import runpod
        import os

        # Configure RunPod API key
        api_key = os.environ.get("RUNPOD_API_KEY")
        if not api_key:
            raise ValueError("RUNPOD_API_KEY environment variable is not set")
        runpod.api_key = api_key

        # Get runpod logger
        self.runpod_logger = logging.getLogger("runpod")
        self.original_runpod_log_level = self.runpod_logger.level

        self.endpoint_url = endpoint_url
        self.endpoint_id = endpoint_url.strip("/").split("/")[-1]

        # Initialize the RunPod endpoint
        self.endpoint = runpod.Endpoint(self.endpoint_id)
        
        # Job state tracking
        self.active_jobs = {}

    def _silence_runpod_logs(self):
        self.original_runpod_log_level = self.runpod_logger.level
        self.runpod_logger.setLevel(logging.WARNING) # Silence INFO logs

    def _restore_runpod_logs(self):
        self.runpod_logger.setLevel(self.original_runpod_log_level)

    async def ExecuteFunction(self, request):
        """
        Execute function on RunPod serverless endpoint using the RunPod SDK.
        Waits for the job to complete using the SDK's built-in timeout mechanism.
        """
        import base64
        import cloudpickle
        import asyncio

        # Convert the gRPC request to RunPod format
        payload = {
            "function_name": request.function_name,
            "function_code": request.function_code,
            "args": [arg for arg in request.args],  # Convert to regular list
            "kwargs": {
                k: v for k, v in request.kwargs.items()
            },  # Convert to regular dict
        }

        # Add dependencies if specified
        if hasattr(request, "dependencies") and request.dependencies:
            payload["dependencies"] = [dep for dep in request.dependencies]

        # Use spinner and silence runpod logs during network operations
        run_request = None
        status = None
        output = None
        
        # Track timing for job execution
        job_start_time = time.time()

        try:
            loop = asyncio.get_event_loop()
            with Spinner(
                f"Submitting '{request.function_name}' to RunPod compute service...", 
                spinner_type="dots", 
                color="bright_yellow",
                icon="rocket"
            ):
                self._silence_runpod_logs()
                run_request = await loop.run_in_executor(
                    None, lambda: self.endpoint.run({"input": payload})
                )
                self._restore_runpod_logs()
            
            # Try to extract job ID if available
            job_id = getattr(run_request, "id", None)
            job_id_str = f" (ID: {job_id})" if job_id else ""
            
            print_timestamp(
                f"{style_text('✦', 'bright_cyan')} Job submitted to RunPod compute{job_id_str}",
                color="bright_white"
            )

            # Show execution spinner with time tracking
            spinner = Spinner(
                f"Running {style_text(request.function_name, 'bright_magenta', 'bold')} on cloud compute...", 
                spinner_type="moon", 
                color="bright_cyan",
                icon="compute"
            )
            
            # Continuously update the spinner message with elapsed time
            with spinner:
                self._silence_runpod_logs()
                # Initial status check
                status = await loop.run_in_executor(None, lambda: run_request.status())
                
                # Wait for completion only if not already completed
                if status != "COMPLETED":
                    # Get intermediate status updates every 2 seconds
                    remaining_time = 300  # 5 minute timeout
                    interval = 2
                    
                    while status != "COMPLETED" and remaining_time > 0:
                        # Update spinner message with elapsed time
                        elapsed = time.time() - job_start_time
                        spinner.update_message(
                            f"Running {style_text(request.function_name, 'bright_magenta', 'bold')} " +
                            f"on cloud compute... [{style_text(f'{elapsed:.1f}s', 'bright_yellow')}]"
                        )
                        
                        # Wait for a bit before checking again
                        await asyncio.sleep(interval)
                        remaining_time -= interval
                        
                        # Check status
                        status = await loop.run_in_executor(None, lambda: run_request.status())
                        
                        if status == "FAILED":
                            # If status is FAILED, break early
                            break
                    
                    # Get the output once we're done or timed out
                    if status == "COMPLETED":
                        output = await loop.run_in_executor(None, lambda: run_request.output())
                    else:
                        # If not completed, try with timeout
                        output = await loop.run_in_executor(
                            None,
                            lambda: run_request.output(timeout=remaining_time)
                        )
                else:
                    # Already completed, just get the output
                    output = await loop.run_in_executor(None, lambda: run_request.output())
                
                self._restore_runpod_logs()
            
            # Calculate total execution time
            execution_time = time.time() - job_start_time
            execution_time_formatted = f"{execution_time:.2f}"
            
            # Show completion message
            if status == "COMPLETED":
                print_timestamp(
                    f"{style_text('✓', 'bright_green')} Remote execution completed in {style_text(execution_time_formatted + 's', 'bright_yellow')}",
                    color="bright_green"
                )
            else:
                # If timeout but still got output
                print_timestamp(
                    f"{style_text('⚠', 'bright_yellow')} Remote execution status: {style_text(status, 'bright_yellow')} " +
                    f"after {style_text(execution_time_formatted + 's', 'bright_yellow')}",
                    color="bright_yellow"
                )

            # Process the output
            if isinstance(output, dict) and "success" in output:
                if output["success"]:
                    return remote_execution_pb2.FunctionResponse(
                        success=True, result=output.get("result", "")
                    )
                else:
                    return remote_execution_pb2.FunctionResponse(
                        success=False, error=output.get("error", "Unknown error")
                    )
            else:
                # Direct output from RunPod assumed successful
                serialized_result = base64.b64encode(cloudpickle.dumps(output)).decode(
                    "utf-8"
                )
                return remote_execution_pb2.FunctionResponse(
                    success=True, result=serialized_result
                )

        except Exception as e:
            self._restore_runpod_logs() # Ensure logs are restored on error
            import traceback
            error_traceback = traceback.format_exc()
            print_error(f"Exception during RunPod execution: {str(e)}\n{error_traceback}")
            return remote_execution_pb2.FunctionResponse(
                success=False, error=f"RunPod request failed: {str(e)}"
            )


class StubWithFallback:
    def __init__(self, primary_stub, client, fallback_spec):
        self.primary_stub = primary_stub
        self.client = client
        self.fallback_spec = fallback_spec

    async def ExecuteFunction(self, request):
        try:
            return await self.primary_stub.ExecuteFunction(request)
        except Exception as e:
            print_warning(f"Primary server failed: {e}, trying fallback...")
            fallback_stub = self.client.get_stub(self.fallback_spec)
            return await fallback_stub.ExecuteFunction(request)


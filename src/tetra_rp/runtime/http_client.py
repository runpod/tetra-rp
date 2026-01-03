"""HTTP client for cross-endpoint function execution."""

import asyncio
import base64
import logging
import os
from typing import Any, Dict, Optional

try:
    import cloudpickle
    import httpx
except ImportError:
    cloudpickle = None
    httpx = None

logger = logging.getLogger(__name__)


class CrossEndpointClient:
    """HTTP client for executing functions on remote endpoints.

    Makes HTTP calls to remote RunPod endpoints using the same RunPod API
    format as local execution, handling serialization and async job polling.
    """

    def __init__(
        self,
        timeout: int = 300,
        poll_interval: int = 1,
        max_polls: int = 300,
        api_key: Optional[str] = None,
    ):
        """Initialize HTTP client for cross-endpoint calls.

        Args:
            timeout: Maximum execution time in seconds (default: 300).
            poll_interval: Job polling interval in seconds (default: 1).
            max_polls: Maximum number of polls before timeout (default: 300).
            api_key: RunPod API key for authentication. Defaults to
                RUNPOD_API_KEY environment variable.
        """
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.max_polls = max_polls
        self.api_key = api_key or os.getenv("RUNPOD_API_KEY")
        self._client: Optional[httpx.AsyncClient] = None

    async def execute(
        self,
        endpoint_url: str,
        payload: Dict[str, Any],
        sync: bool = False,
    ) -> Dict[str, Any]:
        """Execute function on remote endpoint.

        Args:
            endpoint_url: Base URL of the remote endpoint.
            payload: RunPod-format job input with 'input' key containing
                function_name, execution_type, args, kwargs.
            sync: If True, use /runsync endpoint for sync execution.

        Returns:
            Response dict with 'success' bool and 'result'/'error' keys.

        Raises:
            Exception: If execution fails or times out.
        """
        if httpx is None:
            raise ImportError(
                "httpx required for CrossEndpointClient. "
                "Install with: pip install httpx"
            )
        if cloudpickle is None:
            raise ImportError(
                "cloudpickle required for CrossEndpointClient. "
                "Install with: pip install cloudpickle"
            )

        client = await self._get_client()

        # Determine endpoint
        if sync:
            endpoint = f"{endpoint_url}/runsync"
        else:
            endpoint = f"{endpoint_url}/run"

        # Build headers
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            # Submit job
            logger.debug(
                f"Submitting job to {endpoint} for function "
                f"{payload['input'].get('function_name')}"
            )
            response = await client.post(endpoint, json=payload, headers=headers)

            if response.status_code >= 400:
                error_text = response.text[:500]
                raise Exception(
                    f"Remote execution failed: {response.status_code} - {error_text}"
                )

            response_data = response.json()

            # Handle sync vs async response
            if sync:
                # Sync endpoint returns result immediately
                return self._deserialize_response(response_data)
            else:
                # Async endpoint returns job_id for polling
                job_id = response_data.get("id")
                if not job_id:
                    raise Exception(f"No job ID in async response: {response_data}")

                logger.debug(f"Job submitted with ID: {job_id}")

                # Poll for completion
                result = await self._poll_job(endpoint_url, job_id)
                return self._deserialize_response(result)

        except asyncio.TimeoutError:
            raise Exception(f"Remote execution timed out after {self.timeout} seconds")

    async def _poll_job(self, endpoint_url: str, job_id: str) -> Dict[str, Any]:
        """Poll RunPod job until completion.

        Args:
            endpoint_url: Base URL of the endpoint.
            job_id: ID of the job to poll.

        Returns:
            Job output data.

        Raises:
            Exception: If polling times out or job fails.
        """
        client = await self._get_client()
        status_endpoint = f"{endpoint_url}/status/{job_id}"

        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        for poll_count in range(self.max_polls):
            try:
                response = await client.get(status_endpoint, headers=headers)

                if response.status_code >= 400:
                    raise Exception(f"Job status check failed: {response.status_code}")

                job_data = response.json()
                status = job_data.get("status")

                logger.debug(f"Job {job_id} status: {status}")

                # Check completion
                if status in ["COMPLETED", "FAILED"]:
                    return job_data

                # Not done, wait before next poll
                if poll_count < self.max_polls - 1:
                    await asyncio.sleep(self.poll_interval)

            except asyncio.TimeoutError:
                if poll_count < self.max_polls - 1:
                    await asyncio.sleep(self.poll_interval)
                else:
                    raise

        raise Exception(
            f"Job {job_id} did not complete within "
            f"{self.max_polls * self.poll_interval} seconds"
        )

    def _deserialize_response(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """Deserialize function result from response.

        Args:
            response_data: Response data from endpoint.

        Returns:
            Dictionary with 'success' bool and 'result'/'error' keys.
        """
        # Handle both direct response and nested output format
        output = response_data.get("output", response_data)

        if isinstance(output, dict):
            # Extract success status
            success = output.get("success", False)

            if not success:
                error = output.get("error", "Unknown error")
                return {
                    "success": False,
                    "error": error,
                }

            # Deserialize result if present
            result_b64 = output.get("result")
            if result_b64:
                try:
                    result = cloudpickle.loads(base64.b64decode(result_b64))
                    return {
                        "success": True,
                        "result": result,
                    }
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"Failed to deserialize result: {e}",
                    }

            # Success with no result
            return {
                "success": True,
                "result": None,
            }

        return {
            "success": False,
            "error": f"Unexpected response format: {type(output)}",
        }

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with proper configuration."""
        if self._client is None or self._client.is_closed:
            timeout = httpx.Timeout(self.timeout)
            self._client = httpx.AsyncClient(timeout=timeout)

        return self._client

    async def close(self) -> None:
        """Close HTTP session."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

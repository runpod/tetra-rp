"""
Direct GraphQL communication with Runpod API.
Bypasses the outdated runpod-python SDK limitations.
"""

import json
import logging
import os
from typing import Any, Dict, Optional

import aiohttp

log = logging.getLogger(__name__)

RUNPOD_API_BASE_URL = os.environ.get("RUNPOD_API_BASE_URL", "https://api.runpod.io")
RUNPOD_REST_API_URL = os.environ.get("RUNPOD_REST_API_URL", "https://rest.runpod.io/v1")


class RunpodGraphQLClient:
    """
    Runpod GraphQL client for Runpod API.
    Communicates directly with Runpod's GraphQL endpoint without SDK limitations.
    """

    GRAPHQL_URL = f"{RUNPOD_API_BASE_URL}/graphql"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("RUNPOD_API_KEY")
        if not self.api_key:
            raise ValueError("Runpod API key is required")

        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create an aiohttp session."""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=300)  # 5 minute timeout
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self.session

    async def _execute_graphql(
        self, query: str, variables: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute a GraphQL query/mutation."""
        session = await self._get_session()

        payload = {"query": query, "variables": variables or {}}

        log.debug(f"GraphQL Query: {query}")
        log.debug(f"GraphQL Variables: {json.dumps(variables, indent=2)}")

        try:
            async with session.post(self.GRAPHQL_URL, json=payload) as response:
                response_data = await response.json()

                log.debug(f"GraphQL Response Status: {response.status}")
                log.debug(f"GraphQL Response: {json.dumps(response_data, indent=2)}")

                if response.status >= 400:
                    raise Exception(
                        f"GraphQL request failed: {response.status} - {response_data}"
                    )

                if "errors" in response_data:
                    errors = response_data["errors"]
                    error_msg = "; ".join([e.get("message", str(e)) for e in errors])
                    raise Exception(f"GraphQL errors: {error_msg}")

                return response_data.get("data", {})

        except aiohttp.ClientError as e:
            log.error(f"HTTP client error: {e}")
            raise Exception(f"HTTP request failed: {e}")

    async def create_endpoint(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a serverless endpoint using direct GraphQL mutation.
        Supports both GPU and CPU endpoints with full field support.
        """
        # GraphQL mutation for saveEndpoint (based on actual schema)
        mutation = """
        mutation saveEndpoint($input: EndpointInput!) {
            saveEndpoint(input: $input) {
                aiKey
                gpuIds
                id
                idleTimeout
                locations
                name
                networkVolumeId
                scalerType
                scalerValue
                templateId
                type
                userId
                version
                workersMax
                workersMin
                workersStandby
                workersPFBTarget
                gpuCount
                allowedCudaVersions
                executionTimeoutMs
                instanceIds
                activeBuildid
                idePodId
            }
        }
        """

        variables = {"input": input_data}

        log.debug(
            f"Creating endpoint with GraphQL: {input_data.get('name', 'unnamed')}"
        )

        result = await self._execute_graphql(mutation, variables)

        if "saveEndpoint" not in result:
            raise Exception("Unexpected GraphQL response structure")

        endpoint_data = result["saveEndpoint"]
        log.info(
            f"Created endpoint: {endpoint_data.get('id', 'unknown')} - {endpoint_data.get('name', 'unnamed')}"
        )

        return endpoint_data

    async def get_cpu_types(self) -> Dict[str, Any]:
        """Get available CPU types."""
        query = """
        query getCpuTypes {
            cpuTypes {
                id
                displayName
                manufacturer
                cores
                threadsPerCore
                groupId
            }
        }
        """

        result = await self._execute_graphql(query)
        return result.get("cpuTypes", [])

    async def get_gpu_types(
        self, gpu_filter: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get available GPU types."""
        query = """
        query getGpuTypes($input: GpuTypeFilter) {
            gpuTypes(input: $input) {
                id
                displayName
                manufacturer
                memoryInGb
                cudaCores
                secureCloud
                communityCloud
                securePrice
                communityPrice
                communitySpotPrice
                secureSpotPrice
                maxGpuCount
                maxGpuCountCommunityCloud
                maxGpuCountSecureCloud
                minPodGpuCount
                nodeGroupGpuSizes
                throughput
            }
        }
        """

        variables = {"input": gpu_filter} if gpu_filter else {}
        result = await self._execute_graphql(query, variables)
        return result.get("gpuTypes", [])

    async def get_endpoint(self, endpoint_id: str) -> Dict[str, Any]:
        """Get endpoint details."""
        # Note: The schema doesn't show a specific endpoint query
        # This would need to be implemented if such query exists
        raise NotImplementedError("Get endpoint query not available in current schema")

    async def delete_endpoint(self, endpoint_id: str) -> Dict[str, Any]:
        """Delete a serverless endpoint."""
        mutation = """
        mutation deleteEndpoint($id: String!) {
            deleteEndpoint(id: $id)
        }
        """

        variables = {"id": endpoint_id}
        log.info(f"Deleting endpoint: {endpoint_id}")

        result = await self._execute_graphql(mutation, variables)
        return {"success": result.get("deleteEndpoint") is not None}

    async def close(self):
        """Close the HTTP session."""
        if self.session and not self.session.closed:
            await self.session.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


class RunpodRestClient:
    """
    Runpod REST client for Runpod API.
    Provides methods to interact with Runpod's REST endpoints.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("RUNPOD_API_KEY")
        if not self.api_key:
            raise ValueError("Runpod API key is required")

        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create an aiohttp session."""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=300)  # 5 minute timeout
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self.session

    async def _execute_rest(
        self, method: str, url: str, data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute a REST API request."""
        session = await self._get_session()

        log.debug(f"REST Request: {method} {url}")
        log.debug(f"REST Data: {json.dumps(data, indent=2) if data else 'None'}")

        try:
            async with session.request(method, url, json=data) as response:
                response_data = await response.json()

                log.debug(f"REST Response Status: {response.status}")
                log.debug(f"REST Response: {json.dumps(response_data, indent=2)}")

                if response.status >= 400:
                    raise Exception(
                        f"REST request failed: {response.status} - {response_data}"
                    )

                return response_data

        except aiohttp.ClientError as e:
            log.error(f"HTTP client error: {e}")
            raise Exception(f"HTTP request failed: {e}")

    async def create_network_volume(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create a network volume in Runpod."""
        log.debug(f"Creating network volume: {payload.get('name', 'unnamed')}")

        result = await self._execute_rest(
            "POST", f"{RUNPOD_REST_API_URL}/networkvolumes", payload
        )

        log.info(
            f"Created network volume: {result.get('id', 'unknown')} - {result.get('name', 'unnamed')}"
        )

        return result

    async def close(self):
        """Close the HTTP session."""
        if self.session and not self.session.closed:
            await self.session.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

# Cross-Endpoint Routing for Serverless Functions

## Overview

Cross-endpoint routing enables serverless functions to seamlessly call functions deployed on different endpoints. Functions can execute locally or remotely based on service discovery configuration, allowing developers to build distributed applications without manual routing logic.

## Problem Statement

Previously, serverless functions were isolated to their deployment endpoint. Building distributed applications required:
- Manual HTTP calls to other endpoints with serialization boilerplate
- No unified function invocation pattern across endpoints
- Difficulty discovering which functions exist on which endpoints
- Complex error handling for remote failures
- No automatic argument serialization/deserialization

Cross-endpoint routing solves these problems by providing transparent function routing with manifest-based service discovery.

## User Guide

### Quick Start

Cross-endpoint routing works through a manifest that maps functions to resource configurations. Functions are routed automatically based on this manifest.

#### 1. Create a Manifest

Create a `flash_manifest.json` in your project root:

```json
{
  "version": "1.0",
  "project_name": "my-project",
  "function_registry": {
    "process_image": "image-processor",
    "generate_report": "report-generator"
  },
  "resources": {
    "image-processor": {
      "resource_type": "ServerlessEndpoint",
      "handler_file": "handlers/image.py",
      "functions": [
        {"name": "process_image", "module": "processors.image", "is_async": true}
      ]
    },
    "report-generator": {
      "resource_type": "ServerlessEndpoint",
      "handler_file": "handlers/report.py",
      "functions": [
        {"name": "generate_report", "module": "processors.report", "is_async": true}
      ]
    }
  }
}
```

The manifest structure:
- **`function_registry`**: Maps function names to resource configuration names
- **`resources`**: Defines resource configurations with their handler files and function details
- **Functions not in `function_registry`** execute locally on the current endpoint

#### 2. Set Environment Variables

Configure the mothership manifest URL (required for remote routing):

```bash
# Required for cross-endpoint routing to work
export FLASH_MOTHERSHIP_ID=mothership-endpoint-id

# For child endpoints: Identifies which resource config this endpoint represents
export FLASH_RESOURCE_NAME=gpu_config

# Fallback: Used if FLASH_RESOURCE_NAME not set (for mothership identification)
export RUNPOD_ENDPOINT_ID=gpu-endpoint-123
```

Note: Without `FLASH_MOTHERSHIP_ID`, all functions execute locally. The system gracefully falls back to local execution.

#### 3. Define Functions

Define functions normally. The routing system decides execution location:

```python
from tetra_rp import stub

@stub.function()
async def process_image(image_path: str) -> dict:
    """Process an image - may execute locally or remotely."""
    # This function might route to 'image-processor' endpoint
    # based on manifest configuration
    return {"processed": True}

@stub.function()
async def local_only_function(data: str) -> str:
    """Always executes locally (not in manifest)."""
    return f"Processed: {data}"

@stub.function()
async def generate_report(data: list) -> bytes:
    """May route to 'report-generator' endpoint."""
    return b"report data"
```

#### 4. Call Functions Normally

The routing system handles execution location transparently:

```python
# Local execution (not in manifest)
result = await local_only_function("hello")

# Remote or local execution (based on manifest)
result = await process_image("path/to/image.jpg")
```

### Configuration

#### Manifest File

The manifest file (`flash_manifest.json`) defines function routing and resource configurations:

```json
{
  "version": "1.0",
  "project_name": "my-project",
  "function_registry": {
    "function_name": "resource_config_name",
    "another_function": "another_resource"
  },
  "resources": {
    "resource_config_name": {
      "resource_type": "ServerlessEndpoint",
      "handler_file": "handlers/module.py",
      "functions": [
        {"name": "function_name", "module": "path.to.module", "is_async": true}
      ]
    }
  }
}
```

**Key Points**:
- **`function_registry`**: Maps function names to resource configuration names
- **`resources`**: Defines deployment configuration for each resource
- **Functions not listed** in `function_registry` execute locally
- Missing manifest: logs warning, all functions execute locally

**Manifest Location** (in order of precedence):
1. Path specified in `FLASH_MANIFEST_PATH` env var
2. `flash_manifest.json` in project root
3. Auto-detected in package directory

#### Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `FLASH_MOTHERSHIP_ID` | Yes* | Mothership endpoint ID for manifest service |
| `FLASH_RESOURCE_NAME` | No | Resource config name for child endpoints (identifies which resource this endpoint represents) |
| `RUNPOD_ENDPOINT_ID` | No | Fallback endpoint ID (used if FLASH_RESOURCE_NAME not set) |
| `FLASH_MANIFEST_PATH` | No | Explicit path to manifest file |

*Required for remote routing; without it, all functions execute locally

### Usage Patterns

#### Pattern 1: Microservice Architecture

Split functionality across endpoints using manifest:

**Manifest (flash_manifest.json)**:
```json
{
  "version": "1.0",
  "function_registry": {
    "resize_image": "image-processor",
    "generate_metrics": "report-generator",
    "workflow": "orchestrator"
  },
  "resources": {
    "image-processor": {
      "resource_type": "ServerlessEndpoint",
      "functions": [
        {"name": "resize_image", "module": "image_module", "is_async": true}
      ]
    },
    "report-generator": {
      "resource_type": "ServerlessEndpoint",
      "functions": [
        {"name": "generate_metrics", "module": "metrics_module", "is_async": true}
      ]
    },
    "orchestrator": {
      "resource_type": "ServerlessEndpoint",
      "functions": [
        {"name": "workflow", "module": "orchestration", "is_async": true}
      ]
    }
  }
}
```

**Functions**:
```python
@stub.function()
async def resize_image(path: str, size: int) -> str:
    return process_image(path, size)

@stub.function()
async def generate_metrics(data: list) -> dict:
    return create_metrics(data)

@stub.function()
async def workflow():
    # Transparently calls across endpoints
    image = await resize_image("input.jpg", 512)
    metrics = await generate_metrics([1, 2, 3])
    return {"image": image, "metrics": metrics}
```

#### Pattern 2: Mixed Local and Remote

Configure some functions for remote execution, others local:

**Manifest**:
```json
{
  "version": "1.0",
  "function_registry": {
    "heavy_computation": "gpu-cluster"
  },
  "resources": {
    "gpu-cluster": {
      "resource_type": "ServerlessEndpoint",
      "functions": [
        {"name": "heavy_computation", "module": "gpu_module", "is_async": true}
      ]
    }
  }
}
```

**Functions**:
```python
@stub.function()
async def heavy_computation(data: bytes) -> bytes:
    # Routes to GPU cluster (in function_registry)
    return gpu_process(data)

@stub.function()
async def light_computation(value: int) -> int:
    # Always local - not in function_registry
    return value * 2
```

#### Pattern 3: Fallback to Local

Functions gracefully fall back to local execution if routing fails:

```python
@stub.function()
async def critical_service(request: dict) -> dict:
    # Routes to critical-endpoint if:
    # - In function_registry
    # - Manifest available
    # Otherwise executes locally
    return handle_critical(request)

@stub.function()
async def helper_function(x: int) -> int:
    # Always local - not in manifest
    return x + 1
```

### Error Handling

#### Common Issues

**Manifest Service Unavailable**

If `FLASH_MOTHERSHIP_ID` is not set or unreachable:
```
WARNING: FLASH_MOTHERSHIP_ID not set, manifest service unavailable
```

Functions default to local execution. Set the environment variable to enable routing.

**Manifest Not Found**

If manifest file cannot be found:
```
WARNING: flash_manifest.json not found. Cross-endpoint routing disabled.
```

The system logs a warning but continues—all functions execute locally. Create `flash_manifest.json` in your project root or set `FLASH_MANIFEST_PATH` to enable routing.

**Serialization Error**

If function arguments cannot be serialized:
```
SerializationError: Failed to serialize arguments: [error details]
```

Ensure arguments are picklable (cloudpickle-compatible). Avoid lambdas and local functions.

**Remote Execution Failed**

If remote endpoint fails:
```
RemoteExecutionError: Remote function execution failed: [error details]
```

Check remote endpoint logs and ensure it's deployed and healthy.

### Serialization

Arguments are serialized using cloudpickle and transmitted as base64-encoded HTTP payloads:

```python
# Simple types - always work
await process_image("path.jpg")           # str
await generate_report([1, 2, 3])          # list
await compute(data=np.array([1, 2, 3]))   # numpy array

# Complex types - work if picklable
class DataClass:
    def __init__(self, value):
        self.value = value

await process_data(DataClass(42))  # Custom class

# Won't work
async def with_lambda():
    f = lambda x: x + 1  # Can't serialize lambdas
    await remote_function(f)  # Will fail

async def with_local_func():
    def local_helper():
        return 42
    await remote_function(local_helper)  # Will fail
```

## Contributor Guide

### Architecture Overview

```mermaid
graph TD
    A["Function Call"] -->|"intercepts stub layer"| B["ProductionWrapper"]

    B -->|"load service configuration"| C["ServiceRegistry"]
    C -->|"if not cached"| D["ManifestClient"]
    D -->|"query mothership API"| E["Manifest<br/>Endpoint URLs"]
    E -->|"cache result<br/>TTL 300s"| C

    C -->|"lookup in manifest<br/>flash_manifest.json"| F{"Routing<br/>Decision"}

    F -->|"Local<br/>resource=None"| G["Execute Locally<br/>original stub"]
    F -->|"Not in Manifest"| G
    F -->|"Remote<br/>resource found"| H["Remote Execution"]

    H --> I["Serialize Arguments<br/>cloudpickle → base64"]
    I --> J["HTTP POST<br/>to Remote Endpoint"]
    J --> K["Remote Function<br/>Executes"]
    K --> L["Return Response<br/>base64 → cloudpickle"]
    L --> M["Deserialized Result"]

    N["Error Handling:<br/>- RemoteExecutionError<br/>- SerializationError<br/>- ManifestServiceUnavailableError"] -.-> H
    N -.-> I
    N -.-> J

    G --> O["Result Returned<br/>to Caller"]
    M --> O

    style A fill:#1976d2,stroke:#0d47a1,stroke-width:3px,color:#fff
    style B fill:#0d7f1f,stroke:#0d4f1f,stroke-width:3px,color:#fff
    style C fill:#0d7f1f,stroke:#0d4f1f,stroke-width:3px,color:#fff
    style D fill:#0d7f1f,stroke:#0d4f1f,stroke-width:3px,color:#fff
    style F fill:#d32f2f,stroke:#b71c1c,stroke-width:3px,color:#fff
    style G fill:#1976d2,stroke:#0d47a1,stroke-width:3px,color:#fff
    style H fill:#1976d2,stroke:#0d47a1,stroke-width:3px,color:#fff
    style I fill:#1565c0,stroke:#0d47a1,stroke-width:2px,color:#fff
    style J fill:#1565c0,stroke:#0d47a1,stroke-width:2px,color:#fff
    style K fill:#0d7f1f,stroke:#0d4f1f,stroke-width:3px,color:#fff
    style L fill:#1565c0,stroke:#0d47a1,stroke-width:2px,color:#fff
    style M fill:#1976d2,stroke:#0d47a1,stroke-width:3px,color:#fff
    style N fill:#f57c00,stroke:#e65100,stroke-width:3px,color:#fff
    style O fill:#1976d2,stroke:#0d47a1,stroke-width:3px,color:#fff
    style E fill:#0d7f1f,stroke:#0d4f1f,stroke-width:3px,color:#fff
```

### Core Components

#### 1. ProductionWrapper

**Location**: `src/tetra_rp/runtime/production_wrapper.py`

Intercepts function calls at the stub layer and routes to local or remote execution:

```python
class ProductionWrapper:
    """Wrapper that routes function execution between endpoints."""

    async def wrap_function_execution(
        self,
        original_stub_func: Callable,
        func: Callable,
        dependencies: Optional[list],
        system_dependencies: Optional[list],
        accelerate_downloads: bool,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Route function execution to local or remote endpoint."""
        # 1. Load manifest (if needed)
        await self.service_registry._ensure_manifest_loaded()

        # 2. Look up function in manifest
        resource = self.service_registry.get_resource_for_function(func.__name__)

        # 3. Execute locally if not in manifest or resource is None
        if resource is None:
            return await original_stub_func(
                func,
                dependencies,
                system_dependencies,
                accelerate_downloads,
                *args,
                **kwargs
            )

        # 4. Execute remotely
        return await self._execute_remote(resource, func.__name__, args, kwargs)
```

**Routing Logic**:
- **Local**: Function not in manifest or resource=None
- **Remote**: Function in manifest with resource configuration

**Argument Serialization**:
```python
# Serialize
serialized = base64.b64encode(cloudpickle.dumps(args))

# Deserialize
args = cloudpickle.loads(base64.b64decode(serialized))
```

#### 2. ServiceRegistry

**Location**: `src/tetra_rp/runtime/service_registry.py`

Manages service discovery and manifest loading:

```python
class ServiceRegistry:
    """Service discovery and routing for cross-endpoint function calls."""

    def __init__(
        self,
        manifest_path: Optional[Path] = None,
        manifest_client: Optional[ManifestClient] = None,
        cache_ttl: int = DEFAULT_CACHE_TTL,
    ):
        """Initialize service registry.

        Args:
            manifest_path: Path to flash_manifest.json. Defaults to
                FLASH_MANIFEST_PATH env var or auto-detection.
            manifest_client: Manifest service client for mothership API. If None,
                creates one from FLASH_MOTHERSHIP_ID env var.
            cache_ttl: Manifest cache lifetime in seconds (default: 300).

        Environment Variables (for local vs remote detection):
            FLASH_RESOURCE_NAME: Resource config name for this endpoint (child endpoints).
                Identifies which resource config this endpoint represents in the manifest.
            RUNPOD_ENDPOINT_ID: Endpoint ID (used as fallback for mothership identification).
        """
        self._load_manifest(manifest_path)
        self._manifest_client = manifest_client or ManifestClient()
        self._endpoint_registry = {}  # Cached endpoint URLs
        self._endpoint_registry_lock = asyncio.Lock()
        # Child endpoints use FLASH_RESOURCE_NAME to identify which resource they represent
        # Mothership doesn't have FLASH_RESOURCE_NAME, so falls back to RUNPOD_ENDPOINT_ID
        self._current_endpoint = os.getenv("FLASH_RESOURCE_NAME") or os.getenv(
            "RUNPOD_ENDPOINT_ID"
        )

    def get_resource_for_function(self, func_name: str) -> Optional[ServerlessResource]:
        """Get resource config for function from manifest."""
        # Returns the ServerlessResource if function is mapped in manifest
        # Returns None if function maps to current endpoint
        # Raises ValueError if function not found in manifest
        config = self._manifest.function_registry.get(func_name)
        return self._resolve_resource(config)

    async def _ensure_manifest_loaded(self) -> None:
        """Load manifest from mothership if cache expired or not loaded."""
        async with self._endpoint_registry_lock:
            now = time.time()
            cache_age = now - self._endpoint_registry_loaded_at

            if cache_age > self.cache_ttl:
                self._endpoint_registry = await self._manifest_client.get_manifest()
                self._endpoint_registry_loaded_at = now
```

**Manifest Format**:
```json
{
  "version": "1.0",
  "project_name": "project_name",
  "function_registry": {
    "function_name": "resource_config_name",
    "local_function": null
  },
  "resources": {
    "resource_config_name": {
      "resource_type": "ServerlessEndpoint",
      "handler_file": "handler.py",
      "functions": [...]
    }
  }
}
```

**Key fields**:
- `function_registry`: Maps function names to resource config names (null = local)
- `resources`: Defines resource configurations and their handler details

**Manifest Cache**:
- TTL: 300 seconds (configurable via `DEFAULT_CACHE_TTL`)
- Thread-safe with `asyncio.Lock()`
- Graceful fallback if manifest service unavailable

#### 3. ManifestClient

**Location**: `src/tetra_rp/runtime/manifest_client.py`

HTTP client for mothership manifest service:

```python
class ManifestClient:
    """HTTP client for querying mothership manifest.

    The manifest maps resource_config names to their endpoint URLs.
    Example: {"gpu_config": "https://api.runpod.io/v2/abc123"}
    """

    async def get_manifest(self) -> Dict[str, str]:
        """Fetch endpoint manifest from mothership.

        Returns:
            Dictionary mapping resource_config_name → endpoint_url.
            Example: {"gpu_config": "https://api.runpod.io/v2/abc123"}

        Raises:
            ManifestServiceUnavailableError: If manifest service unavailable after retries.
        """
        # Queries {mothership_url}/manifest endpoint with retry logic
```

**Configuration**:
- Mothership ID from `FLASH_MOTHERSHIP_ID` env var (constructs URL as https://{id}.api.runpod.ai)
- HTTP timeout: 10 seconds (via `DEFAULT_REQUEST_TIMEOUT`)
- Retry logic: Exponential backoff with `DEFAULT_MAX_RETRIES` attempts (default: 3)
- Uses `httpx` library for async HTTP requests
- Raises `ImportError` if httpx not installed (with helpful message)

#### 4. StateManagerClient

**Location**: `src/tetra_rp/runtime/state_manager_client.py`

HTTP client for State Manager API (used by mothership auto-provisioning):

```python
class StateManagerClient:
    """HTTP client for State Manager API.

    The State Manager persists manifest state and provides reconciliation
    for detecting new, changed, and removed resources.
    """

    async def get_persisted_manifest(
        self, mothership_id: str
    ) -> Optional[Dict[str, Any]]:
        """Fetch persisted manifest from State Manager.

        Returns:
            Manifest dict or None if not found (first boot).

        Raises:
            ManifestServiceUnavailableError: If State Manager unavailable.
        """
        # Queries {base_url}/api/v1/flash/manifests/{mothership_id}

    async def update_resource_state(
        self,
        mothership_id: str,
        resource_name: str,
        resource_data: Dict[str, Any],
    ) -> None:
        """Update resource entry in State Manager after deployment."""
        # Queries {base_url}/api/v1/flash/manifests/{mothership_id}/resources/{resource_name}
```

**Configuration**:
- Base URL: `https://api.runpod.io` (default, configurable)
- Authentication: Bearer token using RUNPOD_API_KEY env var
- HTTP timeout: 10 seconds (via `DEFAULT_REQUEST_TIMEOUT`)
- Retry logic: Exponential backoff with `DEFAULT_MAX_RETRIES` attempts (default: 3)
- Uses `httpx` library for async HTTP requests
- Raises `ImportError` if httpx not installed (with helpful message)

#### 5. Exception Hierarchy

**Location**: `src/tetra_rp/runtime/exceptions.py`

Custom exceptions for cross-endpoint routing:

```python
class FlashRuntimeError(Exception):
    """Base exception for runtime errors in cross-endpoint execution."""
    pass

class RemoteExecutionError(FlashRuntimeError):
    """Raised when remote function execution fails."""
    pass

class SerializationError(FlashRuntimeError):
    """Raised when serialization or deserialization of arguments fails."""
    pass

class ManifestError(FlashRuntimeError):
    """Raised when manifest is invalid, missing, or has unexpected structure."""
    pass

class ManifestServiceUnavailableError(FlashRuntimeError):
    """Raised when manifest service is unavailable."""
    pass
```

**Usage**:
```python
try:
    result = await remote_execution()
except RemoteExecutionError as e:
    logger.error(f"Remote execution failed: {e}")
except SerializationError as e:
    logger.error(f"Serialization failed: {e}")
except ManifestError as e:
    logger.error(f"Manifest configuration error: {e}")
except ManifestServiceUnavailableError as e:
    logger.warning(f"Manifest unavailable, using fallback")
```

### Integration Points

#### Stub Layer Integration

ProductionWrapper integrates with the stub execution layer in `src/tetra_rp/stubs/registry.py`:

```python
# Before: Direct stub execution
result = await original_stub_func(func, deps, ...)

# After: Routed execution
production_wrapper = ProductionWrapper(service_registry)
result = await production_wrapper.wrap_function_execution(
    original_stub_func,
    func,
    dependencies,
    system_dependencies,
    accelerate_downloads,
    *args,
    **kwargs
)
```

The wrapper is transparent - function signatures and return types are unchanged.

#### Resource Manager

Functions retrieve remote endpoint info from ResourceManager:

```python
# ServiceRegistry uses ResourceManager to find endpoint URLs
resource_manager = ResourceManager()
endpoint = resource_manager.get_resource_for_function("function_name")
endpoint_url = endpoint.url  # e.g., "https://api.runpod.io/v2/abc123"
```

### Configuration

#### Runtime Config

**Location**: `src/tetra_rp/runtime/config.py`

Centralized configuration constants:

```python
DEFAULT_CACHE_TTL = 300  # seconds
DEFAULT_HTTP_TIMEOUT = 10  # seconds
MAX_RETRY_ATTEMPTS = 3
RETRY_BACKOFF_FACTOR = 2.0
```

Add new configuration by:
1. Defining constant in `config.py`
2. Importing in component that uses it
3. Making configurable via environment variable if appropriate

### Data Flow

#### Local Execution Flow

```mermaid
flowchart TD
    A["Function Call"]
    B["ProductionWrapper.wrap_function_execution()"]
    C["ServiceRegistry.get_resource_for_function()"]
    D["Manifest Lookup<br/>resource = None"]
    E["Local Execution<br/>original_stub_func"]
    F["Result"]

    A --> B
    B --> C
    C --> D
    D --> E
    E --> F

    style A fill:#1976d2,stroke:#0d47a1,stroke-width:3px,color:#fff
    style B fill:#1976d2,stroke:#0d47a1,stroke-width:3px,color:#fff
    style C fill:#1976d2,stroke:#0d47a1,stroke-width:3px,color:#fff
    style D fill:#388e3c,stroke:#1b5e20,stroke-width:3px,color:#fff
    style E fill:#388e3c,stroke:#1b5e20,stroke-width:3px,color:#fff
    style F fill:#1976d2,stroke:#0d47a1,stroke-width:3px,color:#fff
```

#### Remote Execution Flow

```mermaid
flowchart TD
    A["Function Call"]
    B["ProductionWrapper.wrap_function_execution()"]
    C["ServiceRegistry.get_resource_for_function()"]
    D["Manifest Lookup<br/>resource found"]
    E["Ensure Manifest Loaded"]
    F["ManifestClient.get_manifest()"]
    G["Get Remote Endpoint URL"]
    H["Serialize Arguments<br/>cloudpickle → base64"]
    I["HTTP POST to Remote Endpoint"]
    J["Remote Function Execution"]
    K["Deserialize Result<br/>base64 → cloudpickle"]
    L["Result"]

    A --> B
    B --> C
    C --> D
    D --> E
    E --> F
    F --> G
    G --> H
    H --> I
    I --> J
    J --> K
    K --> L

    style A fill:#1976d2,stroke:#0d47a1,stroke-width:3px,color:#fff
    style B fill:#1976d2,stroke:#0d47a1,stroke-width:3px,color:#fff
    style C fill:#1976d2,stroke:#0d47a1,stroke-width:3px,color:#fff
    style D fill:#d32f2f,stroke:#b71c1c,stroke-width:3px,color:#fff
    style E fill:#d32f2f,stroke:#b71c1c,stroke-width:3px,color:#fff
    style F fill:#d32f2f,stroke:#b71c1c,stroke-width:3px,color:#fff
    style G fill:#d32f2f,stroke:#b71c1c,stroke-width:3px,color:#fff
    style H fill:#f57c00,stroke:#e65100,stroke-width:3px,color:#fff
    style I fill:#d32f2f,stroke:#b71c1c,stroke-width:3px,color:#fff
    style J fill:#d32f2f,stroke:#b71c1c,stroke-width:3px,color:#fff
    style K fill:#f57c00,stroke:#e65100,stroke-width:3px,color:#fff
    style L fill:#1976d2,stroke:#0d47a1,stroke-width:3px,color:#fff
```

### Design Decisions

#### 1. Manifest-Based Routing

**Decision**: Use JSON manifest for function-to-resource mapping

**Rationale**:
- Decouples function code from deployment configuration
- Enables environment-specific routing without code changes
- Version control friendly
- Dynamic routing without recompilation

#### 2. Thread-Safe Async Caching

**Decision**: Use `asyncio.Lock()` for manifest cache synchronization

**Rationale**:
- Prevents thundering herd on cache expiry
- Efficient - only one coroutine loads manifest
- Simple to understand and maintain
- Follows async/await patterns

#### 3. Cloudpickle Serialization

**Decision**: Use cloudpickle for argument serialization

**Rationale**:
- Supports complex Python objects
- Handles closures and lambdas (when possible)
- Standard in Python ML/data processing
- Works with numpy arrays, dataframes, etc.

#### 4. Graceful Fallback

**Decision**: Default to local execution if manifest service unavailable

**Rationale**:
- Maintains application resilience
- Doesn't fail if mothership unreachable
- Allows local testing without manifest service
- Gradual degradation vs catastrophic failure

#### 5. Transparent Routing

**Decision**: Routing happens at wrapper level, not in business logic

**Rationale**:
- Function code unchanged
- Testing simplified - can mock ProductionWrapper
- Easy to add/remove routing dynamically
- No performance overhead if not needed

### Extension Points

#### Adding New Serialization Formats

To support formats other than cloudpickle:

1. Create serializer class:
```python
class JsonSerializer:
    @staticmethod
    def serialize(obj: Any) -> str:
        return json.dumps(obj)

    @staticmethod
    def deserialize(data: str) -> Any:
        return json.loads(data)
```

2. Update ProductionWrapper to select serializer based on config
3. Add tests for new format

#### Adding New Manifest Backends

To support directories other than mothership:

1. Create client class with `get_manifest()` method:
```python
class CustomManifestClient:
    async def get_manifest(self) -> Dict[str, str]:
        """Fetch manifest mapping resource_config_name → endpoint_url."""
        # Implementation specific to backend
        return {"resource_name": "https://endpoint.url"}
```

2. Update ServiceRegistry to accept and use client in constructor:
```python
registry = ServiceRegistry(
    manifest_path=Path("manifest.json"),
    manifest_client=CustomManifestClient(...)
)
```

3. Update environment variable handling if needed (CustomManifestClient can read from env vars)

#### Adding Routing Policies

To implement routing logic beyond manifest:

1. Create policy class:
```python
class RoutingPolicy:
    async def should_route(
        self,
        func_name: str,
        resource: ServerlessResource,
        args: tuple,
        kwargs: dict
    ) -> bool:
        """Determine if function should route remotely."""
        pass
```

2. Update ProductionWrapper to use policy
3. Add configuration for policy selection

### Testing Strategy

#### Unit Tests

**ServiceRegistry Tests** (`tests/unit/runtime/test_service_registry.py`):
- Manifest loading
- Resource lookup
- Manifest caching
- TTL expiry
- Lock behavior under concurrency

**ManifestClient Tests** (`tests/unit/runtime/test_manifest_client.py`):
- Successful HTTP requests
- Error handling
- Retry logic
- Timeout handling
- URL validation

**ProductionWrapper Tests** (`tests/unit/runtime/test_production_wrapper.py`):
- Local execution routing
- Remote execution routing
- Argument serialization
- Result deserialization
- Error propagation

#### Integration Tests

**Cross-Endpoint Tests** (`tests/integration/test_cross_endpoint_routing.py`):
- End-to-end local execution
- End-to-end remote execution
- Function call across endpoints
- Error handling in real scenarios
- Manifest caching behavior
- Serialization of complex objects

#### Test Patterns

```python
# Unit test: Mock dependencies
@pytest.mark.asyncio
async def test_local_execution():
    mock_registry = AsyncMock()
    mock_registry.get_resource_for_function.return_value = None

    wrapper = ProductionWrapper(mock_registry)
    result = await wrapper.wrap_function_execution(
        original_stub_func=mock_original,
        func=mock_func,
        ...
    )

    assert result == expected_result

# Integration test: Real components
@pytest.mark.asyncio
async def test_cross_endpoint_execution():
    registry = ServiceRegistry(manifest_path=manifest)
    wrapper = ProductionWrapper(registry)

    # Actual function call
    result = await wrapper.wrap_function_execution(
        original_stub_func=real_stub,
        func=test_function,
        ...
    )

    assert result == expected_result
```

### Debugging

#### Logging

Enable debug logging to trace routing decisions:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# ProductionWrapper logs
# ServiceRegistry logs
# ManifestClient logs
```

#### Common Debug Scenarios

**Function not routing to remote**:
```python
# Check manifest
print(registry._manifest)

# Check cached endpoint URLs
print(registry._endpoint_registry)

# Check resource lookup
resource = registry.get_resource_for_function("function_name")
print(f"Resource: {resource}")
```

**Serialization failures**:
```python
# Test pickling directly
import cloudpickle
try:
    cloudpickle.dumps(args)
except Exception as e:
    print(f"Not serializable: {e}")
```

**Manifest unavailable**:
```python
# Check environment variables
import os
print(f"FLASH_MOTHERSHIP_ID: {os.getenv('FLASH_MOTHERSHIP_ID')}")
print(f"RUNPOD_ENDPOINT_ID: {os.getenv('RUNPOD_ENDPOINT_ID')}")

# Check manifest client directly
client = ManifestClient(mothership_url=...)
endpoints = await client.get_manifest()
```

## Manifest Synchronization with RunPod GraphQL API

### Overview

The Mothership's GET /manifest endpoint pulls configuration from RunPod's GraphQL API,
which serves as the single source of truth for manifest data. This enables centralized
configuration management and ensures all child endpoints receive consistent routing
information.

### Architecture

```mermaid
flowchart TD
    A["Child Endpoint<br/>GET /manifest"]
    B["Mothership"]
    C["ManifestFetcher"]
    D{Cache Valid?}
    E["Serve Cached<br/>Manifest"]
    F["Fetch from RunPod<br/>GraphQL API"]
    G["Update<br/>flash_manifest.json"]
    H["Cache Result<br/>TTL: 300s"]
    I["Serve Manifest"]
    J["Fallback:<br/>Load Local File"]

    A -->|Request| B
    B --> C
    C --> D
    D -->|Yes| E
    D -->|No| F
    E --> I
    F --> G
    G --> H
    H --> I
    F -->|Fails| J
    J --> I

    style A fill:#1976d2,stroke:#0d47a1,stroke-width:3px,color:#fff
    style B fill:#388e3c,stroke:#1b5e20,stroke-width:3px,color:#fff
    style C fill:#388e3c,stroke:#1b5e20,stroke-width:3px,color:#fff
    style D fill:#f57c00,stroke:#e65100,stroke-width:3px,color:#fff
    style E fill:#388e3c,stroke:#1b5e20,stroke-width:3px,color:#fff
    style F fill:#d32f2f,stroke:#b71c1c,stroke-width:3px,color:#fff
    style G fill:#d32f2f,stroke:#b71c1c,stroke-width:3px,color:#fff
    style H fill:#388e3c,stroke:#1b5e20,stroke-width:3px,color:#fff
    style I fill:#1976d2,stroke:#0d47a1,stroke-width:3px,color:#fff
    style J fill:#d32f2f,stroke:#b71c1c,stroke-width:3px,color:#fff
```

### How It Works

1. **Source of Truth**: RunPod GraphQL API holds the authoritative manifest configuration
2. **Caching Proxy**: Mothership fetches from RunPod GQL, caches locally (5 min TTL)
3. **Local Persistence**: Fetched manifest written to `flash_manifest.json`
4. **Graceful Fallback**: If RunPod GQL unavailable, serves local file
5. **Cache Invalidation**: Automatic expiry after TTL, manual invalidation supported

### Implementation Status

**Current (Placeholder)**:
- `ManifestFetcher` class with caching infrastructure
- Uses existing `RunpodGraphQLClient` for API communication
- Falls back to local `flash_manifest.json` (GQL fetch raises `NotImplementedError`)
- Cache TTL: 300 seconds (configurable)

**Future (Full Implementation)**:
- Implement `getManifest` query in `ManifestFetcher._fetch_from_gql()`
- Add `saveManifest` mutation for updating manifest in RunPod
- Real-time cache invalidation via webhooks
- Health checks and retry logic

### Configuration

```bash
# Enable Mothership mode (required for /manifest endpoint)
export FLASH_IS_MOTHERSHIP=true

# Optional: Identify this mothership instance
export RUNPOD_ENDPOINT_ID=mothership-prod-1

# Required for RunPod GraphQL API access
export RUNPOD_API_KEY=your-api-key-here
```

### Cache Behavior

- **Default TTL**: 300 seconds (5 minutes)
- **Cache Key**: Per-mothership instance (no cross-instance cache)
- **Thread-Safe**: Uses `asyncio.Lock` for concurrent request handling
- **Manual Invalidation**: `fetcher.invalidate_cache()` for testing

### Historical Context

A previous `StateManagerClient` (commit b19bf7c) used REST API. Current placeholder
prepares for GQL-based architecture with improved caching and error handling.

## Key Implementation Highlights

### Design Focus

1. **Transparent Routing**: Functions route automatically without code changes
2. **Graceful Degradation**: Defaults to local execution if manifest service unavailable
3. **Type Safety**: Full type hints throughout for IDE support and static analysis
4. **Thread-Safe Async**: Proper `asyncio.Lock()` usage for concurrent operations
5. **Clear Error Hierarchy**: Custom exceptions provide actionable error context

## Conclusion

Cross-endpoint routing provides:

- **Transparency**: Functions route automatically without manual HTTP calls
- **Flexibility**: Manifest-based routing enables environment-specific configurations
- **Resilience**: Graceful fallback to local execution if manifest service unavailable
- **Simplicity**: No changes to function code or signatures
- **Debuggability**: Clear error messages and logging for troubleshooting

The architecture prioritizes clarity and maintainability while enabling distributed serverless applications.

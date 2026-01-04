# Using @remote with Load-Balanced Endpoints

## Introduction

Flash provides two ways to execute remote functions on serverless endpoints: queue-based (QB) and load-balanced (LB) endpoints. This guide covers using the `@remote` decorator with load-balanced endpoints for HTTP-based function execution.

### Queue-Based vs Load-Balanced Endpoints

**Queue-Based Endpoints** (ServerlessEndpoint, LiveServerless)
- Requests queued and processed sequentially
- Automatic retry logic on failure
- Built-in fault tolerance
- Higher latency (queuing + processing)
- Fixed request/response format

**Load-Balanced Endpoints** (LoadBalancerSlsResource, LiveLoadBalancer)
- Requests routed directly to available workers
- Direct HTTP execution, no queue
- No automatic retries
- Lower latency (direct HTTP)
- Custom HTTP routes and methods

### When to Use Each Type

Use **Load-Balanced** when you need:
- Low latency API endpoints
- Custom HTTP routing (GET, POST, PUT, DELETE)
- Direct HTTP response handling
- Handling multiple routes on single endpoint

Use **Queue-Based** when you need:
- Automatic retry logic on failures
- Sequential, fault-tolerant processing
- Tolerance for higher latency
- Simple request/response pattern

## Quick Start

### Basic Example with LiveLoadBalancer

For local development, use `LiveLoadBalancer`:

```python
from tetra_rp import LiveLoadBalancer, remote

# Create load-balanced endpoint
api = LiveLoadBalancer(name="example-api")

# Define HTTP-routed function
@remote(api, method="POST", path="/api/greet")
async def greet_user(name: str):
    return {"message": f"Hello, {name}!"}

# Call the function locally
async def main():
    result = await greet_user("Alice")
    print(result)  # {"message": "Hello, Alice!"}

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

Key points:
- `method` parameter specifies HTTP method (GET, POST, PUT, DELETE, PATCH)
- `path` parameter specifies URL route (must start with `/`)
- Functions execute directly without deployment during development

## HTTP Routing

Load-balanced endpoints require explicit HTTP routing metadata in the `@remote` decorator.

### Parameters

**method** (required for LoadBalancerSlsResource)
- Must be one of: GET, POST, PUT, DELETE, PATCH
- Case-insensitive (POST, post, Post all work)

**path** (required for LoadBalancerSlsResource)
- Must start with `/` (e.g., `/api/process`, `/health`)
- Can include path parameters (e.g., `/api/users/{user_id}`)
- Cannot use reserved paths: `/execute`, `/ping`

### Single Endpoint with Multiple Routes

Multiple functions can share a single LoadBalancerSlsResource with different routes:

```python
from tetra_rp import LiveLoadBalancer, remote

api = LiveLoadBalancer(name="user-service")

@remote(api, method="GET", path="/users")
def list_users():
    return {"users": []}

@remote(api, method="POST", path="/users")
async def create_user(name: str, email: str):
    return {"id": 1, "name": name, "email": email}

@remote(api, method="GET", path="/users/{user_id}")
def get_user(user_id: int):
    return {"id": user_id, "name": "Alice"}

@remote(api, method="DELETE", path="/users/{user_id}")
async def delete_user(user_id: int):
    return {"deleted": True}
```

When deployed:
- Single `user-service` endpoint created
- Four HTTP routes registered automatically
- FastAPI handles routing to correct function

### Reserved Paths

The following paths are reserved by Flash and cannot be used:

- `/execute` - Framework endpoint for @remote stub execution
- `/ping` - Health check endpoint (returns 200 OK)

Attempting to use these paths will raise a validation error at build time.

## Local Development

### Using LiveLoadBalancer

For local development and testing, use `LiveLoadBalancer` instead of `LoadBalancerSlsResource`:

```python
from tetra_rp import LiveLoadBalancer, remote

api = LiveLoadBalancer(name="my-api")

@remote(api, method="POST", path="/api/process")
async def process_data(x: int, y: int):
    return {"result": x + y}

# In tests or scripts, call directly
async def test():
    result = await process_data(5, 3)
    assert result == {"result": 8}
```

**Key differences:**
- `LiveLoadBalancer` locks image to Tetra LB runtime (tetra-rp-lb)
- Functions execute directly without deployment
- Ideal for development and CI/CD testing
- Same `@remote` decorator interface as production

### Testing Patterns

```python
import pytest
from tetra_rp import LiveLoadBalancer, remote

api = LiveLoadBalancer(name="test-api")

@remote(api, method="POST", path="/api/calculate")
async def calculate(operation: str, a: int, b: int):
    if operation == "add":
        return a + b
    elif operation == "multiply":
        return a * b
    else:
        raise ValueError(f"Unknown operation: {operation}")

@pytest.mark.asyncio
async def test_calculate_add():
    result = await calculate("add", 5, 3)
    assert result == 8

@pytest.mark.asyncio
async def test_calculate_multiply():
    result = await calculate("multiply", 5, 3)
    assert result == 15

@pytest.mark.asyncio
async def test_calculate_invalid():
    with pytest.raises(ValueError):
        await calculate("unknown", 5, 3)
```

## Building and Deploying

### Build Process

When you run `flash build`, the system:

1. **Scans** your code for `@remote` decorated functions
2. **Extracts** HTTP routing metadata (method, path)
3. **Generates** FastAPI application with routes
4. **Creates** one handler file per LoadBalancerSlsResource
5. **Validates** routes for conflicts and reserved paths

Example generated handler:

```python
from fastapi import FastAPI
from tetra_rp.runtime.lb_handler import create_lb_handler

# Imported from user code
from api.endpoints import process_data, health_check

# Route registry built automatically
ROUTE_REGISTRY = {
    ("POST", "/api/process"): process_data,
    ("GET", "/api/health"): health_check,
}

# FastAPI app created with routes
app = create_lb_handler(ROUTE_REGISTRY)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### Deployment Workflow

```bash
# 1. Define functions with @remote decorator in your code
# 2. Test locally with LiveLoadBalancer
# 3. Build for production
flash build

# 4. Configure your endpoint (optional)
# Edit flash.toml if needed to set image, GPU, etc.

# 5. Deploy
flash deploy

# 6. Check deployment status
flash status
```

### Verifying Deployment

Once deployed, verify your endpoint:

```bash
# Check endpoint is healthy
curl https://<endpoint-url>/ping
# Expected response: {"status": "healthy"}

# Call your function via HTTP
curl -X POST https://<endpoint-url>/api/process \
  -H "Content-Type: application/json" \
  -d '{"x": 5, "y": 3}'
```

## Complete Working Example

Here's a full example with multiple routes, error handling, and testing:

```python
"""
user_service.py - Example load-balanced API service
"""

from tetra_rp import LoadBalancerSlsResource, remote
from typing import Optional

# For production, use LoadBalancerSlsResource
# For local development, use LiveLoadBalancer
api = LoadBalancerSlsResource(
    name="user-service",
    imageName="runpod/tetra-rp-lb:latest"
)

class UserNotFound(Exception):
    pass

# In-memory database for example
users_db = {
    1: {"id": 1, "name": "Alice", "email": "alice@example.com"},
    2: {"id": 2, "name": "Bob", "email": "bob@example.com"},
}

@remote(api, method="GET", path="/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

@remote(api, method="GET", path="/users")
def list_users():
    """List all users."""
    return {"users": list(users_db.values())}

@remote(api, method="POST", path="/users")
async def create_user(name: str, email: str):
    """Create a new user."""
    user_id = max(users_db.keys() or [0]) + 1
    user = {"id": user_id, "name": name, "email": email}
    users_db[user_id] = user
    return user

@remote(api, method="GET", path="/users/{user_id}")
def get_user(user_id: int):
    """Get a specific user."""
    if user_id not in users_db:
        raise UserNotFound(f"User {user_id} not found")
    return users_db[user_id]

@remote(api, method="PUT", path="/users/{user_id}")
async def update_user(user_id: int, name: Optional[str] = None,
                      email: Optional[str] = None):
    """Update a user."""
    if user_id not in users_db:
        raise UserNotFound(f"User {user_id} not found")

    user = users_db[user_id]
    if name is not None:
        user["name"] = name
    if email is not None:
        user["email"] = email
    return user

@remote(api, method="DELETE", path="/users/{user_id}")
async def delete_user(user_id: int):
    """Delete a user."""
    if user_id not in users_db:
        raise UserNotFound(f"User {user_id} not found")

    del users_db[user_id]
    return {"deleted": True}
```

### Testing the Example

```python
"""
test_user_service.py
"""

import pytest
from tetra_rp import LiveLoadBalancer, remote
from typing import Optional

# Use LiveLoadBalancer for testing
api = LiveLoadBalancer(name="user-service-test")

# Define functions (same as above but use test endpoint)
# ... (function definitions) ...

@pytest.mark.asyncio
async def test_list_users():
    users = list_users()
    assert "users" in users
    assert isinstance(users["users"], list)

@pytest.mark.asyncio
async def test_create_and_get_user():
    # Create a user
    new_user = await create_user("Charlie", "charlie@example.com")
    assert new_user["name"] == "Charlie"
    assert new_user["id"] > 0

    # Get the user
    user = get_user(new_user["id"])
    assert user["name"] == "Charlie"

@pytest.mark.asyncio
async def test_update_user():
    new_user = await create_user("Diana", "diana@example.com")
    updated = await update_user(new_user["id"], name="Diana Updated")
    assert updated["name"] == "Diana Updated"

@pytest.mark.asyncio
async def test_delete_user():
    new_user = await create_user("Eve", "eve@example.com")
    result = await delete_user(new_user["id"])
    assert result["deleted"] is True

    # Should raise error when trying to get deleted user
    with pytest.raises(Exception):  # UserNotFound
        get_user(new_user["id"])
```

## Troubleshooting

### Validation Errors

**"requires both 'method' and 'path'"**
- Problem: Using `@remote(lb_resource)` without method/path
- Solution: Add both parameters: `@remote(lb, method="POST", path="/api/endpoint")`

**"Invalid HTTP method 'PATCH' must be one of: GET, POST, PUT, DELETE, PATCH"**
- Problem: Typo in HTTP method (e.g., `PTACH` instead of `PATCH`)
- Solution: Verify method spelling matches valid HTTP verbs

**"path must start with '/'"**
- Problem: Path doesn't start with forward slash
- Solution: Use absolute paths: `/api/endpoint` not `api/endpoint`

**"Route conflict detected: POST /api/process defined twice"**
- Problem: Two functions with same method and path on same endpoint
- Solution: Change path or method to make each route unique

### Runtime Errors

**"Endpoint URL not available - endpoint may not be deployed"**
- Problem: Using LoadBalancerSlsResource before calling `await resource.deploy()`
- Solution: Deploy the endpoint first (`await resource.deploy()`) which auto-populates endpoint_url, or use LiveLoadBalancer for local testing
- Note: endpoint_url is auto-generated by RunPod after deployment and cannot be manually specified

**"HTTP error from endpoint: 500"**
- Problem: Function raised an error during execution
- Solution: Check function code for exceptions, view endpoint logs

**"Execution timeout on user-service after 30s"**
- Problem: Function took longer than 30 seconds to complete
- Solution: Optimize function, consider increasing timeout in LoadBalancerSlsStub

### Build Errors

**"Cannot import module 'user_service'"**
- Problem: Function module not found during handler generation
- Solution: Ensure module is in Python path, check import statements

**"Function 'process_data' not found in executed code"**
- Problem: Function source extraction failed
- Solution: Ensure function is defined at module level (not inside another function)

## API Reference

### @remote Decorator with LoadBalancerSlsResource

```python
@remote(
    resource_config: LoadBalancerSlsResource | LiveLoadBalancer,
    method: str = None,  # Required: GET, POST, PUT, DELETE, PATCH
    path: str = None,    # Required: /api/route
    dependencies: List[str] = None,  # Python packages to install
    system_dependencies: List[str] = None,  # System packages to install
    accelerate_downloads: bool = True  # Use download acceleration
)
def your_function(...):
    pass
```

### LoadBalancerSlsResource

See `docs/Load_Balancer_Endpoints.md` for detailed architecture and configuration options.

### LiveLoadBalancer

A test/development variant of LoadBalancerSlsResource:
- Locks to Tetra LB image
- Enables direct function calls without deployment
- Same decorator interface as production

## Best Practices

1. **Use LiveLoadBalancer for testing** - No deployment needed for development
2. **Test locally before deploying** - Catch routing/logic errors early
3. **Use descriptive paths** - `/api/users/{user_id}` is clearer than `/api/u`
4. **Group related routes** - Keep similar endpoints on same service
5. **Handle errors gracefully** - Return meaningful error messages to clients
6. **Verify health checks** - Ensure `/ping` endpoint works after deployment
7. **Document your API** - Add docstrings explaining what each route does

## Next Steps

- Review `docs/Load_Balancer_Endpoints.md` for LoadBalancerSlsResource class architecture
- Review `docs/LoadBalancer_Runtime_Architecture.md` for runtime execution and request flows
- Check examples in `flash-examples/` repository for more patterns
- Use `flash build --help` to see build options
- Use `flash run --help` to see local testing options

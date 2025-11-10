"""
Example GPU Worker Router

This worker demonstrates the APIRouter pattern for Flash applications.

Each router is discovered as a handler during build:
- Queue-based: Single POST endpoint (async processing)
- Load-balancer: Multiple endpoints or any GET (synchronous API)

This router will be deployed as a Queue-based endpoint.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from .endpoint import ExampleWorker


# Create APIRouter for this worker
# This router will be discovered as a handler during build
example_worker_router = APIRouter()


class ProcessRequest(BaseModel):
    """Request model for processing endpoint."""
    data: str


class ProcessResponse(BaseModel):
    """Response model for processing endpoint."""
    status: str
    input: dict
    output: str


# Define routes for this worker
# Single POST endpoint → Queue-based handler (async processing)
@example_worker_router.post("/", response_model=ProcessResponse)
async def process_data(request: ProcessRequest):
    """
    Process data using GPU worker.

    This is a queue-based handler (single POST endpoint).
    Requests are queued and processed asynchronously.
    """
    worker = ExampleWorker()
    result = await worker.process({"input": request.data})
    return result

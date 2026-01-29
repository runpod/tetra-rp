from fastapi import APIRouter
from pydantic import BaseModel

from .endpoint import gpu_hello

gpu_router = APIRouter()


class MessageRequest(BaseModel):
    """Request model for GPU worker."""

    message: str = "Hello from GPU!"


@gpu_router.post("/hello")
async def hello(request: MessageRequest):
    """Simple GPU worker endpoint."""
    result = await gpu_hello({"message": request.message})
    return result

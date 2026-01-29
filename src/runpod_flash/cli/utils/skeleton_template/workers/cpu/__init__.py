from fastapi import APIRouter
from pydantic import BaseModel

from .endpoint import cpu_hello

cpu_router = APIRouter()


class MessageRequest(BaseModel):
    """Request model for CPU worker."""

    message: str = "Hello from CPU!"


@cpu_router.post("/hello")
async def hello(request: MessageRequest):
    """Simple CPU worker endpoint."""
    result = await cpu_hello({"message": request.message})
    return result

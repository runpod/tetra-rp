"""
Example CPU Interface Router

This router demonstrates CPU-based API endpoints using @remote decorated functions.

Each @remote function is deployed as a separate serverless CPU endpoint.
The router provides RESTful access to these functions.

This router will be deployed as a Load-balancer endpoint (multiple GET/POST).
"""

from fastapi import APIRouter
from pydantic import BaseModel

# Import remote functions
from .endpoint import todo_get_list, todo_add_item, todo_delete_item


# Create APIRouter for this interface
# This router will be discovered as a handler during build
example_interface_router = APIRouter()


class TodoItem(BaseModel):
    """Request model for todo item operations."""

    data: str


# Define routes for this interface
# Multiple endpoints → Load-balancer handler (synchronous API)
@example_interface_router.get("/list")
async def get_todo_list():
    """
    Get the todo list.

    This is a load-balancer handler (multiple endpoints).
    Requests are routed directly to available workers.
    """
    result = await todo_get_list()
    return result


@example_interface_router.post("/add")
async def add_todo_item(item: TodoItem):
    """Add a new todo item."""
    result = await todo_add_item(item.data)
    return {"result": result}


@example_interface_router.post("/delete")
async def delete_todo_item(item: TodoItem):
    """Delete a todo item."""
    result = await todo_delete_item(item.data)
    return {"result": result}

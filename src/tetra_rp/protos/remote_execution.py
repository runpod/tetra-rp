# TODO: generate using betterproto

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Union
from pydantic import BaseModel, Field


class FunctionRequest(BaseModel):
    function_name: str = Field(
        description="Name of the function to execute",
    )
    function_code: str = Field(
        description="Source code of the function to execute",
    )
    args: List = Field(
        default_factory=list,
        description="List of base64-encoded cloudpickle-serialized arguments",
    )
    kwargs: Dict = Field(
        default_factory=dict,
        description="Dictionary of base64-encoded cloudpickle-serialized keyword arguments",
    )
    dependencies: Optional[List] = Field(
        default=None,
        description="Optional list of pip packages to install before executing the function",
    )
    system_dependencies: Optional[List] = Field(
        default=None,
        description="Optional list of system dependencies to install before executing the function",
    )


class FunctionResponse(BaseModel):
    success: bool = Field(
        description="Indicates if the function execution was successful",
    )
    result: Optional[str] = Field(
        default=None,
        description="Base64-encoded cloudpickle-serialized result of the function",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if the function execution failed",
    )
    stdout: Optional[str] = Field(
        default=None,
        description="Captured standard output from the function execution",
    )


class RemoteExecutorStub(ABC):
    """Abstract base class for remote execution."""

    @abstractmethod
    async def ExecuteFunction(self, request: FunctionRequest) -> FunctionResponse:
        """Execute a function on the remote resource."""
        raise NotImplementedError("Subclasses should implement this method.")

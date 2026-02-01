"""Remote execution protocol definitions using Pydantic models.

This module defines the request/response protocol for remote function and class execution.
The models align with the protobuf schema for communication with remote workers.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class FunctionRequest(BaseModel):
    """Request model for remote function or class execution.

    Supports both function-based execution and class instantiation with method calls.
    All serialized data (args, kwargs, etc.) are base64-encoded cloudpickle strings.
    """

    # MADE OPTIONAL - can be None for class-only execution
    function_name: Optional[str] = Field(
        default=None,
        description="Name of the function to execute",
    )
    function_code: Optional[str] = Field(
        default=None,
        description="Source code of the function to execute",
    )
    args: List[str] = Field(
        default_factory=list,
        description="List of base64-encoded cloudpickle-serialized arguments",
    )
    kwargs: Dict[str, str] = Field(
        default_factory=dict,
        description="Dictionary of base64-encoded cloudpickle-serialized keyword arguments",
    )
    dependencies: Optional[List[str]] = Field(
        default=None,
        description="Optional list of pip packages to install before executing the function",
    )
    system_dependencies: Optional[List[str]] = Field(
        default=None,
        description="Optional list of system dependencies to install before executing the function",
    )

    # NEW FIELDS FOR CLASS SUPPORT
    execution_type: str = Field(
        default="function", description="Type of execution: 'function' or 'class'"
    )
    class_name: Optional[str] = Field(
        default=None,
        description="Name of the class to instantiate (for class execution)",
    )
    class_code: Optional[str] = Field(
        default=None,
        description="Source code of the class to instantiate (for class execution)",
    )
    constructor_args: List[str] = Field(
        default_factory=list,
        description="List of base64-encoded cloudpickle-serialized constructor arguments",
    )
    constructor_kwargs: Dict[str, str] = Field(
        default_factory=dict,
        description="Dictionary of base64-encoded cloudpickle-serialized constructor keyword arguments",
    )
    method_name: str = Field(
        default="__call__",
        description="Name of the method to call on the class instance",
    )
    instance_id: Optional[str] = Field(
        default=None,
        description="Unique identifier for the class instance (for persistence)",
    )
    create_new_instance: bool = Field(
        default=True,
        description="Whether to create a new instance or reuse existing one",
    )

    # Download acceleration fields
    accelerate_downloads: bool = Field(
        default=True,
        description="Enable download acceleration for dependencies and models",
    )

    @model_validator(mode="after")
    def validate_execution_requirements(self) -> "FunctionRequest":
        """Validate that required fields are provided based on execution_type.

        Note: function_code and class_code are optional to support Flash deployments
        where code is pre-deployed and not sent with the request.
        """
        if self.execution_type == "function":
            if self.function_name is None:
                raise ValueError(
                    'function_name is required when execution_type is "function"'
                )
            # function_code is optional - absent for Flash deployments

        elif self.execution_type == "class":
            if self.class_name is None:
                raise ValueError(
                    'class_name is required when execution_type is "class"'
                )
            # class_code is optional - absent for Flash deployments

        return self


class FunctionResponse(BaseModel):
    """Response model for remote function or class execution results.

    Contains execution results, error information, and metadata about class instances
    when applicable. The result field contains base64-encoded cloudpickle data.
    """

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
    instance_id: Optional[str] = Field(
        default=None, description="ID of the class instance that was used/created"
    )
    instance_info: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Metadata about the class instance (creation time, call count, etc.)",
    )


class RemoteExecutorStub(ABC):
    """Abstract base class for remote execution."""

    @abstractmethod
    async def ExecuteFunction(self, request: FunctionRequest) -> FunctionResponse:
        """Execute a function on the remote resource."""
        raise NotImplementedError("Subclasses should implement this method.")

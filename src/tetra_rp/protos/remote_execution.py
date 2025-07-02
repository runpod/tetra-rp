# =============================================================================
# UPDATED remote_execution.py WITH CLASS SUPPORT AND OPTIONAL FUNCTION FIELDS
# =============================================================================

# TODO: generate using betterproto
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Union
from pydantic import BaseModel, Field, validator


class FunctionRequest(BaseModel):
    # MADE OPTIONAL - can be None for class-only execution
    function_name: Optional[str] = Field(
        default=None,
        description="Name of the function to execute",
    )
    function_code: Optional[str] = Field(
        default=None,
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
        
    # NEW FIELDS FOR CLASS SUPPORT
    execution_type: str = Field(
        default="function",
        description="Type of execution: 'function' or 'class'"
    )
    class_name: Optional[str] = Field(
        default=None,
        description="Name of the class to instantiate (for class execution)"
    )
    class_code: Optional[str] = Field(
        default=None,
        description="Source code of the class to instantiate (for class execution)"
    )
    constructor_args: Optional[List] = Field(
        default_factory=list,
        description="List of base64-encoded cloudpickle-serialized constructor arguments"
    )
    constructor_kwargs: Optional[Dict] = Field(
        default_factory=dict,
        description="Dictionary of base64-encoded cloudpickle-serialized constructor keyword arguments"
    )
    method_name: str = Field(
        default="__call__",
        description="Name of the method to call on the class instance"
    )
    instance_id: Optional[str] = Field(
        default=None,
        description="Unique identifier for the class instance (for persistence)"
    )
    create_new_instance: bool = Field(
        default=True,
        description="Whether to create a new instance or reuse existing one"
    )

    @validator('function_name', 'function_code')
    def validate_function_fields(cls, v, values, field):
        """Validate that function fields are provided when execution_type is 'function'"""
        execution_type = values.get('execution_type', 'function')
        
        if execution_type == 'function' and v is None:
            raise ValueError(f'{field.name} is required when execution_type is "function"')
        
        return v

    @validator('class_name', 'class_code')
    def validate_class_fields(cls, v, values, field):
        """Validate that class fields are provided when execution_type is 'class'"""
        execution_type = values.get('execution_type', 'function')
        
        if execution_type == 'class' and v is None:
            raise ValueError(f'{field.name} is required when execution_type is "class"')
        
        return v


class FunctionResponse(BaseModel):
    # EXISTING FIELDS (unchanged)
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
        
    # NEW FIELDS FOR CLASS SUPPORT
    instance_id: Optional[str] = Field(
        default=None,
        description="ID of the class instance that was used/created"
    )
    instance_info: Optional[Dict] = Field(
        default=None,
        description="Metadata about the class instance (creation time, call count, etc.)"
    )


class RemoteExecutorStub(ABC):
    """Abstract base class for remote execution."""
    
    @abstractmethod
    async def ExecuteFunction(self, request: FunctionRequest) -> FunctionResponse:
        """Execute a function on the remote resource."""
        raise NotImplementedError("Subclasses should implement this method.")
from typing import Callable, Any, List, Union
from pydantic import BaseModel
from .gpu import GpuType, GpuTypeDetail
from .serverless import ServerlessEndpoint


"""
Define the mapping for the methods and their return types
Only include methods from runpod.*
"""
RUNPOD_TYPED_OPERATIONS = {
    "get_gpus": List[GpuType],
    "get_gpu": GpuTypeDetail,
    "get_endpoints": List[ServerlessEndpoint],
}


def inquire(method: Callable, *args, **kwargs) -> Union[List[Any], Any]:
    """
    This function dynamically determines the return type of the provided method
    based on a predefined mapping (`definitions`) and validates the result using
    Pydantic models if applicable.

    Refer to `RUNPOD_TYPED_OPERATIONS` for the mapping.

    Example:
    ----------
    >>> import runpod
    >>> inquire(runpod.get_gpus)
    [
        GpuType(id='NVIDIA A100 80GB', displayName='A100 80GB', memoryInGb=80),
        GpuType(id='NVIDIA A100 40GB', displayName='A100 40GB', memoryInGb=40),
        GpuType(id='NVIDIA A10', displayName='A10', memoryInGb=24)
    ]
    """
    method_name = method.__name__
    return_type = RUNPOD_TYPED_OPERATIONS.get(method_name)

    raw_result = method(*args, **kwargs)

    if hasattr(return_type, "__origin__") and return_type.__origin__ is list:
        # List case
        model_type = return_type.__args__[0]
        if issubclass(model_type, BaseModel):
            return [model_type.model_validate(item) for item in raw_result]
    elif isinstance(return_type, type) and issubclass(return_type, BaseModel):
        # Single object case
        return return_type.model_validate(raw_result)
    else:
        raise ValueError(f"Unsupported return type for method '{method_name}'")

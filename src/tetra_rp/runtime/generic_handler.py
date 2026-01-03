"""Generic RunPod serverless handler factory for Flash."""

import base64
import json
import logging
import traceback
from pathlib import Path
from typing import Any, Callable, Dict

import cloudpickle

logger = logging.getLogger(__name__)


def load_manifest() -> Dict[str, Any]:
    """Load flash_manifest.json from current directory.

    Returns:
        Manifest dictionary, or empty dict if not found
    """
    try:
        manifest_path = Path(__file__).parent.parent.parent / "flash_manifest.json"
        if manifest_path.exists():
            with open(manifest_path) as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load manifest: {e}")

    return {"resources": {}, "function_registry": {}}


def deserialize_arguments(job_input: Dict[str, Any]) -> tuple[list, dict]:
    """Deserialize function arguments from job input.

    Args:
        job_input: Input dict from RunPod job with 'args' and 'kwargs' keys

    Returns:
        Tuple of (args list, kwargs dict) deserialized from cloudpickle
    """
    args = [
        cloudpickle.loads(base64.b64decode(arg)) for arg in job_input.get("args", [])
    ]
    kwargs = {
        k: cloudpickle.loads(base64.b64decode(v))
        for k, v in job_input.get("kwargs", {}).items()
    }
    return args, kwargs


def serialize_result(result: Any) -> str:
    """Serialize function result for response.

    Args:
        result: Return value from function

    Returns:
        Base64-encoded cloudpickle of result
    """
    return base64.b64encode(cloudpickle.dumps(result)).decode("utf-8")


def execute_function(
    func_or_class: Callable,
    args: list,
    kwargs: dict,
    execution_type: str,
    job_input: Dict[str, Any],
) -> Any:
    """Execute function or class method.

    Args:
        func_or_class: Function or class to execute
        args: Positional arguments
        kwargs: Keyword arguments
        execution_type: Either "function" or "class"
        job_input: Full job input for method calls

    Returns:
        Result of execution

    Raises:
        Exception: If execution fails
    """
    if execution_type == "class":
        # Instantiate class with constructor args
        instance = func_or_class(*args, **kwargs)
        method_name = job_input.get("method_name", "__call__")

        # Call method on instance
        method = getattr(instance, method_name)
        method_args, method_kwargs = deserialize_arguments(
            {
                "args": job_input.get("method_args", []),
                "kwargs": job_input.get("method_kwargs", {}),
            }
        )
        return method(*method_args, **method_kwargs)
    else:
        # Direct function call
        return func_or_class(*args, **kwargs)


def create_handler(function_registry: Dict[str, Callable]) -> Callable:
    """Create a RunPod serverless handler with given function registry.

    This factory function creates a handler that:
    1. Deserializes function arguments from cloudpickle + base64
    2. Looks up function/class in registry by name
    3. Executes function or class method
    4. Serializes result back to cloudpickle + base64
    5. Returns RunPod-compatible response dict

    Args:
        function_registry: Dict mapping function names to function/class objects

    Returns:
        Handler function compatible with runpod.serverless.start()

    Example:
        ```python
        from tetra_rp.runtime.generic_handler import create_handler
        from workers.gpu import process_data, analyze_data

        registry = {
            "process_data": process_data,
            "analyze_data": analyze_data,
        }

        handler = create_handler(registry)

        if __name__ == "__main__":
            import runpod
            runpod.serverless.start({"handler": handler})
        ```
    """

    def handler(job: Dict[str, Any]) -> Dict[str, Any]:
        """RunPod serverless handler.

        Args:
            job: RunPod job dict with 'input' key

        Returns:
            Response dict with 'success', 'result'/'error' keys
        """
        job_input = job.get("input", {})
        function_name = job_input.get("function_name")
        execution_type = job_input.get("execution_type", "function")

        if function_name not in function_registry:
            return {
                "success": False,
                "error": f"Function '{function_name}' not found in registry. "
                f"Available: {list(function_registry.keys())}",
            }

        try:
            # Deserialize arguments
            args, kwargs = deserialize_arguments(job_input)

            # Get function/class from registry
            func_or_class = function_registry[function_name]

            # Execute function or class
            result = execute_function(
                func_or_class, args, kwargs, execution_type, job_input
            )

            # Serialize result
            serialized_result = serialize_result(result)

            return {
                "success": True,
                "result": serialized_result,
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc(),
            }

    return handler

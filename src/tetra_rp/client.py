import base64
import inspect
import logging
import textwrap
import uuid
from functools import wraps
from typing import List, Type

import cloudpickle

from .core.resources import ResourceManager, ServerlessEndpoint
from .protos.remote_execution import FunctionRequest
from .stubs import stub_resource

log = logging.getLogger(__name__)


def remote(
    resource_config: ServerlessEndpoint,
    dependencies: List[str] = None,
    system_dependencies: List[str] = None,
    **extra,
):
    """
    Enhanced decorator supporting both functions and classes.

    Usage:
        # Function (works exactly as before)
        @remote(resource_config=config)
        def my_function(data):
            return process(data)

        # Class (NEW!)
        @remote(resource_config=config)
        class MyModel:
            def __init__(self, model_path):
                self.model = load_model(model_path)

            def predict(self, data):
                return self.model(data)
    """

    def decorator(func_or_class):
        if inspect.isclass(func_or_class):
            # Handle class decoration
            return _create_remote_class(
                func_or_class, resource_config, dependencies, system_dependencies, extra
            )
        else:
            # Handle function decoration (unchanged)
            @wraps(func_or_class)
            async def wrapper(*args, **kwargs):
                resource_manager = ResourceManager()
                remote_resource = await resource_manager.get_or_deploy_resource(
                    resource_config
                )

                stub = stub_resource(remote_resource, **extra)
                return await stub(
                    func_or_class, dependencies, system_dependencies, *args, **kwargs
                )

            return wrapper

    return decorator


def extract_class_code_simple(cls: Type) -> str:
    """Extract clean class code without decorators and proper indentation"""
    try:
        # Get source code
        source = inspect.getsource(cls)

        # Split into lines
        lines = source.split("\n")

        # Find the class definition line (starts with 'class' and contains ':')
        class_start_idx = -1
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("class ") and ":" in stripped:
                class_start_idx = i
                break

        if class_start_idx == -1:
            raise ValueError("Could not find class definition")

        # Take lines from class definition onwards (ignore everything before)
        class_lines = lines[class_start_idx:]

        # Remove empty lines at the end
        while class_lines and not class_lines[-1].strip():
            class_lines.pop()

        # Join back and dedent to remove any leading indentation
        class_code = "\n".join(class_lines)
        class_code = textwrap.dedent(class_code)

        # Validate the code by trying to compile it
        compile(class_code, "<string>", "exec")

        print(f"Successfully extracted class code for {cls.__name__}")
        return class_code

    except Exception as e:
        print(f"Warning: Could not extract class code for {cls.__name__}: {e}")
        print("Falling back to basic class structure")

        # Enhanced fallback: try to preserve method signatures
        fallback_methods = []
        for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
            try:
                sig = inspect.signature(method)
                fallback_methods.append(f"    def {name}{sig}:")
                fallback_methods.append("        pass")
                fallback_methods.append("")
            except:
                fallback_methods.append(f"    def {name}(self, *args, **kwargs):")
                fallback_methods.append("        pass")
                fallback_methods.append("")

        fallback_code = f"""class {cls.__name__}:
    def __init__(self, *args, **kwargs):
        pass

{chr(10).join(fallback_methods)}"""

        return fallback_code


def _create_remote_class(
    cls: Type,
    resource_config: ServerlessEndpoint,
    dependencies: List[str],
    system_dependencies: List[str],
    extra: dict,
):
    """
    Create a remote class wrapper.
    """

    class RemoteClassWrapper:
        def __init__(self, *args, **kwargs):
            self._class_type = cls
            self._resource_config = resource_config
            self._dependencies = dependencies or []
            self._system_dependencies = system_dependencies or []
            self._extra = extra
            self._constructor_args = args
            self._constructor_kwargs = kwargs
            self._instance_id = f"{cls.__name__}_{uuid.uuid4().hex[:8]}"
            self._initialized = False

            self._clean_class_code = extract_class_code_simple(cls)

            log.info(f"Created remote class wrapper for {cls.__name__}")

        async def _ensure_initialized(self):
            """Ensure the remote instance is created."""
            if self._initialized:
                return

            # Get remote resource
            resource_manager = ResourceManager()
            remote_resource = await resource_manager.get_or_deploy_resource(
                self._resource_config
            )
            self._stub = stub_resource(remote_resource, **self._extra)

            # Create the remote instance by calling a method (which will trigger instance creation)
            # We'll do this on first method call
            self._initialized = True

        def __getattr__(self, name):
            """Dynamically create method proxies for all class methods."""
            if name.startswith("_"):
                raise AttributeError(
                    f"'{self.__class__.__name__}' object has no attribute '{name}'"
                )

            async def method_proxy(*args, **kwargs):
                await self._ensure_initialized()

                # Create class method request

                # class_code = inspect.getsource(self._class_type)
                class_code = self._clean_class_code

                request = FunctionRequest(
                    execution_type="class",
                    class_name=self._class_type.__name__,
                    class_code=class_code,
                    method_name=name,
                    args=[
                        base64.b64encode(cloudpickle.dumps(arg)).decode("utf-8")
                        for arg in args
                    ],
                    kwargs={
                        k: base64.b64encode(cloudpickle.dumps(v)).decode("utf-8")
                        for k, v in kwargs.items()
                    },
                    constructor_args=[
                        base64.b64encode(cloudpickle.dumps(arg)).decode("utf-8")
                        for arg in self._constructor_args
                    ],
                    constructor_kwargs={
                        k: base64.b64encode(cloudpickle.dumps(v)).decode("utf-8")
                        for k, v in self._constructor_kwargs.items()
                    },
                    dependencies=self._dependencies,
                    system_dependencies=self._system_dependencies,
                    instance_id=self._instance_id,
                    create_new_instance=not hasattr(
                        self, "_stub"
                    ),  # Create new only on first call
                )

                # Execute via stub
                return await self._stub.execute_class_method(request)

            return method_proxy

    return RemoteClassWrapper

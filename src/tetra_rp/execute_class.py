import base64
import inspect
import logging
import textwrap
import uuid
from typing import List, Type, Optional

import cloudpickle

from .core.resources import ResourceManager, ServerlessResource
from .protos.remote_execution import FunctionRequest
from .stubs import stub_resource

log = logging.getLogger(__name__)


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

        log.debug(f"Successfully extracted class code for {cls.__name__}")
        return class_code

    except Exception as e:
        log.warning(f"Could not extract class code for {cls.__name__}: {e}")
        log.warning("Falling back to basic class structure")

        # Enhanced fallback: try to preserve method signatures
        fallback_methods = []
        for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
            try:
                sig = inspect.signature(method)
                fallback_methods.append(f"    def {name}{sig}:")
                fallback_methods.append("        pass")
                fallback_methods.append("")
            except (TypeError, ValueError, OSError) as e:
                log.warning(f"Could not extract method signature for {name}: {e}")
                fallback_methods.append(f"    def {name}(self, *args, **kwargs):")
                fallback_methods.append("        pass")
                fallback_methods.append("")

        fallback_code = f"""class {cls.__name__}:
    def __init__(self, *args, **kwargs):
        pass

{chr(10).join(fallback_methods)}"""

        return fallback_code


def create_remote_class(
    cls: Type,
    resource_config: ServerlessResource,
    dependencies: Optional[List[str]],
    system_dependencies: Optional[List[str]],
    extra: dict,
):
    """
    Create a remote class wrapper.
    """
    # Validate inputs
    if not inspect.isclass(cls):
        raise TypeError(f"Expected a class, got {type(cls).__name__}")
    if not hasattr(cls, "__name__"):
        raise ValueError("Class must have a __name__ attribute")

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

            log.debug(f"Created remote class wrapper for {cls.__name__}")

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
                return await self._stub.execute_class_method(request)  # type: ignore

            return method_proxy

    return RemoteClassWrapper

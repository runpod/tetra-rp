from functools import wraps
from typing import List, Union, Type
import logging
import inspect
import uuid
import base64
import cloudpickle
from .core.resources import ServerlessEndpoint, ResourceManager
from .stubs import stub_resource
from .protos.remote_execution import FunctionRequest

log = logging.getLogger(__name__)

def remote(
    resource_config: ServerlessEndpoint,
    dependencies: List[str] = None,
    system_dependencies: List[str] = None,
    **extra
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
            return _create_remote_class(func_or_class, resource_config, dependencies, system_dependencies, extra)
        else:
            # Handle function decoration (unchanged)
            @wraps(func_or_class)
            async def wrapper(*args, **kwargs):
                resource_manager = ResourceManager()
                remote_resource = await resource_manager.get_or_deploy_resource(resource_config)
                
                stub = stub_resource(remote_resource, **extra)
                return await stub(func_or_class, dependencies, system_dependencies, *args, **kwargs)
            
            return wrapper
    
    return decorator

def _create_remote_class(cls: Type, resource_config: ServerlessEndpoint, dependencies: List[str], system_dependencies: List[str], extra: dict):
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
            
            log.info(f"Created remote class wrapper for {cls.__name__}")
        
        async def _ensure_initialized(self):
            """Ensure the remote instance is created."""
            if self._initialized:
                return
            
            # Get remote resource
            resource_manager = ResourceManager()
            remote_resource = await resource_manager.get_or_deploy_resource(self._resource_config)
            self._stub = stub_resource(remote_resource, **self._extra)
            
            # Create the remote instance by calling a method (which will trigger instance creation)
            # We'll do this on first method call
            self._initialized = True
        
        def __getattr__(self, name):
            """Dynamically create method proxies for all class methods."""
            if name.startswith('_'):
                raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
            
            async def method_proxy(*args, **kwargs):
                await self._ensure_initialized()
                
                # Create class method request
                
                class_code = inspect.getsource(self._class_type)
                
                request = FunctionRequest(
                    execution_type="class",
                    class_name=self._class_type.__name__,
                    class_code=class_code,
                    method_name=name,
                    args=[base64.b64encode(cloudpickle.dumps(arg)).decode("utf-8") for arg in args],
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
                    create_new_instance=not hasattr(self, '_stub')  # Create new only on first call
                )
                
                # Execute via stub
                return await self._stub.execute_class_method(request)
            
            return method_proxy
    
    return RemoteClassWrapper
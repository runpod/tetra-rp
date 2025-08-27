"""
Simplified Runtime Two Client for Testing

This provides a simple way to test Runtime Two functionality by:
1. Hardcoding the endpoint URL (from manually deployed container)
2. Removing complex deployment logic
3. Focusing on the core dual-capability functionality
"""

import inspect
import logging
import aiohttp
from typing import List, Optional, Dict, Any

from .endpoint import scan_endpoint_methods
from .protos.remote_execution import FunctionRequest
from .serialization_utils import SerializationUtils

log = logging.getLogger(__name__)


class SimpleRuntimeTwo:
    """
    Simplified Runtime Two client for testing.
    
    Usage:
        # After manually deploying Runtime Two container
        runtime = SimpleRuntimeTwo("https://your-deployed-endpoint.com")
        
        @runtime.remote_class
        class MLModel:
            @endpoint(methods=['POST'])
            def predict(self, data):
                return result
    """
    
    def __init__(self, endpoint_url: str, api_key: Optional[str] = None):
        """
        Initialize with hardcoded endpoint URL and optional API key.
        
        Args:
            endpoint_url: Base URL of deployed Runtime Two container
                         e.g. "https://abc123-def456.rp.runpod.ai"
            api_key: RunPod API key for authentication (or set RUNPOD_API_KEY env var)
        """
        import os
        
        self.endpoint_url = endpoint_url.rstrip('/')
        self.api_key = api_key or os.getenv('RUNPOD_API_KEY')
        self._session = None
        
        if not self.api_key:
            log.warning("No API key provided. Set RUNPOD_API_KEY env var or pass api_key parameter.")
        
        log.info(f"SimpleRuntimeTwo initialized with endpoint: {self.endpoint_url}")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session with authentication headers."""
        if self._session is None or self._session.closed:
            headers = {}
            if self.api_key:
                headers['Authorization'] = f'Bearer {self.api_key}'
            
            self._session = aiohttp.ClientSession(headers=headers)
        return self._session
    
    def remote_class(
        self, 
        dependencies: Optional[List[str]] = None,
        system_dependencies: Optional[List[str]] = None
    ):
        """
        Simplified decorator for Runtime Two classes.
        
        Args:
            dependencies: Python packages to install
            system_dependencies: System packages to install
        """
        def decorator(cls):
            return SimpleClassWrapper(
                cls=cls,
                runtime=self,
                dependencies=dependencies or [],
                system_dependencies=system_dependencies or []
            )
        
        return decorator
    
    async def call_remote_method(self, request: FunctionRequest) -> Any:
        """Call remote method via /execute endpoint."""
        session = await self._get_session()
        
        url = f"{self.endpoint_url}/execute"
        payload = {"input": request.model_dump(exclude_none=True)}
        
        log.debug(f"Remote call to {url}")
        
        async with session.post(url, json=payload) as response:
            response.raise_for_status()
            result = await response.json()
        
        if not result.get('success'):
            raise RuntimeError(f"Remote execution failed: {result.get('error')}")
        
        # Deserialize result
        if result.get('result'):
            return SerializationUtils.deserialize_result(result['result'])
        return None
    
    async def call_http_endpoint(self, method_name: str, data: Dict[str, Any]) -> Any:
        """Call HTTP endpoint directly."""
        session = await self._get_session()
        
        url = f"{self.endpoint_url}/{method_name}"
        
        log.debug(f"HTTP call to {url} with data: {data}")
        
        async with session.post(url, json=data) as response:
            response.raise_for_status()
            return await response.json()
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Runtime Two health."""
        session = await self._get_session()
        
        url = f"{self.endpoint_url}/health"
        
        async with session.get(url) as response:
            response.raise_for_status()
            return await response.json()
    
    async def close(self):
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()


class SimpleClassWrapper:
    """Simplified class wrapper for testing Runtime Two."""
    
    def __init__(self, cls, runtime: SimpleRuntimeTwo, dependencies: List[str], system_dependencies: List[str]):
        self._original_class = cls
        self._runtime = runtime
        self._dependencies = dependencies
        self._system_dependencies = system_dependencies
        
        # Scan for @endpoint methods
        self._endpoint_methods = scan_endpoint_methods(cls)
        
        log.info(f"Created simple wrapper for {cls.__name__}")
        log.info(f"Found {len(self._endpoint_methods)} endpoint methods: {list(self._endpoint_methods.keys())}")
    
    def __call__(self, *args, **kwargs):
        """Create instance wrapper when class is instantiated."""
        return SimpleInstanceWrapper(
            wrapper=self,
            constructor_args=args,
            constructor_kwargs=kwargs
        )


class SimpleInstanceWrapper:
    """Instance wrapper for method calls."""
    
    def __init__(self, wrapper: SimpleClassWrapper, constructor_args: tuple, constructor_kwargs: dict):
        self._wrapper = wrapper
        self._constructor_args = constructor_args
        self._constructor_kwargs = constructor_kwargs
        self._instance_id = f"{wrapper._original_class.__name__}_test"
    
    def __getattr__(self, name: str):
        """Route method calls to appropriate interface."""
        
        if name in self._wrapper._endpoint_methods:
            # HTTP endpoint method
            return self._create_http_proxy(name)
        else:
            # Remote execution method
            return self._create_remote_proxy(name)
    
    def _create_http_proxy(self, method_name: str):
        """Create HTTP method proxy."""
        
        async def http_proxy(*args, **kwargs):
            # Convert args to kwargs
            if args:
                method_sig = inspect.signature(getattr(self._wrapper._original_class, method_name))
                param_names = list(method_sig.parameters.keys())[1:]  # Skip 'self'
                for i, arg in enumerate(args):
                    if i < len(param_names):
                        kwargs[param_names[i]] = arg
            
            return await self._wrapper._runtime.call_http_endpoint(method_name, kwargs)
        
        return http_proxy
    
    def _create_remote_proxy(self, method_name: str):
        """Create remote execution proxy."""
        
        async def remote_proxy(*args, **kwargs):
            # Create class execution request
            request = self._create_function_request(method_name, args, kwargs)
            return await self._wrapper._runtime.call_remote_method(request)
        
        return remote_proxy
    
    def _create_function_request(self, method_name: str, args: tuple, kwargs: dict) -> FunctionRequest:
        """Create FunctionRequest for remote execution."""
        import textwrap
        
        # Get class source and clean it
        class_source = inspect.getsource(self._wrapper._original_class)
        clean_class_code = textwrap.dedent(class_source)
        
        # Remove @runtime.remote_class decorator lines
        lines = clean_class_code.split('\n')
        cleaned_lines = []
        skip_next = False
        
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('@') and 'remote_class' in stripped:
                skip_next = True
                continue
            elif skip_next and stripped == '':
                skip_next = False
                continue
            elif skip_next and stripped.startswith('class'):
                skip_next = False
                cleaned_lines.append(line)
            elif not skip_next:
                cleaned_lines.append(line)
        
        clean_class_code = '\n'.join(cleaned_lines)
        
        # Serialize arguments
        serialized_args = [
            SerializationUtils.serialize_result(arg) for arg in args
        ]
        serialized_kwargs = {
            k: SerializationUtils.serialize_result(v) for k, v in kwargs.items()
        }
        
        # Serialize constructor arguments
        constructor_args = [
            SerializationUtils.serialize_result(arg) for arg in self._constructor_args
        ]
        constructor_kwargs = {
            k: SerializationUtils.serialize_result(v) for k, v in self._constructor_kwargs.items()
        }
        
        return FunctionRequest(
            execution_type="class",
            class_name=self._wrapper._original_class.__name__,
            class_code=clean_class_code,
            method_name=method_name,
            args=serialized_args,
            kwargs=serialized_kwargs,
            constructor_args=constructor_args,
            constructor_kwargs=constructor_kwargs,
            dependencies=self._wrapper._dependencies,
            system_dependencies=self._wrapper._system_dependencies,
            instance_id=self._instance_id,
            create_new_instance=True
        )
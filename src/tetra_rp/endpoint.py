"""
HTTP Endpoint decorator for Runtime Two

This module provides the @endpoint decorator that marks class methods
for HTTP endpoint exposure in Runtime Two.
"""

from typing import List, Optional


def endpoint(methods: List[str] = ['POST'], route: Optional[str] = None):
    """
    Decorator to mark class methods as HTTP endpoints in Runtime Two.
    
    Args:
        methods: List of HTTP methods supported (GET, POST, PUT, DELETE, etc.)
        route: Custom route path. If None, uses "/{method_name}"
    
    Example:
        @endpoint(methods=['GET', 'POST'])
        def predict(self, data):
            return self.model.predict(data)
            
        @endpoint(methods=['GET'], route='/health-check')
        def health(self):
            return {"status": "healthy"}
    """
    def decorator(func):
        # Attach endpoint configuration to the method
        func._endpoint_config = {
            'methods': methods,
            'route': route or f"/{func.__name__}"
        }
        return func
    
    return decorator


def scan_endpoint_methods(cls):
    """
    Scan a class for methods decorated with @endpoint.
    
    Args:
        cls: Class to scan
        
    Returns:
        Dict mapping method names to their endpoint configurations
    """
    import inspect
    
    endpoint_methods = {}
    
    for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
        if hasattr(method, '_endpoint_config'):
            endpoint_methods[name] = method._endpoint_config
            
    return endpoint_methods
import threading


class SingletonMixin:
    """Thread-safe singleton mixin class.

    Uses threading.Lock to ensure only one instance is created
    per class, even under concurrent access.
    """

    _instances = {}
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        # Use double-checked locking pattern for performance
        if cls not in cls._instances:
            with cls._lock:
                # Check again inside the lock (double-checked locking)
                if cls not in cls._instances:
                    cls._instances[cls] = super().__new__(cls)
        return cls._instances[cls]

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

    def __reduce__(self):
        """Custom pickle support to handle the singleton pattern.

        Returns the class and arguments needed to reconstruct the instance,
        skipping the threading.Lock which can't be pickled in all contexts.
        """
        # For subclasses of SingletonMixin, return enough to reconstruct via __new__
        # which will return the singleton instance
        return (
            self.__class__,
            (),  # No args - __new__ will use the cached instance
            self.__getstate__() if hasattr(self, "__getstate__") else self.__dict__,
        )

    def __setstate__(self, state):
        """Restore object state from pickle."""
        if hasattr(self, "__setstate__"):
            super().__setstate__(state)
        else:
            self.__dict__.update(state)

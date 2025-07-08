from enum import Enum


class WorkerStatus(Enum):
    """Enum representing the status of a worker"""

    IDLE = "idle"
    RUNNING = "running"
    OFFLINE = "offline"


class JobStatus(Enum):
    """Enum representing the status of a job"""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

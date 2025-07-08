import uuid
from dataclass import WorkerStatus


class Worker:
    """Represents a single worker in the pool

    For Now we store ressources in memory
    """

    def __init__(self, resource_config: dict):
        self.worker_id = str(uuid.uuid4())[:8]
        self.resource_config = resource_config
        self.status = WorkerStatus.IDLE

        self.current_job_id = None

    def __repr__(self):
        return f"Worker(worker_id={self.worker_id}, status={self.status})"

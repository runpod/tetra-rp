import uuid
from dataclass import JobStatus


class Job:
    """Represents a 'job' in the system

    In a real system, this might contain the function to run,
    arguments, and reference to data or code.
    """

    def __init__(self, resource_config: dict):
        self.job_id = str(uuid.uuid4())[:8]
        self.resource_config = resource_config
        self.status = JobStatus.QUEUED

        self.worker_id = None
        self.result = None
        self.error = None

    def __repr__(self):
        return f"Job(job_id={self.job_id}, status={self.status})"

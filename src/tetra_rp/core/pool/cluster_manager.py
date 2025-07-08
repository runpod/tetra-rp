import time
from worker import Worker
from job import Job

from dataclass import WorkerStatus, JobStatus

import logging
import inspect


def setup_logging(level=logging.INFO, fmt=None):
    if fmt is None:
        fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    logging.basicConfig(level=level, format=fmt)


def get_logger(name=None):
    """
    Returns a logger. If no name is provided, it infers the caller's module name.
    """
    if name is None:
        # Get the caller's module name.
        frame = inspect.stack()[1]
        module = inspect.getmodule(frame[0])
        name = module.__name__ if module else "__main__"
    return logging.getLogger(name)


logger = get_logger(__name__)


class ClusterManager:
    """
    Manages workers and Jobs currently in Memory:
    - Runpod for provisioning
    - Real remote execution
    - Data base for the
    """

    def __init__(self):
        self.workers = {}  # Worker ID -> Worker
        self.jobs = {}  # Job ID -> Job

    # ----------------- Worker Management -----------------
    # ------------------------------------------------------
    def add_worker(self, resource_config: dict):
        """
        Add a new worker to the cluster
        """
        # here will go the logic to create a worker and add it to the cluster: RUNPOD LOGIC will be added here.
        worker = Worker(resource_config)
        self.workers[worker.worker_id] = worker

        logger.info(f"Added worker {worker.worker_id} to the cluster")
        return worker.worker_id

    def remove_worker(self, worker_id):
        """
        Remove a worker from the cluster
        """
        worker = self.workers.get(worker_id)
        if not worker:
            logger.error(f"Worker {worker_id} not found")
            return False
        if worker.status == WorkerStatus.RUNNING:
            logger.error(f"Worker {worker_id} is still running")
            return False
        del self.workers[worker_id]
        logger.info(f"Removed worker {worker_id} from the cluster")
        return True

    def list_workers(self):
        """
        List all workers in the cluster
        """
        return list(self.workers.values())

    # ----------------- Job Management -----------------
    # ---------------------------------------------------

    def submit_job(self, resource_config: dict):
        """
        Submit a new job to the cluster (Queueud). Then attempt to scheduel it.
        """
        job = Job(resource_config)
        self.jobs[job.job_id] = job
        logger.info(f"Submitted job {job.job_id} to the cluster")
        # attempt to schedule the job
        self.schedule_job(job)
        return job.job_id

    def schedule_job(self, job: Job):
        """
        find a suitable worker for the job. It none, Job remains queued.
        If we want to a auto provision we can actually add a logic here to add a worker if none is available.
        """
        if job.status != JobStatus.QUEUED:
            logger.error(f"Job {job.job_id} is not pending")
            return False

        # Find worker candidate
        candidate = self.find_idle_worker(job.resource_config)
        if candidate:
            self.assign_job_to_worker(job, candidate)
        else:
            logger.info(f"No worker available for job {job.job_id}")
            # we cn either provision new worker from here and then scehediule the job from here.

    def find_idle_worker(self, resource_config: dict):
        """
        Find an idle worker that can run the job
        """
        for w in self.workers.values():
            if w.status == WorkerStatus.IDLE:
                # check the resource config
                if w.resource_config == resource_config:
                    continue
                return w
        return None

    def assign_job_to_worker(self, job: Job, worker: Worker):
        """
        Mark the job as running and the worker as Running and 'execute' the job.
        In a real system, we would send a remote command to the worker (eg: gRPC) to execute the job.
        """
        job.worker_id = worker.worker_id
        job.status = JobStatus.RUNNING
        worker.status = WorkerStatus.RUNNING
        worker.current_job_id = job.job_id
        logger.info(f"Assigned job {job.job_id} to worker {worker.worker_id}")
        self._execute_job(job, worker)

    def _execute_job(self, job: Job, worker: Worker):
        """
        Simulate the remote execution. right now, we jsut sleep for 1s.
        In production, what we we can do is:
        - Open a gRPC connection to the worker
        - pass the job details
        - wait for the compeltion call back
        """
        try:
            logger.info(f"Executing job {job.job_id} on worker {worker.worker_id}")
            time.sleep(
                1
            )  # Here we can add the actual execution logic, currently it mimics the execution.

            # mark the job as completed
            job.status = JobStatus.COMPLETED
            job.result = "Job completed successfully"
            logger.info(f"[Cluster Manager] Job {job.job_id} completed successfully")
        except Exception as e:
            job.status = JobStatus.FAILED
            job.result = f"Job failed: {str(e)}"
            logger.error(f"[Cluster Manager] Job {job.job_id} failed: {str(e)}")
        finally:
            worker.status = WorkerStatus.IDLE
            worker.current_job_id = None

    def get_job_status(self, job_id):
        """
        Get the job details
        """
        job = self.jobs.get(job_id)
        if not job:
            logger.error(f"Job {job_id} not found")
            return None
        return job

    # this function has retry logic but it's currently fuzzy, we might have to change it.

    def retry_queued_jobs(self):
        """
        Retry all queued jobs
        """
        for job in self.jobs.values():
            if job.status == JobStatus.QUEUED:
                self.schedule_job(job)

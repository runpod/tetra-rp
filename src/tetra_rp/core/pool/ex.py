from cluster_manager import ClusterManager


if __name__ == "__main__":
    cm = ClusterManager()

    # 1) Submit a job with no existing workers (use resource_config dict)
    job_id = cm.submit_job(
        resource_config={"gpu": "H100", "memory": 16, "network_volume": 50}
    )
    print(
        "Job status:", cm.get_job_status(job_id)
    )  # should be QUEUED, no suitable worker

    # 2) Add a worker that doesn't match the GPU
    w1 = cm.add_worker(
        resource_config={"gpu": "H100", "memory": 16, "network_volume": 50}
    )
    # Re-try scheduling
    cm.retry_queued_jobs()
    print("Job status (still queued):", cm.get_job_status(job_id))

    # 3) Add a matching worker
    w2 = cm.add_worker(
        resource_config={"gpu": "H100", "memory": 16, "network_volume": 50}
    )
    # Re-try scheduling
    cm.retry_queued_jobs()
    print("Job status (should complete):", cm.get_job_status(job_id))

    # 4) Submit another job that requires less resources
    job_id2 = cm.submit_job(resource_config={"memory": 8, "network_volume": 10})
    # Should be assigned to w1 if it's idle
    print("Job2 final status:", cm.get_job_status(job_id2))

    # 5) Show final state of workers
    for worker in cm.list_workers():
        print("Worker:", worker)

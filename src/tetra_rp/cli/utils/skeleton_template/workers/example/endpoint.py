"""
Example GPU Worker
"""

from tetra_rp import remote, LiveServerless, GpuGroup


# Configure GPU resource for this worker
config = LiveServerless(
    name="example_worker",
    gpus=[GpuGroup.ADA_24],  # RTX 4090
)


@remote(config)
class ExampleWorker:
    """Example GPU worker for processing tasks."""

    def __init__(self):
        """Initialize the worker."""
        print("ExampleWorker initialized")

    def process(self, input_data: dict) -> dict:
        """
        Process input data and return result.

        Args:
            input_data: Dictionary with input parameters

        Returns:
            Dictionary with processing results
        """
        # Your GPU processing logic here
        result = {
            "status": "success",
            "input": input_data,
            "output": f"Processed: {input_data}"
        }

        return result


# Run this script by itself to test in Live Serverless
if __name__ == "__main__":
    import asyncio

    worker = ExampleWorker()
    payload = {
        "input": {
            "foo": "bar"
        }
    }

    result = asyncio.run(worker.process(payload))

    print(result)

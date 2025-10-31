"""
Example GPU Worker

This is an example of a GPU worker class that can be deployed
to RunPod serverless endpoints.
"""

from tetra_rp import remote, LiveServerless


# Configure GPU resource
config = LiveServerless(
    name="example_worker",
    workersMax=3,
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

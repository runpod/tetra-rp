import asyncio
from dotenv import load_dotenv
from tetra import remote, LiveServerless

# Load environment variables from .env file
load_dotenv()

# Configuration for a GPU resource
gpu_config = LiveServerless(
    gpuIds="NVIDIA H200",
    workersMax=1,
    name="example_matrix_operations_server",
)

@remote(
    resource_config=gpu_config,
    dependencies=["numpy", "torch"]
)
def tetra_matrix_operations(size):
    """Perform large matrix operations using NumPy and check GPU availability."""
    import numpy as np
    import torch
    
    # Get GPU count and name
    device_count = torch.cuda.device_count()
    device_name = torch.cuda.get_device_name(0)
    
    # Create large random matrices
    A = np.random.rand(size, size)
    B = np.random.rand(size, size)

    # Perform matrix multiplication
    C = np.dot(A, B)
    
    return {
        "matrix_size": size,
        "result_shape": C.shape,
        "result_mean": float(np.mean(C)),
        "result_std": float(np.std(C)),
        "device_count": device_count,
        "device_name": device_name
    }

# Single-process version:
async def main():
    print("Starting large matrix operations on GPU...")
    result = await tetra_matrix_operations(1000)
    
    # Print the results
    print("\nMatrix operations results:")
    print(f"Matrix size: {result['matrix_size']}x{result['matrix_size']}")
    print(f"Result shape: {result['result_shape']}")
    print(f"Result mean: {result['result_mean']:.4f}")
    print(f"Result standard deviation: {result['result_std']:.4f}")
    
    # Print GPU information
    print("\nGPU Information:")
    print(f"GPU device count: {result['device_count']}")
    print(f"GPU device name: {result['device_name']}")

# Uncomment below for parallel-process version:
# async def main():
#     print("Starting large matrix operations on GPU...")
    
#     # Run matrix operations in parallel
#     results = await asyncio.gather(
#         tetra_matrix_operations(500),
#         tetra_matrix_operations(1000),
#         tetra_matrix_operations(2000)
#     )

#     print("\nMatrix operations results:")
#     # Print the results for each matrix size
#     for result in results:
#         print(f"\nMatrix size: {result['matrix_size']}x{result['matrix_size']}")
#         print(f"Result shape: {result['result_shape']}")
#         print(f"Result mean: {result['result_mean']:.4f}")
#         print(f"Result standard deviation: {result['result_std']:.4f}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"An error occurred: {e}")

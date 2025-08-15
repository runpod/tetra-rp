import asyncio
from dotenv import load_dotenv
from tetra_rp import remote, LiveServerless

# Load environment variables from .env file
load_dotenv()

# Configuration for GPU workload
gpu_config = LiveServerless(
    name="gpu_compute",
    workersMax=1,
    gpu=1,
    gpuType="A40",
    cpu=4,
    memory=8192,
)


@remote(gpu_config)
def gpu_computation():
    """GPU-accelerated computation example."""
    try:
        import torch

        # Check GPU availability
        if torch.cuda.is_available():
            device = torch.cuda.get_device_name(0)
            print(f"Using GPU: {device}")

            # Simple GPU computation
            x = torch.randn(1000, 1000).cuda()
            y = torch.randn(1000, 1000).cuda()
            result = torch.mm(x, y)

            return {
                "device": device,
                "matrix_shape": result.shape,
                "result_mean": result.mean().item(),
                "computation": "Matrix multiplication completed on GPU",
            }
        else:
            return {"error": "GPU not available"}

    except ImportError:
        return {"error": "PyTorch not available"}


async def main():
    print("🚀 Running GPU compute example...")
    result = await gpu_computation()

    if "error" in result:
        print(f"{result['error']}")
    else:
        print("GPU computation completed!")
        print(f"Device: {result['device']}")
        print(f"Result: {result['computation']}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"An error occurred: {e}")

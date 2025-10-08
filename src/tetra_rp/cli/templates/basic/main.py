import asyncio
from dotenv import load_dotenv
from tetra_rp import remote, LiveServerless

# Load environment variables from .env file
load_dotenv()

# Configuration for a simple resource
config = LiveServerless(
    name="basic_example",
    workersMax=1,
)


@remote(config)
def hello_world():
    """Simple remote function example."""
    print("Hello from the remote function!")
    return "Hello, World!"


async def main():
    print("🚀 Running basic Tetra example...")
    result = await hello_world()
    print(f"Result: {result}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"An error occurred: {e}")

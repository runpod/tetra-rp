import asyncio
from dotenv import load_dotenv
from tetra_rp import remote, LiveServerless
from api import create_api_app

# Load environment variables from .env file
load_dotenv()

# Configuration for web API
api_config = LiveServerless(
    name="web_api_service",
    workersMax=3,
    cpu=2,
    memory=2048,
    ports=[8000],
)


@remote(api_config)
def run_api_server():
    """Run FastAPI web service."""
    import uvicorn

    app = create_api_app()

    # Run the server
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")

    return "API server started"


async def main():
    print("🚀 Starting web API service...")
    result = await run_api_server()
    print(f"Result: {result}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"An error occurred: {e}")

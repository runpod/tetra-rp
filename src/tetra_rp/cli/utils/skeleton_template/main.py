"""
Flash Application - Flash Server

This is the main entry point for your Flash application.
It runs a FastAPI server that coordinates with GPU and CPU workers.

Each APIRouter is discovered as a handler during build and can be deployed
as a separate serverless endpoint (queue-based or load-balancer based).
"""
import os
import logging
from fastapi import FastAPI

from workers.example import example_worker_router
from workers.interface import example_interface_router


log = logging.getLogger(__name__)


# Create FastAPI app
app = FastAPI(title="Flash Application")


@app.get("/")
def home():
    """Root endpoint."""
    return {"status": "ok", "message": "Flash application running"}


@app.get("/ping")
def ping():
    """Health check endpoint."""
    return {"healthy": True}


# Include worker routers
# Each router is discovered as a handler during build
app.include_router(example_worker_router, prefix="/example", tags=["workers"])
app.include_router(example_interface_router, prefix="/interface", tags=["workers"])


# Run the app when the script is executed
if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 80))
    logger.info(f"Starting Flash server on port {port}")

    # Start the server
    uvicorn.run(app, host="0.0.0.0", port=port)

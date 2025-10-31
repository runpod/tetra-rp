"""
Flash Application - Flash Server

This is the main entry point for your Flash application.
It runs a FastAPI server that coordinates GPU workers.
"""

import asyncio
from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv

from workers import ExampleWorker

# Load environment variables
load_dotenv()

# Create FastAPI app
app = FastAPI(title="Flash Application")


class ProcessRequest(BaseModel):
    """Request model for processing endpoint."""
    data: str


@app.get("/")
def home():
    """Health check endpoint."""
    return {"status": "ok", "message": "Flash application running"}


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"healthy": True}


@app.post("/process")
async def process(request: ProcessRequest):
    """
    Process data using GPU worker.

    Example request:
    {
        "data": "test input"
    }
    """
    # Instantiate worker
    worker = ExampleWorker()

    # Call worker's process method
    result = await worker.process({"input": request.data})

    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8888)

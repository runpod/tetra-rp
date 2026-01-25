import logging
import os

from fastapi import FastAPI

from workers.cpu import cpu_router
from workers.gpu import gpu_router

logger = logging.getLogger(__name__)


app = FastAPI(
    title="Flash Application",
    description="Distributed GPU and CPU computing with Runpod Flash",
    version="0.1.0",
)

# Include routers
app.include_router(gpu_router, prefix="/gpu", tags=["GPU Workers"])
app.include_router(cpu_router, prefix="/cpu", tags=["CPU Workers"])


@app.get("/")
def home():
    return {
        "message": "Flash Application",
        "docs": "/docs",
        "endpoints": {"gpu_hello": "/gpu/hello", "cpu_hello": "/cpu/hello"},
    }


@app.get("/ping")
def ping():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("FLASH_HOST", "localhost")
    port = int(os.getenv("FLASH_PORT", 8888))
    logger.info(f"Starting Flash server on {host}:{port}")

    uvicorn.run(app, host=host, port=port)

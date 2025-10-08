"""FastAPI application with example endpoints."""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


def create_api_app() -> FastAPI:
    """Create and configure FastAPI application."""

    app = FastAPI(
        title="Tetra API Service",
        description="Example web API deployed with Tetra",
        version="1.0.0",
    )

    # Example models
    class ComputeRequest(BaseModel):
        operation: str
        values: list[float]

    class ComputeResponse(BaseModel):
        result: float
        operation: str
        input_count: int

    @app.get("/")
    async def root():
        """Root endpoint."""
        return {"message": "Tetra API Service", "status": "running"}

    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy", "service": "tetra-rp-api"}

    @app.post("/compute", response_model=ComputeResponse)
    async def compute(request: ComputeRequest):
        """Perform computation on provided values."""

        if not request.values:
            raise HTTPException(status_code=400, detail="No values provided")

        try:
            if request.operation == "sum":
                result = sum(request.values)
            elif request.operation == "mean":
                result = sum(request.values) / len(request.values)
            elif request.operation == "max":
                result = max(request.values)
            elif request.operation == "min":
                result = min(request.values)
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported operation: {request.operation}",
                )

            return ComputeResponse(
                result=result,
                operation=request.operation,
                input_count=len(request.values),
            )

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return app

"""Generator for mothership handler that serves main.py FastAPI app."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

MOTHERSHIP_HANDLER_TEMPLATE = '''"""Auto-generated handler for mothership endpoint."""

import os
from fastapi.middleware.cors import CORSMiddleware
from {main_module} import {app_variable} as app

# Add CORS middleware for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mothership endpoint information (set by RunPod when deployed)
MOTHERSHIP_ID = os.getenv("RUNPOD_ENDPOINT_ID")
MOTHERSHIP_URL = os.getenv("RUNPOD_ENDPOINT_URL")


@app.get("/ping")
async def ping():
    """Health check endpoint required by RunPod."""
    return {{"status": "healthy", "endpoint": "mothership", "id": MOTHERSHIP_ID}}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
'''


def generate_mothership_handler(
    main_file: str,
    app_variable: str,
    output_path: Path,
) -> None:
    """Generate handler that imports and serves user's main.py FastAPI app.

    Args:
        main_file: Filename of main.py (e.g., "main.py")
        app_variable: Name of the FastAPI app variable (e.g., "app")
        output_path: Path where to write the generated handler file

    Raises:
        ValueError: If parameters are invalid
    """
    if not main_file or not main_file.endswith(".py"):
        raise ValueError(f"Invalid main_file: {main_file}")

    if not app_variable or not app_variable.isidentifier():
        raise ValueError(f"Invalid app_variable: {app_variable}")

    # Convert filename to module name (e.g., "main.py" -> "main")
    main_module = main_file.replace(".py", "")

    # Generate handler code
    handler_code = MOTHERSHIP_HANDLER_TEMPLATE.format(
        main_module=main_module,
        app_variable=app_variable,
    )

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write handler file
    output_path.write_text(handler_code)
    logger.info(f"Generated mothership handler: {output_path}")

"""Project skeleton creation utilities."""

from pathlib import Path
from typing import List

# Template files content
MAIN_PY_TEMPLATE = '''"""
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
'''

WORKER_EXAMPLE_PY_TEMPLATE = '''"""
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
'''

WORKERS_INIT_PY_TEMPLATE = '''"""GPU Workers package."""

from .example_worker import ExampleWorker

__all__ = ["ExampleWorker"]
'''

ENV_EXAMPLE_TEMPLATE = """# RunPod API Configuration
RUNPOD_API_KEY=your_runpod_api_key_here

# Development settings
DEBUG=false
LOG_LEVEL=INFO
"""

REQUIREMENTS_TXT_TEMPLATE = """# Core dependencies for Flash
tetra-rp>=0.12.0
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
python-dotenv>=1.0.0
pydantic>=2.0.0
aiohttp>=3.9.0
"""

GITIGNORE_TEMPLATE = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Environment
.env
.venv

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# Tetra
.tetra/

# OS
.DS_Store
Thumbs.db
"""

FLASHIGNORE_TEMPLATE = """# Flash build ignores
# Similar to .gitignore but specifically for flash build command

# Version control
.git/
.gitignore

# Python artifacts
__pycache__/
*.pyc
*.pyo
*.pyd
.Python

# Virtual environments
.env
.venv/
env/
venv/
ENV/

# Build artifacts
.build/
.tetra/
*.tar.gz
*.egg-info/
dist/
build/

# IDE files
.vscode/
.idea/
*.swp
*.swo
*~

# OS files
.DS_Store
Thumbs.db

# Test files
tests/
test_*.py
*_test.py

# Documentation (optional - comment out to include)
# docs/
# *.md

# Logs
*.log
"""

README_TEMPLATE = """# {{project_name}}

Flash application with Flash Server and GPU workers.

## Setup

1. Activate the conda environment:
```bash
conda activate {{project_name}}
```

2. Configure your RunPod API key:
```bash
cp .env.example .env
# Edit .env and add your RUNPOD_API_KEY
```

3. Run the development server:
```bash
flash run
```

## Project Structure

```
{{project_name}}/
├── main.py              # Flash Server (FastAPI)
├── workers/             # GPU workers
│   ├── __init__.py
│   └── example_worker.py
├── .env.example         # Environment variables template
├── requirements.txt     # Python dependencies
└── README.md           # This file
```

## Development

The Flash Server runs on `localhost:8888` and coordinates GPU workers.

### Adding New Workers

1. Create a new file in `workers/` directory
2. Define a class with `@remote` decorator
3. Import it in `workers/__init__.py`
4. Use it in `main.py`

Example:
```python
from tetra_rp import remote, LiveServerless

config = LiveServerless(name="my_worker", workersMax=3)

@remote(config)
class MyWorker:
    def process(self, data):
        return {{"result": f"Processed: {{data}}"}}
```

## Deployment

Deploy to production:
```bash
flash deploy send production
```

## Documentation

- [Flash CLI Docs](./docs/)
- [Tetra Documentation](https://docs.tetra.dev)
"""


def create_project_skeleton(project_dir: Path, force: bool = False) -> List[str]:
    """
    Create Flash project skeleton.

    Args:
        project_dir: Project directory path
        force: Overwrite existing files

    Returns:
        List of created file paths
    """
    created_files = []

    # Define project structure
    files_to_create = {
        "main.py": MAIN_PY_TEMPLATE,
        "workers/__init__.py": WORKERS_INIT_PY_TEMPLATE,
        "workers/example_worker.py": WORKER_EXAMPLE_PY_TEMPLATE,
        ".env.example": ENV_EXAMPLE_TEMPLATE,
        "requirements.txt": REQUIREMENTS_TXT_TEMPLATE,
        ".gitignore": GITIGNORE_TEMPLATE,
        ".flashignore": FLASHIGNORE_TEMPLATE,
        "README.md": README_TEMPLATE.format(project_name=project_dir.name),
    }

    # Create files
    for relative_path, content in files_to_create.items():
        file_path = project_dir / relative_path

        # Create parent directories if needed
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Skip existing files unless force is True
        if file_path.exists() and not force:
            continue

        # Write file
        file_path.write_text(content)
        created_files.append(str(file_path.relative_to(project_dir)))

    return created_files

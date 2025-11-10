# {{project_name}}

A Flash application for distributed inference and serving on Runpod's serverless infrastructure.

## Quick Start (60 seconds)

### 1. Install Dependencies

**Using pip:**
```bash
pip install -r requirements.txt
```

**Using uv (faster):**
```bash
uv pip install -r requirements.txt
```

**Using conda (if environment was created):**
```bash
conda activate {{project_name}}
pip install -r requirements.txt
```

### 2. Configure Environment

Add your Runpod API key to `.env`:

```bash
RUNPOD_API_KEY=your_api_key_here
```

Get your API key from [Runpod Settings](https://www.runpod.io/console/user/settings).

### 3. Run Locally

```bash
flash run
```

The server starts at **http://localhost:8000**

### 4. Test the API

```bash
# Health check
curl http://localhost:8000/ping

# Test GPU worker endpoint
curl -X POST http://localhost:8000/example/ \
  -H "Content-Type: application/json" \
  -d '{"data": "example task"}'

# Test CPU interface endpoint
curl http://localhost:8000/interface/list
```

Test using the OpenAPI (Swagger) UI at **http://localhost:8000/docs**

## Understanding the Architecture

Flash applications consist of three components:

### 1. **Flash Server** (`main.py`)
- FastAPI application that coordinates all workers
- Runs locally during development
- Serves as the entry point for all API requests

### 2. **GPU Workers** (`workers/example/`)
- **Queue-based handlers** for GPU-intensive tasks
- Each request is queued and processed by available workers
- Auto-scales based on queue depth
- Best for: ML inference, image processing, video encoding

Example configuration:
```python
from tetra_rp import remote, LiveServerless, GpuGroup

config = LiveServerless(
    name="example_worker",
    gpus=[GpuGroup.ADA_24],  # RTX 4090
    workersMin=0,      # Scale to zero when idle
    workersMax=3       # Max concurrent workers
)

@remote(config)
class ExampleWorker:
    def process(self, input_data: dict) -> dict:
        # Your GPU processing logic here
        return {"result": "processed"}
```

### 3. **CPU Interfaces** (`workers/interface/`)
- **Load-balancer handlers** for CPU-based API endpoints
- Direct HTTP requests, no queue
- Lower latency, better for APIs
- Best for: REST APIs, data transformations, business logic

Example configuration:
```python
from tetra_rp import remote, CpuLiveServerless, CpuInstanceType

config = CpuLiveServerless(
    name="interface_worker",
    instanceIds=[CpuInstanceType.CPU3G_2_8],  # 2 vCPU, 8GB RAM
    workersMin=0,
    workersMax=5
)

@remote(config)
def todo_get_list():
    return {"items": [...]}
```

## Project Structure

```
{{project_name}}/
├── main.py                 # FastAPI application entry point
├── workers/
│   ├── example/           # GPU worker (queue-based)
│   │   ├── __init__.py    # FastAPI router
│   │   └── endpoint.py    # Worker implementation with @remote decorator
│   └── interface/         # CPU interface (load-balancer)
│       ├── __init__.py    # FastAPI router
│       └── endpoint.py    # Functions with @remote decorator
├── .env                   # Environment variables (RUNPOD_API_KEY)
├── .flashignore          # Files to exclude from build
├── requirements.txt       # Python dependencies
└── README.md             # This file
```

## Deployment

### Build and Deploy

```bash
# Build the application (discovers all handlers)
flash build

# Create deployment environment
flash deploy new production

# Deploy to Runpod serverless
flash deploy send production

# Check deployment status and get endpoint URLs
flash deploy report production
```

### What Happens During Build?

1. **Handler Discovery**: Flash scans your code for `@remote` decorators
2. **Classification**: Determines if handler is queue-based (GPU) or load-balancer (CPU)
3. **Resource Configuration**: Creates endpoint configuration for each handler
4. **Packaging**: Bundles code and dependencies for deployment

### Monitor Deployments

```bash
# View all deployed resources
flash report

# Check specific environment
flash deploy report production

# View logs in Runpod Console
# Links are shown in the report output
```

## API Reference

### Health Endpoints

#### `GET /`
Root endpoint returning application status.

**Response:**
```json
{
  "status": "ok",
  "message": "Flash application running"
}
```

#### `GET /ping`
Health check endpoint.

**Response:**
```json
{
  "healthy": true
}
```

### Example GPU Worker

#### `POST /example/`
Queue-based GPU processing endpoint.

**Request:**
```json
{
  "data": "example task"
}
```

**Response:**
```json
{
  "status": "success",
  "input": {"input": "example task"},
  "output": "Processed: {'input': 'example task'}"
}
```

### Example CPU Interface

#### `GET /interface/list`
Get list of todo items.

**Response:**
```json
{
  "item_1": "Make a list",
  "item_2": "Show a list",
  "item_3": "Delete a list"
}
```

#### `POST /interface/add`
Add a new todo item.

**Request:**
```json
{
  "data": "New task"
}
```

**Response:**
```json
{
  "result": "added item: New task"
}
```

#### `POST /interface/delete`
Delete a todo item.

**Request:**
```json
{
  "data": "Old task"
}
```

**Response:**
```json
{
  "result": "deleted item: Old task"
}
```

## Configuration

### Environment Variables (`.env`)

```bash
# Required: Runpod API Key
RUNPOD_API_KEY=your_api_key_here

# Optional: Server port (default: 80)
PORT=8000

# Optional: Log level (default: INFO)
LOG_LEVEL=DEBUG
```

### GPU Worker Configuration

```python
from tetra_rp import LiveServerless, GpuGroup

config = LiveServerless(
    name="my_worker",
    gpus=[GpuGroup.ADA_24],          # GPU type
    gpuCount=1,                      # GPUs per worker
    workersMin=0,                    # Minimum workers (0 = scale to zero)
    workersMax=3,                    # Maximum workers
    idleTimeout=5,                   # Minutes before scaling down
    env={"MODEL_PATH": "/models"}   # Environment variables
)
```

**Available GPU Types:**
- `GpuGroup.ADA_24` - NVIDIA GeForce RTX 4090 (24GB)
- `GpuGroup.ADA_48_PRO` - NVIDIA RTX 6000 Ada, L40, L40S (48GB)
- `GpuGroup.ADA_80_PRO` - NVIDIA H100 PCIe, H100 80GB HBM3 (80GB)
- `GpuGroup.AMPERE_24` - NVIDIA RTX A5000, L4, GeForce RTX 3090 (24GB)
- `GpuGroup.AMPERE_48` - NVIDIA A40, RTX A6000 (48GB)
- `GpuGroup.AMPERE_80` - NVIDIA A100 80GB PCIe, A100-SXM4-80GB (80GB)
- `GpuGroup.HOPPER_141` - NVIDIA H200 (141GB)

### CPU Interface Configuration

```python
from tetra_rp import CpuLiveServerless, CpuInstanceType

config = CpuLiveServerless(
    name="my_interface",
    instanceIds=[CpuInstanceType.CPU3G_2_8],  # 2 vCPU, 8GB RAM
    workersMin=0,
    workersMax=5,
    idleTimeout=5,
    env={"API_TIMEOUT": "30"}
)
```

**Available CPU Types:**
- `CPU3G_1_4` - 1 vCPU, 4GB RAM (3rd Gen General Purpose)
- `CPU3G_2_8` - 2 vCPU, 8GB RAM (3rd Gen General Purpose)
- `CPU3G_4_16` - 4 vCPU, 16GB RAM (3rd Gen General Purpose)
- `CPU3G_8_32` - 8 vCPU, 32GB RAM (3rd Gen General Purpose)
- `CPU3C_1_2` - 1 vCPU, 2GB RAM (3rd Gen Compute-Optimized)
- `CPU3C_2_4` - 2 vCPU, 4GB RAM (3rd Gen Compute-Optimized)
- `CPU3C_4_8` - 4 vCPU, 8GB RAM (3rd Gen Compute-Optimized)
- `CPU3C_8_16` - 8 vCPU, 16GB RAM (3rd Gen Compute-Optimized)
- `CPU5C_1_2` - 1 vCPU, 2GB RAM (5th Gen Compute-Optimized)
- `CPU5C_2_4` - 2 vCPU, 4GB RAM (5th Gen Compute-Optimized)
- `CPU5C_4_8` - 4 vCPU, 8GB RAM (5th Gen Compute-Optimized)
- `CPU5C_8_16` - 8 vCPU, 16GB RAM (5th Gen Compute-Optimized)

## Adding New Workers

### Add a GPU Worker

1. Create new directory in `workers/`:
```bash
mkdir -p workers/my_gpu_worker
```

2. Create `endpoint.py`:
```python
from tetra_rp import remote, LiveServerless

config = LiveServerless(name="my_gpu_worker")

@remote(config)
class MyWorker:
    def __init__(self):
        # Load models, initialize resources
        pass

    def process(self, data: dict) -> dict:
        # Your GPU processing logic
        return {"result": "processed"}
```

3. Create `__init__.py`:
```python
from fastapi import APIRouter
from .endpoint import MyWorker

router = APIRouter()

@router.post("/process")
async def process(data: dict):
    worker = MyWorker()
    return await worker.process(data)
```

4. Register in `main.py`:
```python
from workers.my_gpu_worker import router as my_gpu_router
app.include_router(my_gpu_router, prefix="/my_gpu_worker", tags=["workers"])
```

### Add a CPU Interface

1. Create new directory in `workers/`:
```bash
mkdir -p workers/my_api
```

2. Create `endpoint.py`:
```python
from tetra_rp import remote, CpuLiveServerless

config = CpuLiveServerless(name="my_api")

@remote(config)
def get_data(id: str):
    return {"id": id, "data": "..."}

@remote(config)
def process_data(data: dict):
    return {"processed": data}
```

3. Create `__init__.py`:
```python
from fastapi import APIRouter
from .endpoint import get_data, process_data

router = APIRouter()

@router.get("/data/{id}")
async def get_data_endpoint(id: str):
    return await get_data(id)

@router.post("/process")
async def process_endpoint(data: dict):
    return await process_data(data)
```

4. Register in `main.py`:
```python
from workers.my_api import router as my_api_router
app.include_router(my_api_router, prefix="/my_api", tags=["api"])
```

## Common Patterns

### Pattern 1: ML Model Inference (GPU)

```python
from tetra_rp import remote, LiveServerless, GpuGroup

config = LiveServerless(
    name="model_inference",
    gpus=[GpuGroup.ADA_24],
    workersMax=3
)

@remote(config)
class ModelInference:
    def __init__(self):
        # Imports must be inside the function/class
        import torch
        from transformers import AutoModel

        self.model = AutoModel.from_pretrained("model-name")
        self.model.cuda()

    def predict(self, text: str) -> dict:
        import torch

        with torch.no_grad():
            result = self.model(text)

        return {"prediction": result}
```

### Pattern 2: API Gateway (CPU)

```python
from tetra_rp import remote, CpuLiveServerless, CpuInstanceType

config = CpuLiveServerless(
    name="api_gateway",
    instanceIds=[CpuInstanceType.CPU5C_4_8],  # Compute optimized
    workersMax=10
)

@remote(config)
def fetch_user(user_id: str):
    # Call external APIs, databases, etc.
    import requests
    response = requests.get(f"https://api.example.com/users/{user_id}")
    return response.json()

@remote(config)
def process_webhook(data: dict):
    # Process webhook events
    return {"status": "processed", "data": data}
```

### Pattern 3: Batch Processing (GPU)

```python
from tetra_rp import remote, LiveServerless, GpuGroup

config = LiveServerless(
    name="batch_processor",
    gpus=[GpuGroup.AMPERE_80],
    gpuCount=2,  # Multi-GPU
    workersMax=5
)

@remote(config)
class BatchProcessor:
    def process_batch(self, items: list[dict]) -> list[dict]:
        import torch

        results = []
        for item in items:
            # Process each item
            result = self.process_single(item)
            results.append(result)

        return results
```

## Troubleshooting

### Local Development

**Issue: `ModuleNotFoundError` when running `flash run`**
```bash
# Solution: Install dependencies
pip install -r requirements.txt
```

**Issue: Port already in use**
```bash
# Solution: Change port in .env
PORT=8001

# Or kill the process using port 8000
lsof -ti:8000 | xargs kill -9
```

**Issue: API key not found**
```bash
# Solution: Make sure .env file exists with RUNPOD_API_KEY
cp .env.example .env
# Edit .env and add your API key
```

### Deployment Issues

**Issue: Build fails with import errors**
```bash
# Solution: Add missing dependencies to requirements.txt
# Then rebuild:
flash build
```

**Issue: Handler not discovered during build**
```bash
# Solution: Make sure you're using @remote decorator
# And the function/class is imported in __init__.py
```

**Issue: Deployment stuck or failing**
```bash
# Solution: Check logs in Runpod console
# Get console link from:
flash deploy report production
```

**Issue: Worker not scaling**
```bash
# Solution: Check worker configuration
# Make sure workersMax > 0
# Check idleTimeout isn't too aggressive
```

### Performance Issues

**Issue: High latency on GPU workers**
```bash
# Queue-based handlers have higher latency
# Solution: Consider using CPU interface if no GPU needed
# Or increase workersMin to keep workers warm
```

**Issue: Cold starts are slow**
```bash
# Solution: Set workersMin > 0 to keep workers running
# Or optimize model loading in __init__
```

## Available Commands

| Command | Description |
|---------|-------------|
| `flash run` | Start local development server |
| `flash build` | Build application for deployment |
| `flash deploy new <name>` | Create deployment environment |
| `flash deploy send <name>` | Deploy to environment |
| `flash deploy report <name>` | View environment status and URLs |
| `flash deploy list` | List all environments |
| `flash report` | Show all deployed resources |
| `flash clean` | Remove all deployed resources |

## Learn More

- **Runpod Console**: [https://www.runpod.io/console](https://www.runpod.io/console)
- **Runpod Documentation**: [https://docs.runpod.io](https://docs.runpod.io)
- **Get API Key**: [https://www.runpod.io/console/user/settings](https://www.runpod.io/console/user/settings)

## Support

- **Issues**: Report bugs at [GitHub Issues](https://github.com/runpod/flash/issues)
- **Discord**: Join the [Runpod Discord](https://discord.gg/runpod)
- **Email**: support@runpod.io

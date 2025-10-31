# {project_name}

Flash application with Flash Server and GPU workers.

## Setup

1. Activate the conda environment:
```bash
conda activate {project_name}
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
{project_name}/
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
        return {"result": f"Processed: {data}"}
```

## Deployment

Deploy to production:
```bash
flash deploy send production
```

## Documentation

- [Flash CLI Docs](./docs/)
- [Tetra Documentation](https://docs.tetra.dev)

# Flash CLI Documentation

Command-line interface for Flash - distributed inference and serving framework.

## Quick Start

```bash
# Create new project
flash init my-project

# Navigate to project
cd my-project

# Setup environment
conda activate my-project
cp .env.example .env  # Add RUNPOD_API_KEY

# Run development server
flash run
```

## Commands

### flash init

Create a new Flash project.

```bash
flash init PROJECT_NAME [OPTIONS]
```

**Options:**
- `--no-env`: Skip conda environment creation
- `--force, -f`: Overwrite existing directory

**Example:**
```bash
flash init my-project
flash init my-project --no-env
```

[Full documentation](./flash-init.md)

---

### flash run

Run Flash development server.

```bash
flash run [OPTIONS]
```

**Options:**
- `--host`: Host to bind to (default: localhost)
- `--port, -p`: Port to bind to (default: 8888)
- `--reload/--no-reload`: Enable auto-reload (default: enabled)

**Example:**
```bash
flash run
flash run --port 3000
```

[Full documentation](./flash-run.md)

---

## Project Structure

```
my-project/
├── main.py              # Flash Server (FastAPI)
├── workers/             # GPU workers
│   ├── __init__.py
│   └── example_worker.py
├── .env.example
├── requirements.txt
└── README.md
```

## Environment Variables

Required in `.env`:
```bash
RUNPOD_API_KEY=your_api_key_here
```

## Testing Your Server

```bash
# Health check
curl http://localhost:8888/

# Call GPU worker
curl -X POST http://localhost:8888/process \
  -H "Content-Type: application/json" \
  -d '{"data": "test input"}'
```

## Getting Help

```bash
flash --help
flash init --help
flash run --help
```

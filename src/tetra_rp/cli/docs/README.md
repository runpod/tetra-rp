# Flash CLI Documentation

Command-line interface for Flash - distributed inference and serving framework.

## Quick Start

```bash
# Create new project
flash init my-project

# Navigate to project
cd my-project

# Install dependencies
pip install -r requirements.txt

# Add your Runpod API key to .env
# RUNPOD_API_KEY=your_key_here

# Run development server
flash run
```

## Commands

### flash init

Create a new Flash project.

```bash
flash init [PROJECT_NAME] [OPTIONS]
```

**Options:**
- `--force, -f`: Overwrite existing files

**Examples:**
```bash
# Create new project
flash init my-project

# Initialize in current directory
flash init .

# Overwrite existing files
flash init my-project --force
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
├── workers/
│   ├── gpu/             # GPU worker
│   │   ├── __init__.py
│   │   └── endpoint.py
│   └── cpu/             # CPU worker
│       ├── __init__.py
│       └── endpoint.py
├── .env
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
curl http://localhost:8888/ping

# Call GPU worker
curl -X POST http://localhost:8888/gpu/hello \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello GPU!"}'

# Call CPU worker
curl -X POST http://localhost:8888/cpu/hello \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello CPU!"}'
```

## Getting Help

```bash
flash --help
flash init --help
flash run --help
```

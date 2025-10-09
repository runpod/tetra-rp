# flash run

Run Flash development server.

## Usage

```bash
flash run [OPTIONS]
```

## Options

- `--host`: Host to bind to (default: localhost)
- `--port, -p`: Port to bind to (default: 8888)
- `--reload/--no-reload`: Enable auto-reload (default: enabled)

## Examples

```bash
# Start server with defaults
flash run

# Custom port
flash run --port 3000

# Disable auto-reload
flash run --no-reload

# Custom host and port
flash run --host 0.0.0.0 --port 8000
```

## What It Does

1. Discovers `main.py` (or `app.py`, `server.py`)
2. Checks for FastAPI app
3. Starts uvicorn server with hot reload
4. GPU workers use LiveServerless (no packaging needed)

## Testing

```bash
# Health check
curl http://localhost:8888/

# Process endpoint (calls GPU worker)
curl -X POST http://localhost:8888/process \
  -H "Content-Type: application/json" \
  -d '{"data": "test input"}'
```

## Requirements

- `RUNPOD_API_KEY` in `.env` file

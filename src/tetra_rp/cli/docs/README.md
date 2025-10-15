# Flash CLI Documentation

Command-line interface for Flash - distributed inference and serving framework.

## Quick Start

```bash
# 1. Create new project
flash init my-project
cd my-project

# 2. Setup environment
conda activate my-project
cp .env.example .env  # Add your credentials

# 3. Local development
flash run

# 4. Production deployment
flash build --upload
flash deploy
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

### flash build

Build Flash project for production deployment.

```bash
flash build [OPTIONS]
```

**Options:**
- `--upload/--no-upload`: Upload to S3 (default: enabled)
- `--dir, -d`: Project directory
- `--name, -n`: Project name
- `--workers-only`: Build only GPU workers
- `--flash-server-only`: Build only Flash Server

**Example:**
```bash
flash build --upload
flash build --no-upload
flash build --workers-only
```

[Full documentation](./flash-build.md)

---

### flash deploy

Deploy Flash project to RunPod.

```bash
flash deploy [OPTIONS]
```

**Options:**
- `--dir, -d`: Project directory (default: current directory)

**Example:**
```bash
flash deploy
flash deploy --dir ./my-project
```

[Full documentation](./flash-deploy.md)

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

### For Local Development (`flash run`)
```bash
RUNPOD_API_KEY=your_api_key_here
```

### For Production Build (`flash build --upload`)
```bash
# S3/Volume Configuration
RUNPOD_S3_ENDPOINT=https://s3api-eu-ro-1.runpod.io
RUNPOD_S3_BUCKET=your-bucket-name
RUNPOD_VOLUME_ENDPOINT=https://s3api-eu-ro-1.runpod.io
RUNPOD_VOLUME_ACCESS_KEY=your_access_key
RUNPOD_VOLUME_SECRET_KEY=your_secret_key
RUNPOD_VOLUME_BUCKET=your-bucket-name

# Optional
TETRA_GPU_IMAGE=runpod/worker-tetra:latest
```

### For Production Deploy (`flash deploy`)
```bash
RUNPOD_API_KEY=your_api_key_here
RUNPOD_VOLUME_ENDPOINT=https://s3api-eu-ro-1.runpod.io
RUNPOD_VOLUME_ACCESS_KEY=your_access_key
RUNPOD_VOLUME_SECRET_KEY=your_secret_key
RUNPOD_VOLUME_BUCKET=your-bucket-name
TETRA_GPU_IMAGE=runpod/worker-tetra:latest
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
flash build --help
flash deploy --help
```

# flash init

Create a new Flash project with Flash Server and GPU workers.

## Usage

```bash
flash init PROJECT_NAME [OPTIONS]
```

## Arguments

- `PROJECT_NAME` (required): Name of the project directory to create

## Options

- `--no-env`: Skip conda environment creation
- `--force, -f`: Overwrite existing directory

## Examples

```bash
# Create project with conda environment
flash init my-project

# Create without conda environment
flash init my-project --no-env

# Overwrite existing directory
flash init my-project --force
```

## What It Creates

```
my-project/
├── main.py              # Flash Server (FastAPI)
├── workers/             # GPU workers
│   ├── __init__.py
│   └── example_worker.py
├── .env.example
├── requirements.txt
├── .gitignore
└── README.md
```

## Dependencies Installed

When conda environment is created:
- `fastapi>=0.104.0`
- `uvicorn[standard]>=0.24.0`
- `python-dotenv>=1.0.0`
- `pydantic>=2.0.0`
- `aiohttp>=3.9.0`
- `tetra-rp>=0.12.0`

## Next Steps

```bash
cd my-project
conda activate my-project  # if env created
cp .env.example .env       # add RUNPOD_API_KEY
flash run
```

# flash init

Create a new Flash project with Flash Server and GPU/CPU workers.

## Usage

```bash
flash init [PROJECT_NAME] [OPTIONS]
```

## Arguments

- `PROJECT_NAME` (optional): Name of the project directory to create
  - If omitted or `.`, initializes in current directory

## Options

- `--force, -f`: Overwrite existing files

## Examples

```bash
# Create new project directory
flash init my-project

# Initialize in current directory
flash init .

# Overwrite existing files
flash init my-project --force
```

## What It Creates

```
my-project/
├── main.py              # Flash Server (FastAPI)
├── workers/
│   ├── gpu/             # GPU worker example
│   │   ├── __init__.py
│   │   └── endpoint.py
│   └── cpu/             # CPU worker example
│       ├── __init__.py
│       └── endpoint.py
├── .env
├── requirements.txt
└── README.md
```

## Next Steps

```bash
cd my-project
pip install -r requirements.txt  # or use your preferred environment manager
# Add RUNPOD_API_KEY to .env
flash run
```

Visit http://localhost:8888/docs for interactive API documentation.

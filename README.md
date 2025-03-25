# Tetra

Tetra is a Python library for distributed inference and serving of machine learning models. It provides a flexible and efficient way to run inference across multiple machines.

## Prerequisites

- Python 3.9 or higher
- Poetry (for dependency management)
- Docker (optional, for containerized deployment)
- RunPod account and API key

## Installation

1. Clone the repository:

```bash
gh repo clone runpod/Tetra && cd Tetra
```

2. Install dependencies:

For core Tetra functionality only:

```bash
poetry install
```

For running examples (includes additional ML dependencies):

```bash
poetry install --with examples
```

## Quick Start

1. Set up your virtual environment:

```bash
poetry shell
```

2. Run an example:

```bash
python examples/example.py
```

## Project Structure

```
tetra/
├── tetra/          # Main package directory
├── protos/         # Protocol buffer definitions
├── examples/       # Example usage and demos
│   ├── example.py
│   └── image_gen.py
├── pyproject.toml  # Project dependencies and metadata
└── Dockerfile      # Container definition for deployment
```

## Examples

The `examples/` directory contains sample code demonstrating how to use Tetra:

- `example.py`: Basic usage example
- `image_gen.py`: Example of image generation using Tetra

## Development

To contribute to Tetra:

1. Create a virtual environment and install dependencies:

```bash
poetry install
```

2. Run tests:

```bash
poetry run pytest
```

## Docker Support

### Building the Docker Image

Build the Docker image:

```bash
docker build -t tetra .
```

### Running the Docker Container

Run the container with your RunPod API key:

```bash
docker run -it --env-file .env tetra
```

### Troubleshooting Docker Issues

If you encounter platform compatibility issues, you can try:

1. Specifying the platform explicitly:
   ```bash
   docker build --platform linux/amd64 -t tetra .
   ```

2. Running with platform specified:
   ```bash
   docker run --platform linux/amd64 -it --env-file .env tetra
   ```

3. For M1/M2 Mac users:
   - The PyTorch image is built for AMD64, but will run on ARM64 with emulation
   - You may see a warning about platform mismatch, but it should still work

## License

MIT

## Contributing

Contributions are welcome! 
Please feel free to submit a Pull Request.

## Support

For support, please [open an issue](https://github.com/runpod/Tetra/issues) on GitHub.

## Configuration

### Setting up RunPod API Key

The examples and many features of Tetra require a RunPod API key to function. To set this up:

1. Create a RunPod account at [runpod.io](https://www.runpod.io)
2. Go to your account settings and generate an API key
3. Create a `.env` file in the project root:

```bash
echo "RUNPOD_API_KEY=your_api_key_here" > .env
```

4. Replace `your_api_key_here` with your actual RunPod API key

If you see the error:

```text
Failed to provision resource: RunPod API key not provided in config or environment
```

This means either:

- The `.env` file is missing
- The API key is not set correctly in the `.env` file
- The `.env` file is not being loaded properly

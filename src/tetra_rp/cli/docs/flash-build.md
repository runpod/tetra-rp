# flash build

Build Flash project for production deployment.

## Usage

```bash
flash build [OPTIONS]
```

## Description

Packages your Flash Server and GPU workers for deployment to RunPod. Creates optimized build artifacts and uploads them to S3-compatible storage.

## Options

| Option | Description | Default |
|--------|-------------|---------|
| `--upload/--no-upload` | Upload build artifacts to S3 | `--upload` |
| `--dir, -d` | Project directory | Current directory |
| `--name, -n` | Project name | Auto-detected |
| `--workers-only` | Build only GPU workers | `False` |
| `--flash-server-only` | Build only Flash Server | `False` |

## Environment Variables

### Required (when using `--upload`)

```bash
RUNPOD_S3_ENDPOINT          # S3 endpoint URL
RUNPOD_S3_BUCKET            # S3 bucket name
RUNPOD_VOLUME_ENDPOINT      # Volume endpoint URL
RUNPOD_VOLUME_ACCESS_KEY    # S3 access key
RUNPOD_VOLUME_SECRET_KEY    # S3 secret key
RUNPOD_VOLUME_BUCKET        # Volume bucket name
```

### Optional

```bash
TETRA_GPU_IMAGE            # Custom GPU worker image
                           # Default: runpod/worker-tetra:latest
```

## Examples

### Basic Build

```bash
# Build and upload to S3
flash build --upload
```

### Build Locally

```bash
# Build without uploading
flash build --no-upload
```

### Build Specific Components

```bash
# Build only GPU workers
flash build --workers-only

# Build only Flash Server
flash build --flash-server-only
```

### Custom Project Directory

```bash
# Build from specific directory
flash build --dir ./my-project --upload
```

## Output

After a successful build, you'll see:

```
Preparing GPU workers...       ✓ 1 GPU worker(s) ready
Preparing Flash Server...      ✓ Flash Server ready

GPU Workers    1 (ExampleWorker)
Flash Server   ✓

Ready to deploy!
Run: flash deploy

╭─────────────────────────╮
│ ✓ Success               │
│ Build complete for test │
╰─────────────────────────╯
```

Build artifacts are saved to `.tetra/build_artifacts.json`.

## Next Steps

After building, deploy your project:

```bash
flash deploy
```

## Troubleshooting

### "No GPU workers found"

Make sure you have `@remote` decorated classes in your `workers/` directory:

```python
from tetra_rp import remote

@remote()
class MyWorker:
    def run(self, input_data):
        return {"result": input_data}
```

### "Volume not configured"

Set the required S3 environment variables in your `.env` file or use `--no-upload` for local builds.

## See Also

- [flash deploy](./flash-deploy.md)
- [flash init](./flash-init.md)

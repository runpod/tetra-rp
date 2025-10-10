# flash deploy

Deploy Flash project to RunPod production environment.

## Usage

```bash
flash deploy [OPTIONS]
```

## Description

Deploys your Flash Server as a CPU endpoint with Load Balancer. GPU workers automatically deploy on first request to `@remote` decorated endpoints.

## Prerequisites

### 1. Build Your Project

```bash
flash build --upload
```

### 2. Set Environment Variables

```bash
RUNPOD_API_KEY=your_api_key_here
RUNPOD_VOLUME_ENDPOINT=https://s3api-eu-ro-1.runpod.io
RUNPOD_VOLUME_ACCESS_KEY=your_access_key
RUNPOD_VOLUME_SECRET_KEY=your_secret_key
RUNPOD_VOLUME_BUCKET=your-bucket-name
```

## Options

| Option | Description | Default |
|--------|-------------|---------|
| `--dir, -d` | Project directory | Current directory |
| `--name, -n` | Project name | Auto-detected |

## Examples

### Basic Deployment

```bash
# Deploy to production
flash deploy
```

### Custom Project Directory

```bash
# Deploy from specific directory
flash deploy --dir ./my-project
```

## Output

After successful deployment:

```
Deploying to RunPod...        ✓ Deployed

╭──────────────────────────────────────╮
│ ✓ Live                               │
│ my-project deployed successfully!    │
│                                      │
│ URL: https://abc123.api.runpod.ai   │
╰──────────────────────────────────────╯

Test your endpoint:
curl https://abc123.api.runpod.ai/<your-endpoint>
```

## Testing Your Deployment

### Test Flash Server

```bash
# Health check
curl https://YOUR_ENDPOINT_ID.api.runpod.ai/health

# Call your FastAPI endpoint
curl https://YOUR_ENDPOINT_ID.api.runpod.ai/your-endpoint
```

### Test GPU Workers

GPU workers deploy automatically when you call a `@remote` endpoint:

```python
# In your FastAPI endpoint
result = await MyWorker.run.remote({"input": "data"})
```

First request will be slower (worker deployment), subsequent requests are fast.

## Managing Your Deployment

### View Deployment Status

```bash
# Check your endpoint in RunPod dashboard
# https://www.runpod.io/console/serverless
```

### Update Deployment

```bash
# Rebuild and redeploy
flash build --upload
flash deploy
```

### Environment Variables

Your Flash Server has access to all environment variables from your local `.env` file during deployment.

## Troubleshooting

### "No build artifacts found"

Run `flash build --upload` before deploying:

```bash
flash build --upload
flash deploy
```

### "API key not configured"

Set your RunPod API key:

```bash
export RUNPOD_API_KEY=your_api_key_here
```

### "Volume not configured"

Ensure all volume environment variables are set in your `.env` file.

### GPU Worker Not Starting

Check your `@remote` decorator:

```python
from tetra_rp import remote

@remote()
class MyWorker:
    def run(self, input_data):
        return {"result": input_data}
```

## See Also

- [flash build](./flash-build.md)
- [flash init](./flash-init.md)

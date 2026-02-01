# Migration Guide: tetra-rp → runpod-flash v0.23.1

## Overview

This document outlines the breaking changes when upgrading from tetra-rp to runpod-flash. The rename is clean and direct—there are no deprecated APIs or deprecation periods. Update your code to use the new names.

## Breaking Changes

### 1. Package Name

**Before:**
```bash
pip install tetra-rp
```

**After:**
```bash
pip install runpod-flash
```

Update your `requirements.txt` and `pyproject.toml` files.

### 2. Import Statements

All imports must change from `tetra_rp` to `runpod_flash`.

**Before:**
```python
from tetra_rp import remote, LiveServerless, CpuLiveServerless
from tetra_rp import LiveLoadBalancer, CpuLiveLoadBalancer
from tetra_rp.core.resources import Serverless, CpuServerlessEndpoint
from tetra_rp.config import get_paths
```

**After:**
```python
from runpod_flash import remote, LiveServerless, CpuLiveServerless
from runpod_flash import LiveLoadBalancer, CpuLiveLoadBalancer
from runpod_flash.core.resources import Serverless, CpuServerlessEndpoint
from runpod_flash.config import get_paths
```

Update all Python files containing imports from `tetra_rp`.

### 3. Environment Variables

All runtime configuration environment variables have been renamed.

| Old Name | New Name |
|----------|----------|
| `TETRA_CIRCUIT_BREAKER_ENABLED` | `FLASH_CIRCUIT_BREAKER_ENABLED` |
| `TETRA_CB_FAILURE_THRESHOLD` | `FLASH_CB_FAILURE_THRESHOLD` |
| `TETRA_CB_SUCCESS_THRESHOLD` | `FLASH_CB_SUCCESS_THRESHOLD` |
| `TETRA_CB_TIMEOUT_SECONDS` | `FLASH_CB_TIMEOUT_SECONDS` |
| `TETRA_LOAD_BALANCER_ENABLED` | `FLASH_LOAD_BALANCER_ENABLED` |
| `TETRA_LB_STRATEGY` | `FLASH_LB_STRATEGY` |
| `TETRA_RETRY_ENABLED` | `FLASH_RETRY_ENABLED` |
| `TETRA_RETRY_MAX_ATTEMPTS` | `FLASH_RETRY_MAX_ATTEMPTS` |
| `TETRA_RETRY_BASE_DELAY` | `FLASH_RETRY_BASE_DELAY` |
| `TETRA_METRICS_ENABLED` | `FLASH_METRICS_ENABLED` |
| `TETRA_IMAGE_TAG` | `FLASH_IMAGE_TAG` |
| `TETRA_GPU_IMAGE` | `FLASH_GPU_IMAGE` |
| `TETRA_CPU_IMAGE` | `FLASH_CPU_IMAGE` |
| `TETRA_LB_IMAGE` | `FLASH_LB_IMAGE` |
| `TETRA_CPU_LB_IMAGE` | `FLASH_CPU_LB_IMAGE` |

Update your `.env` files and deployment scripts.

### 4. Configuration Directory

The configuration and state directory has changed.

**Before:**
```bash
~/.tetra/
├── config.json
└── deployments.json
```

**After:**
```bash
~/.flash/
├── config.json
└── deployments.json
```

Migrate your existing deployments:
```bash
mkdir -p ~/.flash
cp ~/.tetra/config.json ~/.flash/
cp ~/.tetra/deployments.json ~/.flash/
```

### 5. Docker Images

Docker image names have changed for all runtime containers.

| Old Image | New Image |
|-----------|-----------|
| `runpod/tetra-rp:{tag}` | `runpod/flash:{tag}` |
| `runpod/tetra-rp-cpu:{tag}` | `runpod/flash-cpu:{tag}` |
| `runpod/tetra-rp-lb:{tag}` | `runpod/flash-lb:{tag}` |
| `runpod/tetra-rp-lb-cpu:{tag}` | `runpod/flash-lb-cpu:{tag}` |

These are automatically used by `LiveServerless` and `CpuLiveServerless` endpoints. You can override them with the environment variables listed above.

### 6. Metrics Namespace

The metrics namespace has changed.

**Before:**
```
tetra.metrics.*
```

**After:**
```
flash.metrics.*
```

Update any monitoring rules or dashboards that reference the old namespace.

## Migration Checklist

- [ ] Update package name in requirements.txt: `tetra-rp` → `runpod-flash`
- [ ] Update package name in pyproject.toml: `"tetra-rp"` → `"runpod-flash"`
- [ ] Search and replace all imports: `from tetra_rp` → `from runpod_flash`
- [ ] Search and replace all imports: `import tetra_rp` → `import runpod_flash`
- [ ] Update all `TETRA_*` environment variables to `FLASH_*`
- [ ] Update `.env` files with new variable names
- [ ] Migrate configuration: copy `~/.tetra/` to `~/.flash/`
- [ ] Update deployment scripts and CI/CD pipelines
- [ ] Test with `flash run` to verify local execution works
- [ ] Update any monitoring/alerting rules referencing `tetra.metrics`

## Running the Migration

### Step 1: Update Dependencies

```bash
# Update requirements.txt
sed -i 's/tetra-rp/runpod-flash/' requirements.txt
pip install -r requirements.txt

# Or update pyproject.toml
sed -i 's/"tetra-rp"/"runpod-flash"/' pyproject.toml
uv sync
```

### Step 2: Update Imports

```bash
# Update all Python files
find . -name "*.py" -type f -exec sed -i 's/from tetra_rp/from runpod_flash/g' {} \;
find . -name "*.py" -type f -exec sed -i 's/import tetra_rp/import runpod_flash/g' {} \;
```

### Step 3: Update Environment Variables

```bash
# Update .env file
sed -i 's/TETRA_/FLASH_/g' .env

# Update deployment configuration files
find . -name "*.json" -o -name "*.yaml" -o -name "*.yml" | xargs sed -i 's/TETRA_/FLASH_/g'
```

### Step 4: Migrate Configuration Directory

```bash
# Backup old configuration
cp -r ~/.tetra ~/.tetra.backup

# Create new directory
mkdir -p ~/.flash

# Copy existing configuration
cp ~/.tetra/config.json ~/.flash/
cp ~/.tetra/deployments.json ~/.flash/
```

### Step 5: Test

```bash
# Verify imports work
python -c "from runpod_flash import remote, LiveServerless; print('✓ Imports work')"

# Test local execution
flash run

# Check that endpoints are discovered correctly
```

## Troubleshooting

### ImportError: No module named 'tetra_rp'

This error means you haven't updated your imports yet.

```bash
# Find all Python files with tetra_rp imports
grep -r "from tetra_rp\|import tetra_rp" . --include="*.py"

# Update them
find . -name "*.py" -type f -exec sed -i 's/from tetra_rp/from runpod_flash/g' {} \;
find . -name "*.py" -type f -exec sed -i 's/import tetra_rp/import runpod_flash/g' {} \;
```

### Configuration not found

If you see "configuration not found" errors, ensure you've migrated the config directory:

```bash
mkdir -p ~/.flash
cp ~/.tetra/*.json ~/.flash/ 2>/dev/null || true
```

### Old environment variables not working

Double-check that you've updated all `TETRA_*` variables to `FLASH_*` in:
- `.env` files
- Deployment environment configurations
- Docker run commands
- Kubernetes manifests
- CI/CD pipeline variables

### Docker image pull failures

If you're using explicit Docker image names, update them from `runpod/tetra-rp*` to `runpod/flash*`.

## Getting Help

If you encounter migration issues:

1. Check the [runpod-flash documentation](./README.md)
2. Review [Flash SDK Reference](./docs/Flash_SDK_Reference.md)
3. Open an issue on [GitHub](https://github.com/runpod/runpod-python/issues)

## What's New in runpod-flash

Beyond the name change, runpod-flash v0.23.1 includes:

- Improved reliability configuration with circuit breakers
- Better load balancer support for distributed endpoints
- Enhanced metrics and observability
- Streamlined CLI with `flash` command
- Updated Docker images with latest dependencies

See the [CHANGELOG.md](./CHANGELOG.md) for full release notes.

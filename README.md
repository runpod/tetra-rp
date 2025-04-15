# Tetra: Serverless GPU Computing for AI Workloads


<p align="center">
  <b>Dynamic GPU provisioning for ML workloads with transparent execution</b>
</p>

<p align="center">
  <a href="#overview">Overview</a> •
  <a href="#installation">Installation</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#key-features">Key Features</a> •
  <a href="#examples">Examples</a> •
  <a href="#configuration">Configuration</a> •
  <a href="#troubleshooting">Troubleshooting</a>
</p>

---

## Overview

The Tetra-RunPod integration provides seamless access to on-demand GPU resources through RunPod's serverless platform. With a simple decorator-based API, you can execute functions on powerful GPUs without managing infrastructure, while Tetra handles all the complexity of provisioning, communication, and state management.

## Installation

```bash
git clone https://github.com/runpod/tetra-rp
cd tetra-rp 
poetry install
```

You'll need a RunPod API key to use this integration. Sign up at [RunPod.io](https://runpod.io) and generate an API key in your account settings. set it in ENV:
```bash
export RUNPOD_API_KEY=<YOUR_API_KEY>
```
## Quick Start

```python
import os
import asyncio
from tetra import remote, ServerlessResource

# Configure RunPod resource
runpod_config = ServerlessResource(
    gpuIds="any",
    workersMin=1, 
    workersMax=1,
    name="example-diffusion-server",
)

# Define a function to run on RunPod GPU
@remote(
    resource_config=runpod_config,
    resource_type="serverless",
    dependencies=["torch", "numpy"]
)
def gpu_compute(data):
    import torch
    import numpy as np
    
    # Convert to tensor and perform computation on GPU
    tensor = torch.tensor(data, device="cuda")
    result = tensor.sum().item()
    
    # Get GPU info
    gpu_info = torch.cuda.get_device_properties(0)
    
    return {
        "result": result,
        "gpu_name": gpu_info.name,
        "cuda_version": torch.version.cuda
    }

async def main():
    # Run the function on RunPod GPU
    result = await gpu_compute([1, 2, 3, 4, 5])
    print(f"Result: {result['result']}")
    print(f"Computed on: {result['gpu_name']} with CUDA {result['cuda_version']}")

if __name__ == "__main__":
    asyncio.run(main())
```

## Key Features

### Dynamic GPU Provisioning

Automatically provision GPUs on demand without any manual setup:

```python
@remote(
    resource_config=runpod_config,
    resource_type="serverless"
)
def my_gpu_function(data):
    # Runs on GPU when called
    return process(data)
```

### Automatic Dependency Management

Specify dependencies to be installed on the serverless endpoint:

```python
@remote(
    resource_config=runpod_config,
    resource_type="serverless",
    dependencies=["torch==2.0.1", "transformers", "diffusers"]
)
def generate_image(prompt):
    # Dependencies are automatically installed
    from diffusers import StableDiffusionPipeline
    # Generate image...
    return image
```

## Examples


### Multi-Stage ML Pipeline

```python
# Feature extraction on GPU
@remote(
    resource_config=runpod_config,
    resource_type="serverless",
    dependencies=["torch", "transformers"]
)
def extract_features(texts):
    import torch
    from transformers import AutoTokenizer, AutoModel
    
    # Load model
    tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased")
    model = AutoModel.from_pretrained("bert-base-uncased")
    model.to("cuda")
    
    # Process texts
    features = []
    for text in texts:
        inputs = tokenizer(text, return_tensors="pt").to("cuda")
        with torch.no_grad():
            outputs = model(**inputs)
        features.append(outputs.last_hidden_state[:, 0].cpu().numpy().tolist()[0])
    
    return features

# Classification on GPU
@remote(
    resource_config=runpod_config,
    resource_type="serverless",
    dependencies=["torch", "sklearn"]
)
def classify(features, labels=None):
    import torch
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    
    # Convert to numpy
    features = np.array(features)
    
    if labels is not None:
        # Training mode
        labels = np.array(labels)
        classifier = LogisticRegression()
        classifier.fit(features, labels)
        
        # Save model coefficients (can't pickle sklearn model easily)
        coefficients = {
            "coef": classifier.coef_.tolist(),
            "intercept": classifier.intercept_.tolist(),
            "classes": classifier.classes_.tolist()
        }
        
        return coefficients
    else:
        # Inference mode (assuming coefficients are passed as first element)
        coefficients = features[0]
        actual_features = features[1:]
        
        # Recreate classifier
        classifier = LogisticRegression()
        classifier.coef_ = np.array(coefficients["coef"])
        classifier.intercept_ = np.array(coefficients["intercept"])
        classifier.classes_ = np.array(coefficients["classes"])
        
        # Predict
        predictions = classifier.predict(actual_features)
        probabilities = classifier.predict_proba(actual_features)
        
        return {
            "predictions": predictions.tolist(),
            "probabilities": probabilities.tolist()
        }

# Complete pipeline
async def text_classification_pipeline(train_texts, train_labels, test_texts):
    # Extract features
    train_features = await extract_features(train_texts)
    test_features = await extract_features(test_texts)
    
    # Train classifier
    model = await classify(train_features, train_labels)
    
    # Predict
    predictions = await classify([model] + test_features)
    
    return predictions
```

## Configuration

### Configuration Parameters

| Parameter | Description | Default | Example Values |
|-----------|-------------|---------|---------------|
| `name` | Name for your endpoint | Required | "stable-diffusion-server" |
| `gpuIds` | Type of GPU to request | GpuGroups.ADA_24.value | GpuGroups.AMPERE_16.value, GpuGroups.ADA_80.value |
| `gpuCount` | Number of GPUs per worker | 1 | 1, 2, 4 |
| `workersMin` | Minimum number of workers | 0 | Set to 1 for persistence |
| `workersMax` | Maximum number of workers | 3 | Higher for more concurrency |
| `idleTimeout` | Minutes before scaling down | 5 | 10, 30, 60 |
| `env` | Environment variables | None | `{"HF_TOKEN": "xyz"}` |
| `networkVolumeId` | Persistent storage ID | None | "vol_abc123" |
| `executionTimeoutMs` | Max execution time (ms) | 0 (no limit) | 600000 (10 min) |
| `scalerType` | Scaling strategy | QUEUE_DELAY | NONE, QUEUE_SIZE |
| `scalerValue` | Scaling parameter value | 4 | 1-10 range typical |
| `locations` | Preferred datacenter locations | None | "us-east,eu-central" |

### RunPod Configuration Options

```python
runpod_config = ServerlessResource(
    gpuIds="any",
    workersMin=1,
    workersMax=1,
    name="example-diffusion-server",
   ...
)
```
---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.


---

<p align="center">
  <a href="https://github.com/yourusername/tetra">Tetra</a> •
  <a href="https://runpod.io">RunPod</a>
</p>

# Tetra: Serverless Computing for AI Workloads

<p align="center">
  <b>Dynamic GPU and CPU provisioning for ML workloads with transparent execution</b>
</p>

<p align="center">
  <a href="#overview">Overview</a> •
  <a href="#getting-started">Getting Started</a> •
  <a href="#key-features-and-concepts">Key Features and Concepts</a> •
  <a href="#how-tetra-works">How Tetra Works</a> •
  <a href="#common-use-cases">Common Use Cases</a> •
  <a href="#quick-start-example">Quick Start Example</a> •
  <a href="#examples">More Examples</a> •
  <a href="#configuration">Configuration</a> •
</p>

## Overview

Tetra is a Python SDK that streamlines the development and deployment of AI workflows on Runpod's Serverless infrastructure. It provides an abstraction layer that lets you define, execute, and monitor sophisticated AI pipelines using both GPU and CPU resources through nothing but Python code and your local terminal, eliminating the need to interact with the Runpod console GUI.

You can find a list of prebuilt Tetra examples at: [runpod/tetra-examples](https://github.com/runpod/tetra-examples).

-----

## Get Started

To get started with Tetra, you can follow this step-by-step tutorial to learn how to code remote workflows in both serial and parallel: [Get started with Tetra](https://runpod.notion.site/tetra-tutorial).

Alternatively, you can clone the Tetra examples repository to explore and run pre-built examples:

```bash
git clone https://github.com/runpod/tetra-examples.git
```

### Installation

```bash
pip install tetra_rp
```

You must also set up a [Runpod API key](https://docs.runpod.io/get-started/api-keys) to use this integration. You can sign up at [Runpod.io](https://runpod.io) and generate an API key from your account settings. Set this key as an environment variable or save it in a local `.env` file:

```bash
export RUNPOD_API_KEY=<YOUR_API_KEY>
```

-----

## Key Features and Concepts

Tetra offers several advantages and introduces core concepts that simplify AI workflow development:

  * **Simplified Workflow Development**: Define sophisticated AI pipelines in pure Python with minimal configuration, allowing you to concentrate on your logic rather than infrastructure complexities.
  * **Optimized Resource Utilization**: Specify hardware requirements directly at the function level. This gives you precise control over GPU and CPU allocation for each part of your pipeline.
  * **Seamless Deployment**: Tetra automatically manages the setup of Runpod Serverless infrastructure, including worker communication and data transfer between your local environment and remote workers.
  * **Reduced Development Overhead**: Avoid the time-consuming tasks of writing application code for each worker, building Docker containers, and managing individual endpoints.
  * **Intuitive Programming Model**: Utilize Python decorators to easily mark functions for remote execution on the Runpod infrastructure.

### Inline Resource Configuration

Tetra allows for granular hardware specification at the function level using the `LiveServerless` object. This enables detailed control over GPU/CPU allocation and worker scaling.

#### GPU Configuration
```python
from tetra_rp import LiveServerless, GpuGroup

# Configure a GPU endpoint
gpu_config = LiveServerless(
    gpus=[GpuGroup.ANY], # Use any available GPU (default: .ANY)
    workersMax=5, # Scales up to 5 workers (default: 3)
    name="parallel-processor", # Name of the endpoint that will be created or used
)

# Configure a GPU endpoint with custom Docker image (using ServerlessEndpoint)
from tetra_rp import ServerlessEndpoint

gpu_config_custom = ServerlessEndpoint(
    gpus=[GpuGroup.AMPERE_80], # Use A100 GPUs
    imageName="pytorch/pytorch:2.0.1-cuda11.7-cudnn8-runtime", # Custom GPU image
    name="custom-gpu-processor",
)
```

#### CPU Configuration
```python
from tetra_rp import LiveServerless, CpuInstanceType

# Configure a CPU endpoint
cpu_config = LiveServerless(
    instanceIds=[CpuInstanceType.CPU5C_8_16], # Use compute-optimized CPUs
    workersMax=1, # Scales up to 1 worker (default: 3)
    name="cpu-processor", # Name of the endpoint that will be created or used
)

# Configure a CPU endpoint with custom Docker image (using CpuServerlessEndpoint)
from tetra_rp import CpuServerlessEndpoint

cpu_config_custom = CpuServerlessEndpoint(
    imageName="python:3.11-slim", # Custom Docker image
    name="custom-cpu-processor",
)
```

Refer to the [Configuration Parameters](#configuration) section for a full list of available settings.

**Note**: `LiveServerless` uses fixed Docker images optimized for Tetra runtime and supports full remote code execution. `ServerlessEndpoint` and `CpuServerlessEndpoint` allow custom Docker images but **only support dict payload communication** - they cannot execute arbitrary Python functions remotely and are designed for traditional endpoint usage where you send structured payloads like `{"input": {...}}`.

### Dynamic Resource Provisioning

Tetra enables you to automatically provision GPUs or CPUs on demand without any manual setup:

#### GPU Functions
```python
@remote(
    resource_config=gpu_config,
)
def my_gpu_function(data):
    # Runs on GPU when called
    import torch
    tensor = torch.tensor(data).cuda()
    return tensor.sum().item()
```

#### CPU Functions
```python
@remote(
    resource_config=cpu_config,
)
def my_cpu_function(data):
    # Runs on CPU when called
    import pandas as pd
    df = pd.DataFrame(data)
    return df.describe().to_dict()
```

### Automatic Dependency Management

Specify necessary Python dependencies for remote workers directly within the `@remote` decorator. Tetra ensures these dependencies are installed in the execution environment.

```python
@remote(
    resource_config=gpu_config,
    dependencies=["torch==2.0.1", "transformers", "pillow"]
    # dependencies=["torch==2.0.1", "transformers", "diffusers"]

def model_inference(data):
    # Libraries are automatically installed
    from transformers import AutoModel #
    import torch #
    from PIL import Image #
    # ...
    return "inference_results"
```

Ensure that `import` statements for these dependencies are included *inside* any remote functions that require them.

-----

## How Tetra Works

When a Tetra workflow is executed, the following steps occur:

1.  The `@remote` decorator identifies functions that are designated for remote execution.
2.  Tetra analyzes the dependencies between these functions to determine the correct order of execution.
3.  For each remote function:
      * Tetra provisions the necessary endpoint and worker resources on Runpod.
      * Input data is serialized and transferred to the remote worker.
      * The function executes on the remote infrastructure.
      * Results are then returned to your local environment.
4.  Data flows between functions as defined by your local Python code.

-----

## Common Use Cases

Tetra is well-suited for a variety of AI and data processing tasks, including:

  * **Multi-modal AI pipelines**: Combine text, image, and audio models into unified workflows using GPU resources.
  * **Distributed model training**: Scale model training operations across multiple GPU workers.
  * **AI research experimentation**: Quickly prototype and test complex combinations of models.
  * **Production inference systems**: Deploy sophisticated, multi-stage inference pipelines for real-world applications.
  * **Data processing workflows**: Process large datasets efficiently using CPU workers for general computation and GPU workers for accelerated tasks.
  * **Hybrid GPU/CPU workflows**: Combine CPU preprocessing with GPU inference for optimal cost and performance.

-----

## Quick Start Examples

### GPU Example

```python
import asyncio
from tetra_rp import remote, LiveServerless

# Configure Runpod GPU resources
gpu_config = LiveServerless(name="example-gpu-server")

# Define a function to run on Runpod GPU
@remote(
    resource_config=gpu_config,
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

async def main_gpu_example():
    # Run the function on Runpod GPU
    result = await gpu_compute([1, 2, 3, 4, 5])
    print(f"Result: {result['result']}")
    print(f"Computed on: {result['gpu_name']} with CUDA {result['cuda_version']}")

if __name__ == "__main__":
    asyncio.run(main_gpu_example())
```

### CPU Example

```python
import asyncio
from tetra_rp import remote, LiveServerless, CpuInstanceType

# Configure Runpod CPU resources
cpu_config = LiveServerless(
    name="example-cpu-server",
    instanceIds=[CpuInstanceType.CPU3G_1_4, CpuInstanceType.CPU3C_1_2],
)

# Define a function to run on Runpod CPU
@remote(
    resource_config=cpu_config,
    dependencies=["pandas", "numpy"]
)
def cpu_data_processing(data):
    import pandas as pd
    import numpy as np
    import platform
    
    # Process data using CPU
    df = pd.DataFrame(data)
    
    return {
        "row_count": len(df),
        "column_count": len(df.columns) if not df.empty else 0,
        "mean_values": df.select_dtypes(include=[np.number]).mean().to_dict(),
        "system_info": platform.processor(),
        "platform": platform.platform()
    }

async def main_cpu_example():
    # Sample data
    sample_data = [
        {"name": "Alice", "age": 30, "score": 85},
        {"name": "Bob", "age": 25, "score": 92},
        {"name": "Charlie", "age": 35, "score": 78}
    ]
    
    # Run the function on Runpod CPU
    result = await cpu_data_processing(sample_data)
    print(f"Processed {result['row_count']} rows on {result['platform']}")
    print(f"Mean values: {result['mean_values']}")

if __name__ == "__main__":
    asyncio.run(main_cpu_example())
```

-----

## More Examples

You can find more examples in the [tetra-examples repository](https://github.com/runpod/tetra-examples).

You can also install the examples as a submodule:

```bash
git clone [https://github.com/runpod/tetra-examples.git](https://github.com/runpod/tetra-examples.git)

cd tetra-examples
python -m examples.example
python -m examples.image_gen
python -m examples.matrix_operations
```

### Multi-Stage ML Pipeline Example

```python
import os
import asyncio
from tetra_rp import remote, LiveServerless

# Configure Runpod resources
runpod_config = LiveServerless(name="multi-stage-pipeline-server")

# Feature extraction on GPU
@remote(
    resource_config=runpod_config,
    dependencies=["torch", "transformers"]
)
def extract_features(texts):
    import torch
    from transformers import AutoTokenizer, AutoModel
    
    tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased")
    model = AutoModel.from_pretrained("bert-base-uncased")
    model.to("cuda")
    
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
    dependencies=["torch", "sklearn"]
)
def classify(features, labels=None):
    import torch
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    
    features_np = np.array(features[1:] if labels is None and isinstance(features, list) and len(features)>0 and isinstance(features[0], dict) else features)
    
    if labels is not None:
        labels_np = np.array(labels)
        classifier = LogisticRegression()
        classifier.fit(features_np, labels_np)
        
        coefficients = {
            "coef": classifier.coef_.tolist(),
            "intercept": classifier.intercept_.tolist(),
            "classes": classifier.classes_.tolist()
        }
        return coefficients
    else:
        coefficients = features[0]
        
        classifier = LogisticRegression()
        classifier.coef_ = np.array(coefficients["coef"])
        classifier.intercept_ = np.array(coefficients["intercept"])
        classifier.classes_ = np.array(coefficients["classes"])
        
        # Predict
        predictions = classifier.predict(features_np)
        probabilities = classifier.predict_proba(features_np)
        
        return {
            "predictions": predictions.tolist(),
            "probabilities": probabilities.tolist()
        }

# Complete pipeline
async def text_classification_pipeline(train_texts, train_labels, test_texts):
    train_features = await extract_features(train_texts)
    test_features = await extract_features(test_texts)
    
    model_coeffs = await classify(train_features, train_labels)
    
    # For inference, pass model coefficients along with test features
    # The classify function expects a list where the first element is the model (coeffs)
    # and subsequent elements are features for prediction.
    predictions = await classify([model_coeffs] + test_features)
    
    return predictions
```

-----

## Configuration

### GPU Configuration Parameters

The following parameters can be used with `LiveServerless` (full remote code execution) and `ServerlessEndpoint` (dict payload only) to configure your Runpod GPU endpoints:

| Parameter          | Description                                     | Default       | Example Values                      |
|--------------------|-------------------------------------------------|---------------|-------------------------------------|
| `name`             | (Required) Name for your endpoint               | `""`          | `"stable-diffusion-server"`         |
| `gpus`             | GPU pool IDs that can be used by workers        | `[GpuGroup.ANY]` | `[GpuGroup.ADA_24]` for RTX 4090 |
| `gpuCount`         | Number of GPUs per worker                       | 1             | 1, 2, 4                             |
| `workersMin`       | Minimum number of workers                       | 0             | Set to 1 for persistence            |
| `workersMax`       | Maximum number of workers                       | 3             | Higher for more concurrency         |
| `idleTimeout`      | Minutes before scaling down                     | 5             | 10, 30, 60                          |
| `env`              | Environment variables                           | `None`        | `{"HF_TOKEN": "xyz"}`               |
| `networkVolumeId`  | Persistent storage ID                           | `None`        | `"vol_abc123"`                      |
| `executionTimeoutMs`| Max execution time (ms)                         | 0 (no limit)  | 600000 (10 min)                     |
| `scalerType`       | Scaling strategy                                | `QUEUE_DELAY` | `REQUEST_COUNT`                     |
| `scalerValue`      | Scaling parameter value                         | 4             | 1-10 range typical                  |
| `locations`        | Preferred datacenter locations                  | `None`        | `"us-east,eu-central"`              |
| `imageName`        | Custom Docker image (ServerlessEndpoint only)   | Fixed for LiveServerless | `"pytorch/pytorch:latest"`, `"my-registry/custom:v1.0"` |

### CPU Configuration Parameters

The same GPU Configuration parameters above still apply to `LiveServerless` (full remote code execution) and `CpuServerlessEndpoint` (dict payload only), with the additional parameters:

| Parameter          | Description                                     | Default       | Example Values                      |
|--------------------|-------------------------------------------------|---------------|-------------------------------------|
| `instanceIds`      | CPU Instance Types (forces a CPU Endpoint type) | `None`        | `[CpuInstanceType.CPU5C_2_4]`       |
| `imageName`        | Custom Docker image (CpuServerlessEndpoint only) | Fixed for LiveServerless | `"python:3.11-slim"`, `"my-registry/custom:v1.0"` |

### Resource Class Comparison

| Feature | LiveServerless | ServerlessEndpoint | CpuServerlessEndpoint |
|---------|----------------|-------------------|----------------------|
| **Remote Code Execution** | ✅ Full Python function execution | ❌ Dict payloads only | ❌ Dict payloads only |
| **Custom Docker Images** | ❌ Fixed optimized images | ✅ Any Docker image | ✅ Any Docker image |
| **Use Case** | Dynamic remote functions | Traditional API endpoints | Traditional CPU endpoints |
| **Function Returns** | Any Python object | Dict only | Dict only |
| **@remote decorator** | Full functionality | Limited to payload passing | Limited to payload passing |

### Available GPU Types

Some common GPU groups available through `GpuGroup`:

- `GpuGroup.ADA_24` - NVIDIA GeForce RTX 4090
- `GpuGroup.AMPERE_80` - NVIDIA A100 80GB
- `GpuGroup.AMPERE_48` - NVIDIA A40, RTX A6000
- `GpuGroup.AMPERE_24` - NVIDIA RTX A5000, L4, RTX 3090
- `GpuGroup.ANY` - Any available GPU (default)

### Available CPU Instance Types
- `CpuInstanceType.CPU3G_1_4` - (cpu3g-1-4) 3rd gen general purpose, 1 vCPU, 4GB RAM
- `CpuInstanceType.CPU3G_2_8` - (cpu3g-2-8) 3rd gen general purpose, 2 vCPU, 8GB RAM
- `CpuInstanceType.CPU3G_4_16` - (cpu3g-4-16) 3rd gen general purpose, 4 vCPU, 16GB RAM
- `CpuInstanceType.CPU3G_8_32` - (cpu3g-8-32) 3rd gen general purpose, 8 vCPU, 32GB RAM
- `CpuInstanceType.CPU3C_1_2` - (cpu3c-1-2) 3rd gen compute-optimized, 1 vCPU, 2GB RAM
- `CpuInstanceType.CPU3C_2_4` - (cpu3c-2-4) 3rd gen compute-optimized, 2 vCPU, 4GB RAM
- `CpuInstanceType.CPU3C_4_8` - (cpu3c-4-8) 3rd gen compute-optimized, 4 vCPU, 8GB RAM
- `CpuInstanceType.CPU3C_8_16` - (cpu3c-8-16) 3rd gen compute-optimized, 8 vCPU, 16GB RAM
- `CpuInstanceType.CPU5C_1_2` - (cpu5c-1-2) 5th gen compute-optimized, 1 vCPU, 2GB RAM
- `CpuInstanceType.CPU5C_2_4` - (cpu5c-2-4) 5th gen compute-optimized, 2 vCPU, 4GB RAM
- `CpuInstanceType.CPU5C_4_8` - (cpu5c-4-8) 5th gen compute-optimized, 4 vCPU, 8GB RAM
- `CpuInstanceType.CPU5C_8_16` - (cpu5c-8-16) 5th gen compute-optimized, 8 vCPU, 16GB RAM

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

-----

<p align="center">
  <a href="https://github.com/yourusername/tetra">Tetra</a> •
  <a href="https://runpod.io">Runpod</a>
</p>

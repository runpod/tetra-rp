# Tetra: Serverless computing for AI workloads

Tetra is a Python SDK that streamlines the development and deployment of AI workflows on Runpod's [Serverless infrastructure](http://docs.runpod.io/serverless/overview). Write Python functions locally, and Tetra handles the infrastructure, provisioning GPUs and CPUs, managing dependencies, and transferring data, allowing you to focus on building AI applications.

You can find a repository of prebuilt Tetra examples at [runpod/tetra-examples](https://github.com/runpod/tetra-examples).

> [!Note]
> **New feature - Consolidated template management:** `PodTemplate` overrides now seamlessly integrate with `ServerlessResource` defaults, providing more consistent resource configuration and reducing deployment complexity.

## Table of contents

- [Requirements](#requirements)
- [Getting started](#getting-started)
- [Key concepts](#key-concepts)
- [How it works](#how-it-works)
- [Use cases](#use-cases)
- [Advanced features](#advanced-features)
- [Configuration](#configuration)
- [Workflow examples](#workflow-examples)
- [Contributing](#contributing)
- [Troubleshooting](#troubleshooting)

## Getting started

Before you can use Tetra, you'll need:

- Python 3.9 (or higher) installed on your local machine.
- A Runpod account with API key ([sign up here](https://runpod.io/console)).
- Basic knowledge of Python and async programming.

### Step 1: Install Tetra

```bash
pip install tetra_rp
```

### Step 2: Set your API key

Generate an API key from the [Runpod account settings](https://docs.runpod.io/get-started/api-keys) page and set it as an environment variable:

```bash
export RUNPOD_API_KEY=[YOUR_API_KEY]
```

Or save it in a `.env` file in your project directory:

```bash
echo "RUNPOD_API_KEY=[YOUR_API_KEY]" > .env
```

### Step 3: Write your first Tetra function

Add the following code to a new Python file:

```python
import asyncio
from tetra_rp import remote, LiveServerless

# Configure GPU resources
gpu_config = LiveServerless(name="tetra-quickstart")

@remote(
    resource_config=gpu_config,
    dependencies=["torch", "numpy"]
)
def gpu_compute(data):
    import torch
    import numpy as np
    
    # This runs on a GPU in Runpod's cloud
    tensor = torch.tensor(data, device="cuda")
    result = tensor.sum().item()
    
    return {
        "result": result,
        "device": torch.cuda.get_device_name(0)
    }

async def main():
    # This runs locally
    result = await gpu_compute([1, 2, 3, 4, 5])
    print(f"Sum: {result['result']}")
    print(f"Computed on: {result['device']}")

if __name__ == "__main__":
    asyncio.run(main())
```

Run the example:

```bash
python your_script.py
```

## Key concepts

### Remote functions

Tetra's `@remote` decorator marks functions for execution on Runpod's infrastructure. Everything inside the decorated function runs remotely, while code outside runs locally.

```python
@remote(resource_config=config, dependencies=["pandas"])
def process_data(data):
    # This code runs remotely
    import pandas as pd
    df = pd.DataFrame(data)
    return df.describe().to_dict()

async def main():
    # This code runs locally
    result = await process_data(my_data)
```

### Resource configuration

Tetra provides fine-grained control over hardware allocation through configuration objects:

```python
from tetra_rp import LiveServerless, GpuGroup, CpuInstanceType, PodTemplate

# GPU configuration
gpu_config = LiveServerless(
    name="ml-inference",
    gpus=[GpuGroup.AMPERE_80],  # A100 80GB
    workersMax=5,
    template=PodTemplate(containerDiskInGb=100)  # Extra disk space
)

# CPU configuration
cpu_config = LiveServerless(
    name="data-processor",
    instanceIds=[CpuInstanceType.CPU5C_4_16],  # 4 vCPU, 16GB RAM
    workersMax=3
)
```

### Dependency management

Specify Python packages in the decorator, and Tetra installs them automatically:

```python
@remote(
    resource_config=gpu_config,
    dependencies=["transformers==4.36.0", "torch", "pillow"]
)
def generate_image(prompt):
    # Import inside the function
    from transformers import pipeline
    import torch
    from PIL import Image
    
    # Your code here
```

### Parallel execution

Run multiple remote functions concurrently using Python's async capabilities:

```python
# Process multiple items in parallel
results = await asyncio.gather(
    process_item(item1),
    process_item(item2),
    process_item(item3)
)
```

## How it works

Tetra orchestrates workflow execution through a sophisticated multi-step process:

1. **Function identification**: The `@remote` decorator marks functions for remote execution, enabling Tetra to distinguish between local and remote operations.
2. **Dependency analysis**: Tetra automatically analyzes function dependencies to construct an optimal execution order, ensuring data flows correctly between sequential and parallel operations.
3. **Resource provisioning and execution**: For each remote function, Tetra:
   - Dynamically provisions endpoint and worker resources on Runpod's infrastructure.
   - Serializes and securely transfers input data to the remote worker.
   - Executes the function on the remote infrastructure with the specified GPU or CPU resources.
   - Returns results to your local environment for further processing.
4. **Data orchestration**: Results flow seamlessly between functions according to your local Python code structure, maintaining the same programming model whether functions run locally or remotely.

## Use cases

Tetra is well-suited for a diverse range of AI and data processing workloads:

- **Multi-modal AI pipelines**: Orchestrate unified workflows combining text, image, and audio models with GPU acceleration.
- **Distributed model training**: Scale training operations across multiple GPU workers for faster model development.
- **AI research experimentation**: Rapidly prototype and test complex model combinations without infrastructure overhead.
- **Production inference systems**: Deploy sophisticated multi-stage inference pipelines for real-world applications.
- **Data processing workflows**: Efficiently process large datasets using CPU workers for general computation and GPU workers for accelerated tasks.
- **Hybrid GPU/CPU workflows**: Optimize cost and performance by combining CPU preprocessing with GPU inference.

## Advanced features

### Custom Docker images

`LiveServerless` resources use a fixed Docker image that's optimized for Tetra runtime, and supports full remote code execution. For specialized environments that require a custom Docker image, use `ServerlessEndpoint` or `CpuServerlessEndpoint`:

```python
from tetra_rp import ServerlessEndpoint

custom_gpu = ServerlessEndpoint(
    name="custom-ml-env",
    imageName="pytorch/pytorch:2.0.1-cuda11.7-cudnn8-runtime",
    gpus=[GpuGroup.AMPERE_80]
)
```

Unlike `LiveServerless`, these endpoints only support dictionary payloads in the form of `{"input": {...}}` (similar to a traditional [Serverless endpoint request](https://docs.runpod.io/serverless/endpoints/send-requests)), and cannot execute arbitrary Python functions remotely.

### Persistent storage

Attach network volumes for model caching:

```python
config = LiveServerless(
    name="model-server",
    networkVolumeId="vol_abc123",  # Your volume ID
    template=PodTemplate(containerDiskInGb=100)
)
```

### Environment variables

Pass configuration to remote functions:

```python
config = LiveServerless(
    name="api-worker",
    env={"HF_TOKEN": "your_token", "MODEL_ID": "gpt2"}
)
```

## Configuration

### GPU configuration parameters

The following parameters can be used with `LiveServerless` (full remote code execution) and `ServerlessEndpoint` (Dictionary payload only) to configure your Runpod GPU endpoints:

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
| `executionTimeoutMs`| Max execution time (ms)                        | 0 (no limit)  | 600000 (10 min)                     |
| `scalerType`       | Scaling strategy                                | `QUEUE_DELAY` | `REQUEST_COUNT`                     |
| `scalerValue`      | Scaling parameter value                         | 4             | 1-10 range typical                  |
| `locations`        | Preferred datacenter locations                  | `None`        | `"us-east,eu-central"`              |
| `imageName`        | Custom Docker image (`ServerlessEndpoint` only)   | Fixed for LiveServerless | `"pytorch/pytorch:latest"`, `"my-registry/custom:v1.0"` |

### CPU configuration parameters

The same GPU configuration parameters above apply to `LiveServerless` (full remote code execution) and `CpuServerlessEndpoint` (dictionary payload only), with these additional CPU-specific parameters:

| Parameter          | Description                                     | Default       | Example Values                      |
|--------------------|-------------------------------------------------|---------------|-------------------------------------|
| `instanceIds`      | CPU Instance Types (forces a CPU endpoint type) | `None`        | `[CpuInstanceType.CPU5C_2_4]`       |
| `imageName`        | Custom Docker image (`CpuServerlessEndpoint` only) | Fixed for `LiveServerless` | `"python:3.11-slim"`, `"my-registry/custom:v1.0"` |

### Resource class comparison

| Feature | LiveServerless | ServerlessEndpoint | CpuServerlessEndpoint |
|---------|----------------|-------------------|----------------------|
| **Remote code execution** | ✅ Full Python function execution | ❌ Dictionary payloads only | ❌ Dictionary payloads only |
| **Custom Docker images** | ❌ Fixed optimized images | ✅ Any Docker image | ✅ Any Docker image |
| **Use case** | Dynamic remote functions | Traditional API endpoints | Traditional CPU endpoints |
| **Function returns** | Any Python object | Dictionary only | Dictionary only |
| **@remote decorator** | Full functionality | Limited to payload passing | Limited to payload passing |

### Available GPU types

Some common GPU groups available through `GpuGroup`:

- `GpuGroup.ANY` - Any available GPU (default)
- `GpuGroup.ADA_24` - NVIDIA GeForce RTX 4090
- `GpuGroup.AMPERE_80` - NVIDIA A100 80GB
- `GpuGroup.AMPERE_48` - NVIDIA A40, RTX A6000
- `GpuGroup.AMPERE_24` - NVIDIA RTX A5000, L4, RTX 3090


### Available CPU instance types
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

## Workflow examples

### Basic GPU workflow

```python
import asyncio
from tetra_rp import remote, LiveServerless

# Simple GPU configuration
gpu_config = LiveServerless(name="example-gpu-server")

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

async def main():
    result = await gpu_compute([1, 2, 3, 4, 5])
    print(f"Result: {result['result']}")
    print(f"Computed on: {result['gpu_name']} with CUDA {result['cuda_version']}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Advanced GPU workflow with template configuration

```python
import asyncio
from tetra_rp import remote, LiveServerless, GpuGroup, PodTemplate

# Advanced GPU configuration with consolidated template overrides
sd_config = LiveServerless(
    gpus=[GpuGroup.AMPERE_80],  # A100 80GB GPUs
    name="example_image_gen_server",
    template=PodTemplate(containerDiskInGb=100),  # Large disk for models
    workersMax=3,
    idleTimeout=10
)

@remote(
    resource_config=sd_config,
    dependencies=["diffusers", "transformers", "torch", "accelerate", "safetensors"]
)
def generate_image(prompt, width=512, height=512):
    import torch
    from diffusers import StableDiffusionPipeline
    import io
    import base64
    
    # Load pipeline (benefits from large container disk)
    pipeline = StableDiffusionPipeline.from_pretrained(
        "runwayml/stable-diffusion-v1-5",
        torch_dtype=torch.float16
    )
    pipeline = pipeline.to("cuda")
    
    # Generate image
    image = pipeline(prompt=prompt, width=width, height=height).images[0]
    
    # Convert to base64 for return
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    
    return {"image": img_str, "prompt": prompt}

async def main():
    result = await generate_image("A serene mountain landscape at sunset")
    print(f"Generated image for: {result['prompt']}")
    # Save image locally if needed
    # img_data = base64.b64decode(result["image"])
    # with open("output.png", "wb") as f:
    #     f.write(img_data)

if __name__ == "__main__":
    asyncio.run(main())
```

### Basic CPU workflow

```python
import asyncio
from tetra_rp import remote, LiveServerless, CpuInstanceType

# Simple CPU configuration
cpu_config = LiveServerless(
    name="example-cpu-server",
    instanceIds=[CpuInstanceType.CPU5G_2_8],  # 2 vCPU, 8GB RAM
)

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

async def main():
    sample_data = [
        {"name": "Alice", "age": 30, "score": 85},
        {"name": "Bob", "age": 25, "score": 92},
        {"name": "Charlie", "age": 35, "score": 78}
    ]
    
    result = await cpu_data_processing(sample_data)
    print(f"Processed {result['row_count']} rows on {result['platform']}")
    print(f"Mean values: {result['mean_values']}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Advanced CPU workflow with template configuration

```python
import asyncio
import base64
from tetra_rp import remote, LiveServerless, CpuInstanceType, PodTemplate

# Advanced CPU configuration with template overrides
data_processing_config = LiveServerless(
    name="advanced-cpu-processor",
    instanceIds=[CpuInstanceType.CPU5C_4_16, CpuInstanceType.CPU3C_4_8],  # Fallback options
    template=PodTemplate(
        containerDiskInGb=20,  # Extra disk space for data processing
        env=[{"key": "PYTHONPATH", "value": "/workspace"}]  # Custom environment
    ),
    workersMax=5,
    idleTimeout=15,
    env={"PROCESSING_MODE": "batch", "DEBUG": "false"}  # Additional env vars
)

@remote(
    resource_config=data_processing_config,
    dependencies=["pandas", "numpy", "scipy", "scikit-learn"]
)
def advanced_data_analysis(dataset, analysis_type="full"):
    import pandas as pd
    import numpy as np
    from sklearn.preprocessing import StandardScaler
    from sklearn.decomposition import PCA
    import platform
    
    # Create DataFrame
    df = pd.DataFrame(dataset)
    
    # Perform analysis based on type
    results = {
        "platform": platform.platform(),
        "dataset_shape": df.shape,
        "memory_usage": df.memory_usage(deep=True).sum()
    }
    
    if analysis_type == "full":
        # Advanced statistical analysis
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 0:
            # Standardize data
            scaler = StandardScaler()
            scaled_data = scaler.fit_transform(df[numeric_cols])
            
            # PCA analysis
            pca = PCA(n_components=min(len(numeric_cols), 3))
            pca_result = pca.fit_transform(scaled_data)
            
            results.update({
                "correlation_matrix": df[numeric_cols].corr().to_dict(),
                "pca_explained_variance": pca.explained_variance_ratio_.tolist(),
                "pca_shape": pca_result.shape
            })
    
    return results

async def main():
    # Generate sample dataset
    sample_data = [
        {"feature1": np.random.randn(), "feature2": np.random.randn(), 
         "feature3": np.random.randn(), "category": f"cat_{i%3}"}
        for i in range(1000)
    ]
    
    result = await advanced_data_analysis(sample_data, "full")
    print(f"Processed dataset with shape: {result['dataset_shape']}")
    print(f"Memory usage: {result['memory_usage']} bytes")
    print(f"PCA explained variance: {result.get('pca_explained_variance', 'N/A')}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Hybrid GPU/CPU workflow

```python
import asyncio
from tetra_rp import remote, LiveServerless, GpuGroup, CpuInstanceType, PodTemplate

# GPU configuration for model inference
gpu_config = LiveServerless(
    name="ml-inference-gpu",
    gpus=[GpuGroup.AMPERE_24],  # RTX 3090/A5000
    template=PodTemplate(containerDiskInGb=50),  # Space for models
    workersMax=2
)

# CPU configuration for data preprocessing
cpu_config = LiveServerless(
    name="data-preprocessor",
    instanceIds=[CpuInstanceType.CPU5C_4_16],  # 4 vCPU, 16GB RAM
    template=PodTemplate(
        containerDiskInGb=30,
        env=[{"key": "NUMPY_NUM_THREADS", "value": "4"}]
    ),
    workersMax=3
)

@remote(
    resource_config=cpu_config,
    dependencies=["pandas", "numpy", "scikit-learn"]
)
def preprocess_data(raw_data):
    import pandas as pd
    import numpy as np
    from sklearn.preprocessing import StandardScaler
    
    # Data cleaning and preprocessing
    df = pd.DataFrame(raw_data)
    
    # Handle missing values
    df = df.fillna(df.mean(numeric_only=True))
    
    # Normalize numeric features
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    if len(numeric_cols) > 0:
        scaler = StandardScaler()
        df[numeric_cols] = scaler.fit_transform(df[numeric_cols])
    
    return {
        "processed_data": df.to_dict('records'),
        "shape": df.shape,
        "columns": list(df.columns)
    }

@remote(
    resource_config=gpu_config,
    dependencies=["torch", "transformers", "numpy"]
)
def run_inference(processed_data):
    import torch
    import numpy as np
    
    # Simulate ML model inference on GPU
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    # Convert to tensor
    data_array = np.array([list(item.values()) for item in processed_data["processed_data"]])
    tensor = torch.tensor(data_array, dtype=torch.float32).to(device)
    
    # Simple neural network simulation
    with torch.no_grad():
        # Simulate model computation
        result = torch.nn.functional.softmax(tensor.mean(dim=1), dim=0)
        predictions = result.cpu().numpy().tolist()
    
    return {
        "predictions": predictions,
        "device_used": str(device),
        "input_shape": tensor.shape
    }

async def ml_pipeline(raw_dataset):
    """Complete ML pipeline: CPU preprocessing -> GPU inference"""
    print("Step 1: Preprocessing data on CPU...")
    preprocessed = await preprocess_data(raw_dataset)
    print(f"Preprocessed data shape: {preprocessed['shape']}")
    
    print("Step 2: Running inference on GPU...")
    results = await run_inference(preprocessed)
    print(f"Inference completed on: {results['device_used']}")
    
    return {
        "preprocessing": preprocessed,
        "inference": results
    }

async def main():
    # Sample dataset
    raw_data = [
        {"feature1": np.random.randn(), "feature2": np.random.randn(), 
         "feature3": np.random.randn(), "label": i % 2}
        for i in range(100)
    ]
    
    # Run the complete pipeline
    results = await ml_pipeline(raw_data)
    
    print("\nPipeline Results:")
    print(f"Data processed: {results['preprocessing']['shape']}")
    print(f"Predictions generated: {len(results['inference']['predictions'])}")
    print(f"GPU device: {results['inference']['device_used']}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Multi-stage ML pipeline example

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

### More examples

You can find many more examples in the [tetra-examples repository](https://github.com/runpod/tetra-examples).

You can also install the examples as a submodule:

```bash
git clone https://github.com/runpod/tetra-examples.git
cd tetra-examples
python -m examples.example
python -m examples.image_gen
python -m examples.matrix_operations
```

## Contributing

We welcome contributions to Tetra! Whether you're fixing bugs, adding features, or improving documentation, your help makes this project better.

### Development Setup

1. Fork and clone the repository
2. Set up your development environment following the project guidelines
3. Make your changes following our coding standards
4. Test your changes thoroughly
5. Submit a pull request

### Release Process

This project uses an automated release system built on Release Please. For detailed information about how releases work, including conventional commits, versioning, and the CI/CD pipeline, see our [Release System Documentation](RELEASE_SYSTEM.md).

**Quick reference for contributors:**
- Use conventional commits: `feat:`, `fix:`, `docs:`, etc.
- CI automatically runs quality checks on all PRs
- Release PRs are created automatically when changes are merged to main
- Releases are published to PyPI automatically when release PRs are merged

## Troubleshooting

### Authentication errors

Verify your API key is set correctly:

```bash
echo $RUNPOD_API_KEY  # Should show your key
```

### Import errors in remote functions

Remember to import packages inside remote functions:

```python
@remote(dependencies=["requests"])
def fetch_data(url):
    import requests  # Import here, not at top of file
    return requests.get(url).json()
```

### Performance optimization

- Set `workersMin=1` to keep workers warm and avoid cold starts
- Use `idleTimeout` to balance cost and responsiveness
- Choose appropriate GPU types for your workload

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

<p align="center">
  <a href="https://github.com/yourusername/tetra">Tetra</a> •
  <a href="https://runpod.io">Runpod</a>
</p>
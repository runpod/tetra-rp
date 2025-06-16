# Tetra: Serverless GPU Computing for AI Workloads

<p align="center">
  <b>Dynamic GPU provisioning for ML workloads with transparent execution</b>
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

Tetra is a Python SDK that streamlines the development and deployment of AI workflows on RunPod's Serverless infrastructure. It provides an abstraction layer that lets you define, execute, and monitor sophisticated AI pipelines using nothing but Python code and your local terminal, eliminating the need to interact with the RunPod console GUI.

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

You must also set up a [RunPod API key](https://docs.runpod.io/get-started/api-keys) to use this integration. You can sign up at [RunPod.io](https://runpod.io) and generate an API key from your account settings. Set this key as an environment variable or save it in a local `.env` file:

```bash
export RUNPOD_API_KEY=<YOUR_API_KEY>
```

-----

## Key Features and Concepts

Tetra offers several advantages and introduces core concepts that simplify AI workflow development:

  * **Simplified Workflow Development**: Define sophisticated AI pipelines in pure Python with minimal configuration, allowing you to concentrate on your logic rather than infrastructure complexities.
  * **Optimized Resource Utilization**: Specify hardware requirements directly at the function level. This gives you precise control over GPU and CPU allocation for each part of your pipeline.
  * **Seamless Deployment**: Tetra automatically manages the setup of RunPod Serverless infrastructure, including worker communication and data transfer between your local environment and remote workers.
  * **Reduced Development Overhead**: Avoid the time-consuming tasks of writing application code for each worker, building Docker containers, and managing individual endpoints.
  * **Intuitive Programming Model**: Utilize Python decorators to easily mark functions for remote execution on the RunPod infrastructure.

### Inline Resource Configuration

Tetra allows for granular hardware specification at the function level using the `LiveServerless` object. This enables detailed control over GPU allocation and worker scaling.

For example:

```python
from tetra import LiveServerless, GpuGroup

# Configure a GPU endpoint
gpu_config = LiveServerless(
    gpus=[GpuGroup.ANY], # Use any available GPU (default: .ANY)
    workersMax=5, # Scales up to 5 workers (default: 3)
    name="parallel-processor", # Name of the endpoint that will be created or used
)
```

Refer to the [Configuration Parameters](#configuration) section for a full list of available settings.

### Dynamic GPU Provisioning

Tetra enables you to automatically provision GPUs on demand without any manual setup:

```python
@remote(
    resource_config=gpu_config,
)
def my_gpu_function(data):
    # Runs on GPU when called
    return process(data)
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
      * Tetra provisions the necessary endpoint and worker resources on RunPod.
      * Input data is serialized and transferred to the remote worker.
      * The function executes on the remote infrastructure.
      * Results are then returned to your local environment.
4.  Data flows between functions as defined by your local Python code.

-----

## Common Use Cases

Tetra is well-suited for a variety of AI and data processing tasks, including:

  * **Multi-modal AI pipelines**: Combine text, image, and audio models into unified workflows.
  * **Distributed model training**: Scale model training operations across multiple GPU workers.
  * **AI research experimentation**: Quickly prototype and test complex combinations of models.
  * **Production inference systems**: Deploy sophisticated, multi-stage inference pipelines for real-world applications.
  * **Data processing workflows**: Process large datasets efficiently using distributed computing resources.

-----

## Quick Start Example

```python
import os
import asyncio
from dotenv import load_dotenv
from tetra_rp import remote, LiveServerless

# Load environment variables from .env file
# Make sure you .env file is in the same directory as your .py file
load_dotenv()

# Configure RunPod resources
runpod_config = LiveServerless(name="example-diffusion-server")

# Define a function to run on RunPod GPU
@remote(
    resource_config=runpod_config,
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

async def main_quick_start():
    # Run the function on RunPod GPU
    result = await gpu_compute([1, 2, 3, 4, 5])
    print(f"Result: {result['result']}")
    print(f"Computed on: {result['gpu_name']} with CUDA {result['cuda_version']}")

if __name__ == "__main__":
    try:
        asyncio.run(main_quick_start())
    except Exception as e:
        print(f"An error occurred: {e}")
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
from dotenv import load_dotenv
from tetra_rp import remote, LiveServerless

# Load environment variables from .env file
# Make sure you .env file is in the same directory as your .py file
load_dotenv()

# Configure RunPod resources
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

### Configuration Parameters

The following parameters can be used with the `LiveServerless` object to configure your RunPod endpoints:

| Parameter          | Description                                     | Default       | Example Values                      |
|--------------------|-------------------------------------------------|---------------|-------------------------------------|
| `name`             | (Required) Name for your endpoint               | `""`          | `"stable-diffusion-server"`         |
| `gpus`             | GPU pool IDs that can be used by workers        | `[GpuGroup.ANY]` | `"List[GpuGroup]"` list of [GPU Pool IDs](https://docs.runpod.io/references/gpu-types#gpu-pools) |
| `gpuCount`         | Number of GPUs per worker                       | 1             | 1, 2, 4                             |
| `workersMin`       | Minimum number of workers                       | 0             | Set to 1 for persistence            |
| `workersMax`       | Maximum number of workers                       | 3             | Higher for more concurrency         |
| `idleTimeout`      | Minutes before scaling down                     | 5             | 10, 30, 60                          |
| `env`              | Environment variables                           | `None`        | `{"HF_TOKEN": "xyz"}`               |
| `networkVolumeId`  | Persistent storage ID                           | `None`        | `"vol_abc123"`                      |
| `executionTimeoutMs`| Max execution time (ms)                         | 0 (no limit)  | 600000 (10 min)                     |
| `scalerType`       | Scaling strategy                                | `QUEUE_DELAY` | `NONE`, `QUEUE_SIZE`                |
| `scalerValue`      | Scaling parameter value                         | 4             | 1-10 range typical                  |
| `locations`        | Preferred datacenter locations                  | `None`        | `"us-east,eu-central"`              |

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

-----

<p align="center">
  <a href="https://github.com/yourusername/tetra">Tetra</a> •
  <a href="https://runpod.io">RunPod</a>
</p>

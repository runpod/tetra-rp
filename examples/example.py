import asyncio
from dotenv import load_dotenv
from tetra_rp import remote, LiveServerless

# Load environment variables from .env file
load_dotenv()

# Configuration for a GPU resource
gpu_config = LiveServerless(
    gpuIds="any",
    workersMax=1,
    name="example_live_server",
)


# Initialize the model server and save to disk
@remote(
    resource_config=gpu_config,
    dependencies=["scikit-learn", "numpy", "torch"],
)
def initialize_model():
    """Initialize a simple ML model and save it to disk."""
    from sklearn.ensemble import RandomForestClassifier
    from pathlib import Path
    import numpy as np
    import pickle
    import torch

    model_path = Path("/tmp/persisted_model.pkl")
    is_cuda_available = torch.cuda.is_available()
    device_count = torch.cuda.device_count()
    # Only create and save model if it doesn't exist yet
    if not model_path.exists():
        print("Creating new model instance...")
        # Create a simple random forest model
        model = RandomForestClassifier(n_estimators=10)

        # Train on a tiny dataset
        X = np.array([[1, 2], [2, 3], [3, 4], [4, 5]])
        y = np.array([0, 0, 1, 1])
        model.fit(X, y)

        # Save the model to disk
        with open(model_path, "wb") as f:
            pickle.dump(model, f)

        print(f"Model created, trained, and saved to {model_path}")
    else:
        print(f"Model already exists at {model_path}")

    return {
        "status": "ready",
        "model_path": model_path,
        "cuda_available": is_cuda_available,
        "device_count": device_count,
    }


# Make predictions using the model loaded from disk
@remote(resource_config=gpu_config)
def predict(features):
    """Make predictions using the model loaded from disk."""
    import numpy as np
    import pickle
    from pathlib import Path

    model_path = Path("/tmp/persisted_model.pkl")

    # Check if model file exists
    if not model_path.exists():
        return {"error": "Model not initialized. Call initialize_model first."}

    # Load the model from disk
    with open(model_path, "rb") as f:
        model = pickle.load(f)

    # Convert features to numpy array
    X = np.array([features])

    # Make prediction
    prediction = model.predict(X)[0]
    probability = model.predict_proba(X)[0].tolist()

    return {"prediction": int(prediction), "probability": probability}


async def main():
    # Step 1: Initialize the model (only needed once)
    print("Initializing model...")
    init_result = await initialize_model()
    print(f"Initialization result: {init_result}")

    # Step 2: Make a prediction
    print("\nMaking first prediction...")
    pred1 = await predict([2.5, 3.5])
    print(f"Prediction result: {pred1}")

    # Step 3: Make another prediction
    print("\nMaking second prediction...")
    pred2 = await predict([3.5, 4.5])
    print(f"Prediction result: {pred2}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"An error occurred: {e}")

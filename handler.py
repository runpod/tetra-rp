import os
import traceback
import runpod
import base64
import cloudpickle
import importlib.util
import sys
import subprocess
import importlib
import time
import pkg_resources


def install_dependencies(packages):
    """
    Install Python packages using pip with proper process completion handling.

    Args:
        packages: List of package names or package specifications

    Returns:
        tuple: (success, output_or_error)
    """
    if not packages:
        return True, "No packages to install"

    print(f"Installing dependencies: {packages}")

    try:
        # Use pip to install the packages
        # Note: communicate() already waits for process completion
        process = subprocess.Popen(
            [sys.executable, "-m", "pip", "install", "--no-cache-dir"] + packages,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # This waits for the process to complete and captures output
        stdout, stderr = process.communicate()

        # Force reload of installed packages
        importlib.invalidate_caches()

        # Simply rely on pip's return code
        if process.returncode != 0:
            return False, f"Error installing packages: {stderr.decode()}"
        else:
            print(f"Successfully installed packages: {packages}")
            return True, stdout.decode()
    except Exception as e:
        return False, f"Exception during package installation: {str(e)}"


def handler(event):
    """
    RunPod serverless function handler with dependency installation.

    The event input should contain:
    - function_name: Name of the function to execute
    - function_code: Source code of the function
    - args: List of base64-encoded cloudpickle-serialized arguments
    - kwargs: Dictionary of base64-encoded cloudpickle-serialized keyword arguments
    - dependencies: (Optional) List of pip packages to install
    """
    try:
        # Extract parameters from the event
        input_data = event.get("input", {})

        function_name = input_data.get("function_name")
        function_code = input_data.get("function_code")
        serialized_args = input_data.get("args", [])
        serialized_kwargs = input_data.get("kwargs", {})
        dependencies = input_data.get("dependencies", [])

        if not all([function_name, function_code]):
            return {
                "success": False,
                "error": "Missing required parameters: function_name or function_code",
            }

        # Install dependencies if provided
        if dependencies:
            success, output = install_dependencies(dependencies)
            if not success:
                return {
                    "success": False,
                    "error": f"Dependency installation failed: {output}",
                }
            print(f"Successfully installed dependencies: {dependencies}")

        # Execute the function code
        namespace = {}
        exec(function_code, namespace)

        if function_name not in namespace:
            return {
                "success": False,
                "error": f"Function '{function_name}' not found in the provided code",
            }

        func = namespace[function_name]

        # Deserialize arguments using cloudpickle
        args = [cloudpickle.loads(base64.b64decode(arg)) for arg in serialized_args]
        kwargs = {
            k: cloudpickle.loads(base64.b64decode(v))
            for k, v in serialized_kwargs.items()
        }

        # Execute the function
        result = func(*args, **kwargs)

        # Serialize result using cloudpickle
        serialized_result = base64.b64encode(cloudpickle.dumps(result)).decode("utf-8")

        # Return success response
        return {"success": True, "result": serialized_result}

    except Exception as e:
        # Capture full traceback for better debugging
        traceback_str = traceback.format_exc()
        error_message = f"{str(e)}\n{traceback_str}"
        print(f"Error executing function: {error_message}")

        # Return error response
        return {"success": False, "error": error_message}


# Start the RunPod serverless handler

runpod.serverless.start({"handler": handler})

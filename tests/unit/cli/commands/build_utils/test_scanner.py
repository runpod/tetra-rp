"""Tests for RemoteDecoratorScanner."""

import tempfile
from pathlib import Path


from runpod_flash.cli.commands.build_utils.scanner import RemoteDecoratorScanner


def test_discover_simple_function():
    """Test discovering a simple @remote function."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)

        # Create a simple test file
        test_file = project_dir / "test_module.py"
        test_file.write_text(
            """
from runpod_flash import LiveServerless, remote

gpu_config = LiveServerless(name="test_gpu")

@remote(gpu_config)
async def my_function(data):
    return processed_data
"""
        )

        scanner = RemoteDecoratorScanner(project_dir)
        functions = scanner.discover_remote_functions()

        assert len(functions) == 1
        assert functions[0].function_name == "my_function"
        assert functions[0].resource_config_name == "test_gpu"
        assert functions[0].is_async is True
        assert functions[0].is_class is False


def test_discover_class():
    """Test discovering a @remote class."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)

        test_file = project_dir / "test_module.py"
        test_file.write_text(
            """
from runpod_flash import LiveServerless, remote

gpu_config = LiveServerless(name="test_gpu")

@remote(gpu_config)
class MyModel:
    def __init__(self):
        pass

    def process(self, data):
        return data
"""
        )

        scanner = RemoteDecoratorScanner(project_dir)
        functions = scanner.discover_remote_functions()

        assert len(functions) == 1
        assert functions[0].function_name == "MyModel"
        assert functions[0].is_class is True


def test_discover_multiple_functions_same_config():
    """Test discovering multiple functions with same resource config."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)

        test_file = project_dir / "test_module.py"
        test_file.write_text(
            """
from runpod_flash import LiveServerless, remote

gpu_config = LiveServerless(name="gpu_worker")

@remote(gpu_config)
async def process_data(data):
    return data

@remote(gpu_config)
async def analyze_data(data):
    return analysis
"""
        )

        scanner = RemoteDecoratorScanner(project_dir)
        functions = scanner.discover_remote_functions()

        assert len(functions) == 2
        assert all(f.resource_config_name == "gpu_worker" for f in functions)
        assert functions[0].function_name in ["process_data", "analyze_data"]


def test_discover_functions_different_configs():
    """Test discovering functions with different resource configs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)

        test_file = project_dir / "test_module.py"
        test_file.write_text(
            """
from runpod_flash import LiveServerless, CpuLiveServerless, remote

gpu_config = LiveServerless(name="gpu_worker")
cpu_config = CpuLiveServerless(name="cpu_worker")

@remote(gpu_config)
async def gpu_task(data):
    return data

@remote(cpu_config)
async def cpu_task(data):
    return data
"""
        )

        scanner = RemoteDecoratorScanner(project_dir)
        functions = scanner.discover_remote_functions()

        assert len(functions) == 2
        resource_configs = {f.resource_config_name for f in functions}
        assert resource_configs == {"gpu_worker", "cpu_worker"}


def test_discover_nested_module():
    """Test discovering functions in nested modules."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)

        # Create nested structure
        workers_dir = project_dir / "workers" / "gpu"
        workers_dir.mkdir(parents=True)

        test_file = workers_dir / "inference.py"
        test_file.write_text(
            """
from runpod_flash import LiveServerless, remote

config = LiveServerless(name="gpu_inference")

@remote(config)
async def inference(model, data):
    return results
"""
        )

        scanner = RemoteDecoratorScanner(project_dir)
        functions = scanner.discover_remote_functions()

        assert len(functions) == 1
        assert functions[0].module_path == "workers.gpu.inference"
        assert functions[0].function_name == "inference"


def test_discover_inline_config():
    """Test discovering with inline resource config."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)

        test_file = project_dir / "test_module.py"
        test_file.write_text(
            """
from runpod_flash import LiveServerless, remote

@remote(LiveServerless(name="inline_config"))
async def my_function(data):
    return data
"""
        )

        scanner = RemoteDecoratorScanner(project_dir)
        functions = scanner.discover_remote_functions()

        assert len(functions) == 1
        assert functions[0].resource_config_name == "inline_config"


def test_ignore_non_remote_functions():
    """Test that non-decorated functions are ignored."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)

        test_file = project_dir / "test_module.py"
        test_file.write_text(
            """
async def normal_function(data):
    return data

class NormalClass:
    pass
"""
        )

        scanner = RemoteDecoratorScanner(project_dir)
        functions = scanner.discover_remote_functions()

        assert len(functions) == 0


def test_discover_sync_function():
    """Test discovering synchronous @remote function."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)

        test_file = project_dir / "test_module.py"
        test_file.write_text(
            """
from runpod_flash import LiveServerless, remote

config = LiveServerless(name="cpu_sync")

@remote(config)
def sync_function(data):
    return data
"""
        )

        scanner = RemoteDecoratorScanner(project_dir)
        functions = scanner.discover_remote_functions()

        assert len(functions) == 1
        assert functions[0].is_async is False


def test_exclude_venv_directory():
    """Test that .venv directory is excluded from scanning."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)

        # Create .venv directory with Python files
        venv_dir = project_dir / ".venv" / "lib" / "python3.11"
        venv_dir.mkdir(parents=True)
        venv_file = venv_dir / "test_module.py"
        venv_file.write_text(
            """
from runpod_flash import LiveServerless, remote

config = LiveServerless(name="venv_config")

@remote(config)
async def venv_function(data):
    return data
"""
        )

        # Create legitimate project file
        project_file = project_dir / "main.py"
        project_file.write_text(
            """
from runpod_flash import LiveServerless, remote

config = LiveServerless(name="project_config")

@remote(config)
async def project_function(data):
    return data
"""
        )

        scanner = RemoteDecoratorScanner(project_dir)
        functions = scanner.discover_remote_functions()

        # Should only find the project function, not the venv one
        assert len(functions) == 1
        assert functions[0].resource_config_name == "project_config"


def test_exclude_flash_directory():
    """Test that .flash directory is excluded from scanning."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)

        # Create .flash directory with Python files
        flash_dir = project_dir / ".flash" / "build"
        flash_dir.mkdir(parents=True)
        flash_file = flash_dir / "generated.py"
        flash_file.write_text(
            """
from runpod_flash import LiveServerless, remote

config = LiveServerless(name="flash_config")

@remote(config)
async def flash_function(data):
    return data
"""
        )

        # Create legitimate project file
        project_file = project_dir / "main.py"
        project_file.write_text(
            """
from runpod_flash import LiveServerless, remote

config = LiveServerless(name="project_config")

@remote(config)
async def project_function(data):
    return data
"""
        )

        scanner = RemoteDecoratorScanner(project_dir)
        functions = scanner.discover_remote_functions()

        # Should only find the project function, not the flash one
        assert len(functions) == 1
        assert functions[0].resource_config_name == "project_config"


def test_exclude_runpod_directory():
    """Test that .runpod directory is excluded from scanning."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)

        # Create .runpod directory with Python files
        runpod_dir = project_dir / ".runpod" / "cache"
        runpod_dir.mkdir(parents=True)
        runpod_file = runpod_dir / "cached.py"
        runpod_file.write_text(
            """
from runpod_flash import LiveServerless, remote

config = LiveServerless(name="runpod_config")

@remote(config)
async def runpod_function(data):
    return data
"""
        )

        # Create legitimate project file
        project_file = project_dir / "main.py"
        project_file.write_text(
            """
from runpod_flash import LiveServerless, remote

config = LiveServerless(name="project_config")

@remote(config)
async def project_function(data):
    return data
"""
        )

        scanner = RemoteDecoratorScanner(project_dir)
        functions = scanner.discover_remote_functions()

        # Should only find the project function, not the runpod one
        assert len(functions) == 1
        assert functions[0].resource_config_name == "project_config"


def test_fallback_to_variable_name_when_name_parameter_missing():
    """Test that variable name is used when resource config has no name= parameter."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)

        test_file = project_dir / "test_module.py"
        test_file.write_text(
            """
from runpod_flash import LiveServerless, remote

gpu_config = LiveServerless()

@remote(gpu_config)
async def my_function(data):
    return data
"""
        )

        scanner = RemoteDecoratorScanner(project_dir)
        functions = scanner.discover_remote_functions()

        assert len(functions) == 1
        # Should fall back to variable name when name parameter is missing
        assert functions[0].resource_config_name == "gpu_config"


def test_ignore_non_serverless_classes_with_serverless_in_name():
    """Test that helper classes with 'Serverless' in name are ignored."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)

        test_file = project_dir / "test_module.py"
        test_file.write_text(
            """
from runpod_flash import LiveServerless, remote

class MyServerlessHelper:
    def __init__(self):
        pass

helper = MyServerlessHelper()
config = LiveServerless(name="real_config")

@remote(config)
async def my_function(data):
    return data
"""
        )

        scanner = RemoteDecoratorScanner(project_dir)
        functions = scanner.discover_remote_functions()

        # Should find function with real config but ignore helper class
        assert len(functions) == 1
        assert functions[0].resource_config_name == "real_config"


def test_extract_resource_name_with_special_characters():
    """Test that resource names with special characters are extracted correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)

        test_file = project_dir / "test_module.py"
        test_file.write_text(
            """
from runpod_flash import LiveServerless, remote

config = LiveServerless(name="01_gpu-worker.v1")

@remote(config)
async def my_function(data):
    return data
"""
        )

        scanner = RemoteDecoratorScanner(project_dir)
        functions = scanner.discover_remote_functions()

        assert len(functions) == 1
        # Should preserve special characters in resource name
        assert functions[0].resource_config_name == "01_gpu-worker.v1"


def test_scanner_extracts_config_variable_names():
    """Test that scanner captures config variable names."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        test_file = project_dir / "endpoint.py"

        test_file.write_text(
            """
from runpod_flash import LiveLoadBalancer, remote

gpu_config = LiveLoadBalancer(name="my-endpoint")

@remote(gpu_config, method="GET", path="/health")
async def health():
    return {"status": "ok"}
"""
        )

        scanner = RemoteDecoratorScanner(project_dir)
        functions = scanner.discover_remote_functions()

        assert len(functions) == 1
        assert functions[0].config_variable == "gpu_config"
        assert functions[0].resource_config_name == "my-endpoint"


def test_cpu_live_load_balancer_flags():
    """Test that CpuLiveLoadBalancer is correctly flagged as load-balanced and live."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        test_file = project_dir / "cpu_endpoint.py"

        test_file.write_text(
            """
from runpod_flash import CpuLiveLoadBalancer, remote

cpu_config = CpuLiveLoadBalancer(name="cpu_worker")

@remote(cpu_config, method="POST", path="/validate")
async def validate_data(text):
    return {"valid": True}

@remote(cpu_config, method="GET", path="/health")
async def health():
    return {"status": "ok"}
"""
        )

        scanner = RemoteDecoratorScanner(project_dir)
        functions = scanner.discover_remote_functions()

        assert len(functions) == 2

        # Check that both functions have the correct flags
        for func in functions:
            assert func.resource_config_name == "cpu_worker"
            assert func.is_load_balanced is True, (
                "CpuLiveLoadBalancer should be marked as load-balanced"
            )
            assert func.is_live_resource is True, (
                "CpuLiveLoadBalancer should be marked as live resource"
            )
            assert func.resource_type == "CpuLiveLoadBalancer"

        # Check specific HTTP metadata for each function
        validate_func = next(f for f in functions if f.function_name == "validate_data")
        assert validate_func.http_method == "POST"
        assert validate_func.http_path == "/validate"

        health_func = next(f for f in functions if f.function_name == "health")
        assert health_func.http_method == "GET"
        assert health_func.http_path == "/health"

"""Tests for RemoteDecoratorScanner."""

import tempfile
from pathlib import Path


from tetra_rp.cli.commands.build_utils.scanner import RemoteDecoratorScanner


def test_discover_simple_function():
    """Test discovering a simple @remote function."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)

        # Create a simple test file
        test_file = project_dir / "test_module.py"
        test_file.write_text(
            """
from tetra_rp import LiveServerless, remote

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
        assert functions[0].resource_config_name == "gpu_config"
        assert functions[0].is_async is True
        assert functions[0].is_class is False


def test_discover_class():
    """Test discovering a @remote class."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)

        test_file = project_dir / "test_module.py"
        test_file.write_text(
            """
from tetra_rp import LiveServerless, remote

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
from tetra_rp import LiveServerless, remote

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
        assert all(f.resource_config_name == "gpu_config" for f in functions)
        assert functions[0].function_name in ["process_data", "analyze_data"]


def test_discover_functions_different_configs():
    """Test discovering functions with different resource configs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)

        test_file = project_dir / "test_module.py"
        test_file.write_text(
            """
from tetra_rp import LiveServerless, CpuLiveServerless, remote

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
        assert resource_configs == {"gpu_config", "cpu_config"}


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
from tetra_rp import LiveServerless, remote

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
from tetra_rp import LiveServerless, remote

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
from tetra_rp import LiveServerless, remote

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

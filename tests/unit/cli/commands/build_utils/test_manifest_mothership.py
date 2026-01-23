"""Tests for mothership resource creation in manifest."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from tetra_rp.cli.commands.build_utils.manifest import ManifestBuilder
from tetra_rp.cli.commands.build_utils.scanner import RemoteFunctionMetadata


class TestManifestMothership:
    """Test mothership resource creation in manifest."""

    def test_manifest_includes_mothership_with_main_py(self):
        """Test mothership resource added to manifest when main.py detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)

            # Create main.py with FastAPI routes
            main_file = project_root / "main.py"
            main_file.write_text(
                """
from fastapi import FastAPI
app = FastAPI()

@app.get("/")
def root():
    return {"msg": "Hello"}
"""
            )

            # Create a simple function file
            func_file = project_root / "functions.py"
            func_file.write_text(
                """
from tetra_rp import remote
from tetra_rp import LiveServerless

gpu_config = LiveServerless(name="gpu_worker")

@remote(resource_config=gpu_config)
def process(data):
    return data
"""
            )

            # Change to project directory for detection
            with patch(
                "tetra_rp.cli.commands.build_utils.manifest.Path.cwd",
                return_value=project_root,
            ):
                builder = ManifestBuilder(
                    project_name="test",
                    remote_functions=[],
                )
                manifest = builder.build()

                # Check mothership is in resources
                assert "mothership" in manifest["resources"]
                mothership = manifest["resources"]["mothership"]
                assert mothership["is_mothership"] is True
                assert mothership["main_file"] == "main.py"
                assert mothership["app_variable"] == "app"
                assert mothership["resource_type"] == "CpuLiveLoadBalancer"
                assert mothership["imageName"] == "runpod/tetra-rp-lb-cpu:latest"

    def test_manifest_skips_mothership_without_routes(self):
        """Test mothership NOT added if main.py has no routes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)

            # Create main.py without routes
            main_file = project_root / "main.py"
            main_file.write_text(
                """
from fastapi import FastAPI
app = FastAPI()
# No routes defined
"""
            )

            with patch(
                "tetra_rp.cli.commands.build_utils.manifest.Path.cwd",
                return_value=project_root,
            ):
                builder = ManifestBuilder(project_name="test", remote_functions=[])
                manifest = builder.build()

                # Mothership should NOT be in resources
                assert "mothership" not in manifest["resources"]

    def test_manifest_skips_mothership_without_main_py(self):
        """Test mothership NOT added if no main.py exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)

            with patch(
                "tetra_rp.cli.commands.build_utils.manifest.Path.cwd",
                return_value=project_root,
            ):
                builder = ManifestBuilder(project_name="test", remote_functions=[])
                manifest = builder.build()

                # Mothership should NOT be in resources
                assert "mothership" not in manifest["resources"]

    def test_manifest_handles_mothership_name_conflict(self):
        """Test mothership uses alternate name if conflict with @remote resource."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)

            # Create main.py with routes
            main_file = project_root / "main.py"
            main_file.write_text(
                """
from fastapi import FastAPI
app = FastAPI()

@app.get("/")
def root():
    return {"msg": "Hello"}
"""
            )

            # Create a remote function with name "mothership" (conflict)
            func_file = project_root / "functions.py"
            func_file.write_text(
                """
from tetra_rp import remote
from tetra_rp import LiveServerless

mothership_config = LiveServerless(name="mothership")

@remote(resource_config=mothership_config)
def process(data):
    return data
"""
            )

            # Create remote function metadata with resource named "mothership"
            remote_func = RemoteFunctionMetadata(
                function_name="process",
                module_path="functions",
                resource_config_name="mothership",
                resource_type="LiveServerless",
                is_async=False,
                is_class=False,
                file_path=func_file,
            )

            with patch(
                "tetra_rp.cli.commands.build_utils.manifest.Path.cwd",
                return_value=project_root,
            ):
                builder = ManifestBuilder(
                    project_name="test", remote_functions=[remote_func]
                )
                manifest = builder.build()

                # Original mothership should be in resources
                assert "mothership" in manifest["resources"]
                # Auto-generated mothership should use alternate name
                assert "mothership-entrypoint" in manifest["resources"]
                entrypoint = manifest["resources"]["mothership-entrypoint"]
                assert entrypoint["is_mothership"] is True

    def test_mothership_resource_config(self):
        """Test mothership resource has correct configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)

            main_file = project_root / "main.py"
            main_file.write_text(
                """
from fastapi import FastAPI
app = FastAPI()

@app.get("/")
def root():
    return {"msg": "Hello"}
"""
            )

            with patch(
                "tetra_rp.cli.commands.build_utils.manifest.Path.cwd",
                return_value=project_root,
            ):
                builder = ManifestBuilder(project_name="test", remote_functions=[])
                manifest = builder.build()

                mothership = manifest["resources"]["mothership"]

                # Check all expected fields
                assert mothership["resource_type"] == "CpuLiveLoadBalancer"
                assert mothership["handler_file"] == "handler_mothership.py"
                assert mothership["functions"] == []
                assert mothership["is_load_balanced"] is True
                assert mothership["is_live_resource"] is True
                assert mothership["imageName"] == "runpod/tetra-rp-lb-cpu:latest"
                assert mothership["workersMin"] == 1
                assert mothership["workersMax"] == 3

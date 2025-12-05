"""Integration tests for flash run --auto-provision command."""

import pytest
from unittest.mock import patch, MagicMock
from textwrap import dedent
from typer.testing import CliRunner

from tetra_rp.cli.main import app

runner = CliRunner()


class TestRunAutoProvision:
    """Test flash run --auto-provision integration."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary Flash project for testing."""
        # Create main.py with FastAPI app
        main_file = tmp_path / "main.py"
        main_file.write_text(
            dedent(
                """
                from fastapi import FastAPI
                from tetra_rp.client import remote
                from tetra_rp.core.resources.serverless import ServerlessResource

                app = FastAPI()

                gpu_config = ServerlessResource(
                    name="test-gpu",
                    gpuCount=1,
                    workersMax=3,
                    workersMin=0,
                    flashboot=False,
                )

                @remote(resource_config=gpu_config)
                async def gpu_task():
                    return "result"

                @app.get("/")
                def root():
                    return {"message": "Hello"}
                """
            )
        )

        return tmp_path

    @pytest.fixture
    def temp_project_many_resources(self, tmp_path):
        """Create temporary project with many resources (> 5)."""
        main_file = tmp_path / "main.py"
        main_file.write_text(
            dedent(
                """
                from fastapi import FastAPI
                from tetra_rp.client import remote
                from tetra_rp.core.resources.serverless import ServerlessResource

                app = FastAPI()

                # Create 6 resources to trigger confirmation
                configs = [
                    ServerlessResource(
                        name=f"endpoint-{i}",
                        gpuCount=1,
                        workersMax=3,
                        workersMin=0,
                        flashboot=False,
                    )
                    for i in range(6)
                ]

                @remote(resource_config=configs[0])
                async def task1(): pass

                @remote(resource_config=configs[1])
                async def task2(): pass

                @remote(resource_config=configs[2])
                async def task3(): pass

                @remote(resource_config=configs[3])
                async def task4(): pass

                @remote(resource_config=configs[4])
                async def task5(): pass

                @remote(resource_config=configs[5])
                async def task6(): pass

                @app.get("/")
                def root():
                    return {"message": "Hello"}
                """
            )
        )

        return tmp_path

    def test_run_without_auto_provision(self, temp_project, monkeypatch):
        """Test that flash run without --auto-provision doesn't deploy resources."""
        monkeypatch.chdir(temp_project)

        # Mock subprocess to prevent actual uvicorn start
        with patch("tetra_rp.cli.commands.run.subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.pid = 12345
            mock_process.wait.side_effect = KeyboardInterrupt()
            mock_popen.return_value = mock_process

            # Mock OS-level process group operations to prevent hanging
            with patch("tetra_rp.cli.commands.run.os.getpgid") as mock_getpgid:
                mock_getpgid.return_value = 12345

                with patch("tetra_rp.cli.commands.run.os.killpg") as mock_killpg:
                    # Mock discovery to track if it was called
                    with patch(
                        "tetra_rp.cli.commands.run._discover_resources"
                    ) as mock_discover:
                        runner.invoke(app, ["run"])

                        # Discovery should not be called
                        mock_discover.assert_not_called()

    def test_run_with_auto_provision_single_resource(self, temp_project, monkeypatch):
        """Test flash run --auto-provision with single resource."""
        monkeypatch.chdir(temp_project)

        # Mock subprocess to prevent actual uvicorn start
        with patch("tetra_rp.cli.commands.run.subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.pid = 12345
            mock_process.wait.side_effect = KeyboardInterrupt()
            mock_popen.return_value = mock_process

            # Mock OS-level process group operations
            with patch("tetra_rp.cli.commands.run.os.getpgid") as mock_getpgid:
                mock_getpgid.return_value = 12345

                with patch("tetra_rp.cli.commands.run.os.killpg") as mock_killpg:
                    # Mock deployment orchestrator
                    with patch(
                        "tetra_rp.cli.commands.run._start_background_provisioning"
                    ) as mock_provision:
                        runner.invoke(app, ["run", "--auto-provision"])

                        # Provisioning should be called
                        mock_provision.assert_called_once()

    def test_run_with_auto_provision_skips_reload(self, temp_project, monkeypatch):
        """Test that auto-provision is skipped on reload."""
        monkeypatch.chdir(temp_project)

        # Simulate reload environment
        monkeypatch.setenv("UVICORN_RELOADER_PID", "12345")

        # Mock subprocess to prevent actual uvicorn start
        with patch("tetra_rp.cli.commands.run.subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.pid = 12345
            mock_process.wait.side_effect = KeyboardInterrupt()
            mock_popen.return_value = mock_process

            # Mock OS-level process group operations
            with patch("tetra_rp.cli.commands.run.os.getpgid") as mock_getpgid:
                mock_getpgid.return_value = 12345

                with patch("tetra_rp.cli.commands.run.os.killpg") as mock_killpg:
                    # Mock provisioning
                    with patch(
                        "tetra_rp.cli.commands.run._start_background_provisioning"
                    ) as mock_provision:
                        runner.invoke(app, ["run", "--auto-provision"])

                        # Provisioning should NOT be called on reload
                        mock_provision.assert_not_called()

    def test_run_with_auto_provision_many_resources_confirmed(
        self, temp_project, monkeypatch
    ):
        """Test auto-provision with > 5 resources and user confirmation."""
        monkeypatch.chdir(temp_project)

        # Create 6 mock resources
        mock_resources = [MagicMock(name=f"endpoint-{i}") for i in range(6)]

        # Mock subprocess to prevent actual uvicorn start
        with patch("tetra_rp.cli.commands.run.subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.pid = 12345
            mock_process.wait.side_effect = KeyboardInterrupt()
            mock_popen.return_value = mock_process

            # Mock OS-level process group operations
            with patch("tetra_rp.cli.commands.run.os.getpgid") as mock_getpgid:
                mock_getpgid.return_value = 12345

                with patch("tetra_rp.cli.commands.run.os.killpg") as mock_killpg:
                    # Mock discovery to return > 5 resources
                    with patch(
                        "tetra_rp.cli.commands.run._discover_resources"
                    ) as mock_discover:
                        mock_discover.return_value = mock_resources

                        # Mock questionary to simulate user confirmation
                        with patch(
                            "tetra_rp.cli.commands.run.questionary.confirm"
                        ) as mock_confirm:
                            mock_confirm.return_value.ask.return_value = True

                            with patch(
                                "tetra_rp.cli.commands.run._start_background_provisioning"
                            ) as mock_provision:
                                runner.invoke(app, ["run", "--auto-provision"])

                                # Should prompt for confirmation
                                mock_confirm.assert_called_once()

                                # Should provision after confirmation
                                mock_provision.assert_called_once()

    def test_run_with_auto_provision_many_resources_cancelled(
        self, temp_project, monkeypatch
    ):
        """Test auto-provision with > 5 resources and user cancellation."""
        monkeypatch.chdir(temp_project)

        # Create 6 mock resources
        mock_resources = [MagicMock(name=f"endpoint-{i}") for i in range(6)]

        # Mock subprocess to prevent actual uvicorn start
        with patch("tetra_rp.cli.commands.run.subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.pid = 12345
            mock_process.wait.side_effect = KeyboardInterrupt()
            mock_popen.return_value = mock_process

            # Mock OS-level process group operations
            with patch("tetra_rp.cli.commands.run.os.getpgid") as mock_getpgid:
                mock_getpgid.return_value = 12345

                with patch("tetra_rp.cli.commands.run.os.killpg") as mock_killpg:
                    # Mock discovery to return > 5 resources
                    with patch(
                        "tetra_rp.cli.commands.run._discover_resources"
                    ) as mock_discover:
                        mock_discover.return_value = mock_resources

                        # Mock questionary to simulate user cancellation
                        with patch(
                            "tetra_rp.cli.commands.run.questionary.confirm"
                        ) as mock_confirm:
                            mock_confirm.return_value.ask.return_value = False

                            with patch(
                                "tetra_rp.cli.commands.run._start_background_provisioning"
                            ) as mock_provision:
                                runner.invoke(app, ["run", "--auto-provision"])

                                # Should prompt for confirmation
                                mock_confirm.assert_called_once()

                                # Should NOT provision after cancellation
                                mock_provision.assert_not_called()

    def test_run_auto_provision_discovery_error(self, temp_project, monkeypatch):
        """Test that run handles discovery errors gracefully."""
        monkeypatch.chdir(temp_project)

        # Mock subprocess to prevent actual uvicorn start
        with patch("tetra_rp.cli.commands.run.subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.pid = 12345
            mock_process.wait.side_effect = KeyboardInterrupt()
            mock_popen.return_value = mock_process

            # Mock OS-level process group operations
            with patch("tetra_rp.cli.commands.run.os.getpgid") as mock_getpgid:
                mock_getpgid.return_value = 12345

                with patch("tetra_rp.cli.commands.run.os.killpg") as mock_killpg:
                    # Mock discovery to raise exception
                    with patch(
                        "tetra_rp.cli.commands.run._discover_resources"
                    ) as mock_discover:
                        mock_discover.return_value = []

                        runner.invoke(app, ["run", "--auto-provision"])

                        # Server should still start despite discovery error
                        mock_popen.assert_called_once()

    def test_run_auto_provision_no_resources_found(self, tmp_path, monkeypatch):
        """Test auto-provision when no resources are found."""
        monkeypatch.chdir(tmp_path)

        # Create main.py without any @remote decorators
        main_file = tmp_path / "main.py"
        main_file.write_text(
            dedent(
                """
                from fastapi import FastAPI

                app = FastAPI()

                @app.get("/")
                def root():
                    return {"message": "Hello"}
                """
            )
        )

        # Mock subprocess to prevent actual uvicorn start
        with patch("tetra_rp.cli.commands.run.subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.pid = 12345
            mock_process.wait.side_effect = KeyboardInterrupt()
            mock_popen.return_value = mock_process

            # Mock OS-level process group operations
            with patch("tetra_rp.cli.commands.run.os.getpgid") as mock_getpgid:
                mock_getpgid.return_value = 12345

                with patch("tetra_rp.cli.commands.run.os.killpg") as mock_killpg:
                    with patch(
                        "tetra_rp.cli.commands.run._start_background_provisioning"
                    ) as mock_provision:
                        runner.invoke(app, ["run", "--auto-provision"])

                        # Provisioning should not be called
                        mock_provision.assert_not_called()

                        # Server should still start
                        mock_popen.assert_called_once()

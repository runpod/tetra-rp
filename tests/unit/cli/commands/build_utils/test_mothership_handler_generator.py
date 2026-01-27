"""Tests for mothership handler generation."""

import tempfile
from pathlib import Path

import pytest

from tetra_rp.cli.commands.build_utils.mothership_handler_generator import (
    generate_mothership_handler,
)


class TestMothershipeHandlerGenerator:
    """Test mothership handler generation."""

    def test_generate_mothership_handler(self):
        """Test basic mothership handler generation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "handler_mothership.py"

            generate_mothership_handler(
                main_file="main.py",
                app_variable="app",
                output_path=output_path,
            )

            assert output_path.exists()
            content = output_path.read_text()

            # Check expected imports and structure
            assert "from main import app" in content
            assert "CORSMiddleware" in content
            assert "add_middleware(" in content
            assert '@app.get("/ping")' in content
            assert "async def ping():" in content
            assert '"status": "healthy"' in content
            assert "MOTHERSHIP_ID = os.getenv(" in content
            assert "MOTHERSHIP_URL = os.getenv(" in content

    def test_generate_mothership_handler_custom_app_name(self):
        """Test handler generation with custom app variable name."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "handler_mothership.py"

            generate_mothership_handler(
                main_file="server.py",
                app_variable="api",
                output_path=output_path,
            )

            content = output_path.read_text()

            # Note: Handler always imports as 'app' for convenience
            assert "from server import api as app" in content
            assert "@app.get" in content

    def test_generate_mothership_handler_creates_directory(self):
        """Test handler generator creates output directory if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "subdir" / "handler_mothership.py"

            generate_mothership_handler(
                main_file="main.py",
                app_variable="app",
                output_path=output_path,
            )

            assert output_path.parent.exists()
            assert output_path.exists()

    def test_generate_mothership_handler_invalid_main_file(self):
        """Test handler generation fails with invalid main_file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "handler_mothership.py"

            with pytest.raises(ValueError, match="Invalid main_file"):
                generate_mothership_handler(
                    main_file="main",  # Missing .py extension
                    app_variable="app",
                    output_path=output_path,
                )

    def test_generate_mothership_handler_invalid_app_variable(self):
        """Test handler generation fails with invalid app_variable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "handler_mothership.py"

            with pytest.raises(ValueError, match="Invalid app_variable"):
                generate_mothership_handler(
                    main_file="main.py",
                    app_variable="123invalid",  # Invalid identifier
                    output_path=output_path,
                )

    def test_generate_mothership_handler_content_structure(self):
        """Test generated handler has correct structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "handler_mothership.py"

            generate_mothership_handler(
                main_file="main.py",
                app_variable="app",
                output_path=output_path,
            )

            content = output_path.read_text()

            # Should have docstring
            assert "Auto-generated handler for mothership endpoint" in content
            # Should have imports
            assert "import os" in content
            assert "from fastapi.middleware.cors" in content
            # Should have CORS setup
            assert "CORSMiddleware" in content
            # Should have health check
            assert "@app.get" in content

    def test_generate_mothership_handler_with_app_py(self):
        """Test handler generation with app.py instead of main.py."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "handler_mothership.py"

            generate_mothership_handler(
                main_file="app.py",
                app_variable="app",
                output_path=output_path,
            )

            content = output_path.read_text()

            assert "from app import app" in content

    def test_generate_mothership_handler_overwrite_existing(self):
        """Test handler generation overwrites existing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "handler_mothership.py"

            # Create initial file
            output_path.write_text("old content")

            # Generate new handler
            generate_mothership_handler(
                main_file="main.py",
                app_variable="app",
                output_path=output_path,
            )

            content = output_path.read_text()

            # Should have new content
            assert "old content" not in content
            assert "Auto-generated handler" in content

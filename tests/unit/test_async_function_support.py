"""
Test that @remote decorator supports both sync and async function definitions.
"""

import pytest
from runpod_flash.stubs.live_serverless import get_function_source


class TestAsyncFunctionSupport:
    """Test async function support in @remote decorator."""

    def test_sync_function_source_extraction(self):
        """Test that sync functions can be extracted."""

        def my_sync_function(x: int) -> int:
            return x * 2

        source, src_hash = get_function_source(my_sync_function)

        assert "def my_sync_function" in source
        assert "return x * 2" in source
        assert src_hash is not None
        assert len(src_hash) == 64  # SHA256 hash length

    def test_async_function_source_extraction(self):
        """Test that async functions can be extracted."""

        async def my_async_function(x: int) -> int:
            return x * 2

        source, src_hash = get_function_source(my_async_function)

        assert "async def my_async_function" in source
        assert "return x * 2" in source
        assert src_hash is not None
        assert len(src_hash) == 64  # SHA256 hash length

    def test_async_function_with_await(self):
        """Test async function with await statements."""

        async def async_with_await(x: int) -> int:
            import asyncio

            await asyncio.sleep(0.1)
            return x * 3

        source, src_hash = get_function_source(async_with_await)

        assert "async def async_with_await" in source
        assert "await asyncio.sleep" in source
        assert "return x * 3" in source

    def test_async_function_with_imports(self):
        """Test async function with internal imports."""

        async def gpu_matrix_multiply(input_data: dict) -> dict:
            import torch

            size = input_data.get("matrix_size", 1000)
            device = "cuda" if torch.cuda.is_available() else "cpu"
            matrix = torch.randn(size, size, device=device)
            result = torch.matmul(matrix, matrix.T)
            return {"device": device, "result": result.shape}

        source, src_hash = get_function_source(gpu_matrix_multiply)

        assert "async def gpu_matrix_multiply" in source
        assert "import torch" in source
        assert "torch.cuda.is_available()" in source
        assert "torch.matmul" in source

    def test_sync_and_async_have_different_hashes(self):
        """Test that sync and async versions of same function have different hashes."""

        def sync_version():
            return "hello"

        async def async_version():
            return "hello"

        sync_source, sync_hash = get_function_source(sync_version)
        async_source, async_hash = get_function_source(async_version)

        assert sync_hash != async_hash
        assert "def sync_version" in sync_source
        assert "async def async_version" in async_source

    def test_async_function_with_type_hints(self):
        """Test async function with complex type hints."""

        async def process_csv_data(input_data: dict) -> dict:
            import pandas as pd
            import numpy as np

            rows = input_data.get("rows", 1000)
            data = {f"col_{i}": np.random.randn(rows) for i in range(5)}
            df = pd.DataFrame(data)

            return {
                "status": "success",
                "shape": list(df.shape),
                "mean": df.mean().to_dict(),
            }

        source, src_hash = get_function_source(process_csv_data)

        assert "async def process_csv_data" in source
        assert "input_data: dict" in source
        assert "-> dict:" in source
        assert "import pandas as pd" in source

    def test_lambda_not_supported(self):
        """Test that lambda functions are not supported."""

        # This should raise because lambdas are not FunctionDef nodes
        # Note: We can't use lambda directly due to ruff E731 rule
        with pytest.raises((ValueError, OSError)):
            # Create lambda inline to test error handling
            # OSError can occur from inspect.getsource on lambda
            get_function_source((lambda x: x * 2))

    def test_source_hash_consistency(self):
        """Test that same function source produces same hash."""

        def test_func(x: int) -> int:
            return x + 1

        source1, hash1 = get_function_source(test_func)
        source2, hash2 = get_function_source(test_func)

        assert source1 == source2
        assert hash1 == hash2

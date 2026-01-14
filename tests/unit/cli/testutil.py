import pytest


@pytest.fixture
def mock_asyncio_run_coro():
    """Create a mock asyncio.run that executes coroutines."""

    def run_coro(coro):
        import asyncio

        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    return run_coro

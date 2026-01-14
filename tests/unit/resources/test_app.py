"""Unit tests for FlashApp hydration logic."""

from unittest.mock import AsyncMock, patch

import pytest

from tetra_rp.core.resources.app import FlashApp


@pytest.fixture
def mock_graphql_client():
    with patch("tetra_rp.core.resources.app.RunpodGraphQLClient") as mock_cls:
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.__aexit__.return_value = False
        mock_cls.return_value = client
        yield client


@pytest.mark.asyncio
async def test_hydrate_short_circuits_when_already_hydrated(mock_graphql_client):
    app = FlashApp("demo", eager_hydrate=False)
    app._hydrated = True

    await app._hydrate()

    mock_graphql_client.__aenter__.assert_not_called()


@pytest.mark.asyncio
async def test_hydrate_sets_id_when_app_exists(mock_graphql_client):
    mock_graphql_client.get_flash_app_by_name.return_value = {"id": "app-123"}
    app = FlashApp("demo", eager_hydrate=False)

    await app._hydrate()

    assert app.id == "app-123"
    mock_graphql_client.get_flash_app_by_name.assert_awaited_once_with("demo")


@pytest.mark.asyncio
async def test_hydrate_raises_for_conflicting_ids(mock_graphql_client):
    mock_graphql_client.get_flash_app_by_name.return_value = {"id": "app-123"}
    app = FlashApp("demo", id="other", eager_hydrate=False)

    with pytest.raises(ValueError):
        await app._hydrate()

    mock_graphql_client.create_flash_app.assert_not_awaited()


@pytest.mark.asyncio
async def test_hydrate_creates_app_when_missing(mock_graphql_client):
    mock_graphql_client.get_flash_app_by_name.side_effect = Exception("app not found")
    mock_graphql_client.create_flash_app.return_value = {"id": "app-999"}
    app = FlashApp("demo", eager_hydrate=False)

    await app._hydrate()

    mock_graphql_client.create_flash_app.assert_awaited_once_with({"name": "demo"})
    assert app.id == "app-999"
    assert app._hydrated is True


@pytest.mark.asyncio
async def test_hydrate_propagates_unexpected_errors(mock_graphql_client):
    mock_graphql_client.get_flash_app_by_name.side_effect = RuntimeError("boom")
    app = FlashApp("demo", eager_hydrate=False)

    with pytest.raises(RuntimeError):
        await app._hydrate()

    mock_graphql_client.create_flash_app.assert_not_awaited()

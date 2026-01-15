"""Unit tests for ManifestFetcher."""

import asyncio
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from tetra_rp.runtime.manifest_fetcher import ManifestFetcher


class TestManifestFetcher:
    """Test ManifestFetcher caching and GQL integration."""

    @pytest.fixture
    def sample_manifest(self):
        """Sample manifest for testing."""
        return {
            "version": "1.0",
            "project_name": "test-app",
            "resources": {"gpu_config": {"resource_type": "ServerlessEndpoint"}},
            "function_registry": {"process_gpu": "gpu_config"},
        }

    @pytest.mark.asyncio
    async def test_fetch_falls_back_to_local_file_when_gql_not_implemented(
        self, sample_manifest, tmp_path
    ):
        """Verify fetcher falls back to local file when GQL raises NotImplementedError."""
        # Write sample manifest to temp file
        manifest_file = tmp_path / "flash_manifest.json"
        with open(manifest_file, "w") as f:
            json.dump(sample_manifest, f)

        fetcher = ManifestFetcher(manifest_path=manifest_file)
        result = await fetcher.get_manifest()

        assert result == sample_manifest

    @pytest.mark.asyncio
    async def test_caching_prevents_multiple_fetches(self, sample_manifest, tmp_path):
        """Verify cached manifest is reused within TTL."""
        manifest_file = tmp_path / "flash_manifest.json"
        with open(manifest_file, "w") as f:
            json.dump(sample_manifest, f)

        fetcher = ManifestFetcher(cache_ttl=300, manifest_path=manifest_file)

        # First call - loads from file
        result1 = await fetcher.get_manifest()
        assert result1 == sample_manifest

        # Second call immediately - should use cache
        result2 = await fetcher.get_manifest()
        assert result2 == sample_manifest
        assert result2 is result1  # Same object reference (cached)

    @pytest.mark.asyncio
    async def test_cache_expiration_triggers_refetch(self, sample_manifest, tmp_path):
        """Verify expired cache triggers new fetch."""
        manifest_file = tmp_path / "flash_manifest.json"
        with open(manifest_file, "w") as f:
            json.dump(sample_manifest, f)

        # Very short TTL
        fetcher = ManifestFetcher(cache_ttl=0.1, manifest_path=manifest_file)

        # First call
        result1 = await fetcher.get_manifest()
        assert result1 == sample_manifest

        # Wait for cache to expire
        await asyncio.sleep(0.2)

        # Second call - cache expired, should refetch
        result2 = await fetcher.get_manifest()
        assert result2 == sample_manifest

    @pytest.mark.asyncio
    async def test_fetch_from_gql_raises_not_implemented(self):
        """Verify GQL fetch placeholder raises NotImplementedError."""
        fetcher = ManifestFetcher()

        with pytest.raises(NotImplementedError, match="not yet implemented"):
            await fetcher._fetch_from_gql()

    @pytest.mark.asyncio
    async def test_update_local_file_writes_manifest(self, sample_manifest, tmp_path):
        """Verify manifest is written to local file."""
        manifest_file = tmp_path / "flash_manifest.json"
        fetcher = ManifestFetcher(manifest_path=manifest_file)

        fetcher._update_local_file(sample_manifest)

        # Verify file was written
        assert manifest_file.exists()
        with open(manifest_file) as f:
            written = json.load(f)
        assert written == sample_manifest

    @pytest.mark.asyncio
    async def test_cache_invalidation(self, sample_manifest, tmp_path):
        """Verify manual cache invalidation works."""
        manifest_file = tmp_path / "flash_manifest.json"
        with open(manifest_file, "w") as f:
            json.dump(sample_manifest, f)

        fetcher = ManifestFetcher(cache_ttl=300, manifest_path=manifest_file)

        # Load and cache
        await fetcher.get_manifest()
        assert fetcher._cached_manifest is not None

        # Invalidate
        fetcher.invalidate_cache()

        # Next call should refetch (cache_loaded_at is 0)
        assert fetcher._cache_loaded_at == 0

    @pytest.mark.asyncio
    async def test_concurrent_requests_use_lock(self, sample_manifest, tmp_path):
        """Verify concurrent requests are properly synchronized."""
        manifest_file = tmp_path / "flash_manifest.json"
        with open(manifest_file, "w") as f:
            json.dump(sample_manifest, f)

        fetcher = ManifestFetcher(manifest_path=manifest_file)

        # Make multiple concurrent requests
        results = await asyncio.gather(
            fetcher.get_manifest(),
            fetcher.get_manifest(),
            fetcher.get_manifest(),
        )

        # All should return the same manifest
        assert all(r == sample_manifest for r in results)

    @pytest.mark.asyncio
    async def test_handles_missing_local_file_gracefully(self):
        """Verify fetcher handles missing local file gracefully."""
        # Point to non-existent file
        fetcher = ManifestFetcher(manifest_path=Path("/nonexistent/manifest.json"))

        # Should fall back to loading from cwd (which also won't exist in test)
        result = await fetcher.get_manifest()

        # load_manifest returns empty dict when no file is found
        assert result == {"resources": {}, "function_registry": {}}

    @pytest.mark.asyncio
    async def test_mothership_id_passed_to_gql(self):
        """Verify mothership_id is passed through to GQL fetch."""
        fetcher = ManifestFetcher()

        # Spy on _fetch_from_gql to capture arguments
        with patch.object(fetcher, "_fetch_from_gql") as mock_fetch:
            mock_fetch.side_effect = NotImplementedError()

            await fetcher.get_manifest(mothership_id="test-123")

            # Verify mothership_id was passed to fetch
            mock_fetch.assert_called_once_with("test-123")

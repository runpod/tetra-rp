"""
Unit tests for NetworkVolume idempotent behavior.
"""

from unittest.mock import AsyncMock, patch
import pytest

from tetra_rp.core.resources.network_volume import NetworkVolume, DataCenter


class TestNetworkVolumeIdempotent:
    """Test NetworkVolume idempotent deployment behavior."""

    @pytest.fixture
    def mock_runpod_client(self):
        """Mock RunpodRestClient."""
        client = AsyncMock()
        # Mock both methods we need
        client.list_network_volumes = AsyncMock()
        client.create_network_volume = AsyncMock()
        return client

    @pytest.fixture
    def sample_volume_data(self):
        """Sample volume data as returned by API."""
        return {
            "id": "vol-123456",
            "name": "deanq",
            "dataCenterId": "EU-RO-1",
            "size": 50,
        }

    @pytest.mark.asyncio
    async def test_deploy_creates_new_volume_when_none_exists(
        self, mock_runpod_client, sample_volume_data
    ):
        """Test that deploy creates a new volume when none with the same name exists."""
        # Arrange
        volume = NetworkVolume(name="deanq", size=50)

        # Mock no existing volumes
        mock_runpod_client.list_network_volumes.return_value = []
        mock_runpod_client.create_network_volume.return_value = sample_volume_data

        with patch(
            "tetra_rp.core.resources.network_volume.RunpodRestClient"
        ) as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_runpod_client
            mock_client_class.return_value.__aexit__ = AsyncMock()
            # Act
            result = await volume.deploy()

        # Assert
        mock_runpod_client.list_network_volumes.assert_called_once()
        mock_runpod_client.create_network_volume.assert_called_once()
        assert result.id == "vol-123456"
        assert result.name == "deanq"

    @pytest.mark.asyncio
    async def test_deploy_reuses_existing_volume_with_same_name(
        self, mock_runpod_client, sample_volume_data
    ):
        """Test that deploy reuses an existing volume with the same name."""
        # Arrange
        volume = NetworkVolume(name="deanq", size=50)

        # Mock existing volume with same name
        mock_runpod_client.list_network_volumes.return_value = [sample_volume_data]

        with patch(
            "tetra_rp.core.resources.network_volume.RunpodRestClient"
        ) as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_runpod_client
            mock_client_class.return_value.__aexit__ = AsyncMock()
            # Act
            result = await volume.deploy()

        # Assert
        mock_runpod_client.list_network_volumes.assert_called_once()
        mock_runpod_client.create_network_volume.assert_not_called()  # Should not create new volume
        assert result.id == "vol-123456"
        assert result.name == "deanq"

    @pytest.mark.asyncio
    async def test_deploy_creates_new_when_existing_has_different_datacenter(
        self, mock_runpod_client, sample_volume_data
    ):
        """Test that deploy creates new volume when existing has different datacenter."""
        # Arrange
        volume = NetworkVolume(name="deanq", size=50, dataCenterId=DataCenter.EU_RO_1)

        # Mock existing volume with same name but different datacenter
        existing_volume_data = {
            **sample_volume_data,
            "dataCenterId": "US-WEST-1",  # Different datacenter
        }
        mock_runpod_client.list_network_volumes.return_value = [existing_volume_data]
        mock_runpod_client.create_network_volume.return_value = sample_volume_data

        with patch(
            "tetra_rp.core.resources.network_volume.RunpodRestClient"
        ) as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_runpod_client
            mock_client_class.return_value.__aexit__ = AsyncMock()
            # Act
            result = await volume.deploy()

        # Assert
        mock_runpod_client.list_network_volumes.assert_called_once()
        mock_runpod_client.create_network_volume.assert_called_once()  # Should create new volume
        assert result.id == "vol-123456"

    @pytest.mark.asyncio
    async def test_deploy_multiple_times_same_name_is_idempotent(
        self, mock_runpod_client, sample_volume_data
    ):
        """Test that multiple deployments with same name are idempotent."""
        # Arrange
        volume1 = NetworkVolume(name="deanq", size=50)
        volume2 = NetworkVolume(name="deanq", size=50)

        # First call returns no existing volumes, second call returns the created volume
        mock_runpod_client.list_network_volumes.side_effect = [
            [],  # First call: no existing
            [sample_volume_data],  # Second call: volume exists
        ]
        mock_runpod_client.create_network_volume.return_value = sample_volume_data

        with patch(
            "tetra_rp.core.resources.network_volume.RunpodRestClient"
        ) as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_runpod_client
            mock_client_class.return_value.__aexit__ = AsyncMock()
            # Act
            result1 = await volume1.deploy()
            result2 = await volume2.deploy()

        # Assert
        assert mock_runpod_client.list_network_volumes.call_count == 2
        assert (
            mock_runpod_client.create_network_volume.call_count == 1
        )  # Only called once
        assert result1.id == result2.id == "vol-123456"

    def test_resource_id_based_on_name_and_datacenter(self):
        """Test that resource_id is based on name and datacenter for named volumes."""
        # Arrange & Act
        volume1 = NetworkVolume(name="deanq", dataCenterId=DataCenter.EU_RO_1)
        volume2 = NetworkVolume(name="deanq", dataCenterId=DataCenter.EU_RO_1)
        volume3 = NetworkVolume(name="different", dataCenterId=DataCenter.EU_RO_1)

        # Assert
        assert volume1.resource_id == volume2.resource_id  # Same name + datacenter
        assert volume1.resource_id != volume3.resource_id  # Different name

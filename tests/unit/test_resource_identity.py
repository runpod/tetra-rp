"""Unit tests for resource identity and resource_id stability."""

import cloudpickle

from tetra_rp.core.resources.live_serverless import LiveServerless
from tetra_rp.core.resources.gpu import GpuGroup


class TestResourceIdentity:
    """Test resource_id stability and identity management."""

    def test_resource_id_stable_across_multiple_calls(self):
        """Test that resource_id remains the same when called multiple times."""
        config = LiveServerless(
            name="test-endpoint",
            gpus=[GpuGroup.ADA_24],
            workersMin=0,
            workersMax=3,
            flashboot=True,
        )

        # Call resource_id multiple times
        id1 = config.resource_id
        id2 = config.resource_id
        id3 = config.resource_id

        # All should be identical
        assert id1 == id2
        assert id2 == id3

    def test_resource_id_stable_after_validator_mutations(self):
        """Test that resource_id is stable even after validators mutate the object."""
        config = LiveServerless(
            name="test-gpu",
            gpus=[GpuGroup.ADA_24],
            workersMin=0,
            workersMax=3,
            flashboot=True,
        )

        # Get resource_id (this triggers caching)
        first_id = config.resource_id

        # Verify validator mutated the name (should have "-fb" suffix)
        assert config.name.endswith("-fb")

        # Get resource_id again
        second_id = config.resource_id

        # Should still be the same
        assert first_id == second_id

    def test_resource_id_different_for_different_configs(self):
        """Test that different configurations produce different resource_ids."""
        config1 = LiveServerless(
            name="endpoint-1",
            gpus=[GpuGroup.ADA_24],
            workersMin=0,
            workersMax=3,
        )

        config2 = LiveServerless(
            name="endpoint-2",
            gpus=[GpuGroup.ADA_24],
            workersMin=0,
            workersMax=3,
        )

        # Different names should produce different IDs
        assert config1.resource_id != config2.resource_id

    def test_resource_id_same_for_identical_configs(self):
        """Test that identical configurations produce the same resource_id."""
        config1 = LiveServerless(
            name="test-endpoint",
            gpus=[GpuGroup.ADA_24],
            workersMin=0,
            workersMax=3,
            flashboot=True,
        )

        config2 = LiveServerless(
            name="test-endpoint",
            gpus=[GpuGroup.ADA_24],
            workersMin=0,
            workersMax=3,
            flashboot=True,
        )

        # Identical configs should produce identical IDs
        assert config1.resource_id == config2.resource_id

    def test_pickled_resource_preserves_id(self):
        """Test that pickling and unpickling preserves resource_id."""
        config = LiveServerless(
            name="test-pickle",
            gpus=[GpuGroup.ADA_24],
            workersMin=0,
            workersMax=3,
            flashboot=True,
        )

        # Get resource_id before pickling
        id_before = config.resource_id

        # Pickle and unpickle
        pickled = cloudpickle.dumps(config)
        restored = cloudpickle.loads(pickled)

        # Get resource_id after unpickling
        id_after = restored.resource_id

        # Should be the same
        assert id_before == id_after

    def test_validator_idempotency_name_suffix(self):
        """Test that validators don't add multiple suffixes."""
        config = LiveServerless(
            name="test",
            gpus=[GpuGroup.ADA_24],
            workersMin=0,
            workersMax=3,
            flashboot=True,
        )

        # First access triggers validators
        _ = config.resource_id

        # Name should have exactly one "-fb" suffix
        assert config.name == "test-fb"
        assert config.name.count("-fb") == 1

        # Manually trigger validator again (simulate multiple runs)
        config.sync_input_fields()

        # Should still have only one "-fb" suffix
        assert config.name == "test-fb"
        assert config.name.count("-fb") == 1

    def test_resource_id_excludes_none_values(self):
        """Test that None values are excluded from resource_id computation."""
        config1 = LiveServerless(
            name="test",
            gpus=[GpuGroup.ADA_24],
            workersMin=0,
            workersMax=3,
            flashboot=True,
        )

        config2 = LiveServerless(
            name="test",
            gpus=[GpuGroup.ADA_24],
            workersMin=0,
            workersMax=3,
            flashboot=True,
            networkVolume=None,  # Explicitly set to None
        )

        # Both should have the same resource_id (None values excluded)
        assert config1.resource_id == config2.resource_id

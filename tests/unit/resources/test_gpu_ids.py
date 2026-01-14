import pytest

from tetra_rp.core.resources.gpu import GpuGroup, GpuType


class TestGpuIdsImports:
    def test_imports_work(self):
        # highlights the import crash that used to happen from type annotations
        assert GpuGroup is not None
        assert GpuType is not None


class TestGpuIdsBehavior:
    def test_to_gpu_ids_str_groups_only_contains_pool_ids(self):
        gpu_ids = GpuGroup.to_gpu_ids_str([GpuGroup.AMPERE_48, GpuGroup.AMPERE_24])
        # extra tokens (negations) can be present, but pools should always be included
        assert "AMPERE_48" in gpu_ids
        assert "AMPERE_24" in gpu_ids

    def test_from_gpu_ids_str_pool_only_returns_group(self):
        parsed = GpuGroup.from_gpu_ids_str("AMPERE_24")
        assert parsed == [GpuGroup.AMPERE_24]

    def test_gpu_type_is_gpu_type_checks_enum_member_names(self):
        assert GpuType.is_gpu_type("NVIDIA_L4") is True
        assert GpuType.is_gpu_type("NVIDIA L4") is False

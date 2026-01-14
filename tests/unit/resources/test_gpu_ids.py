import pytest

from tetra_rp.core.resources.gpu import GpuGroup, GpuType


class TestGpuIdsEncoding:
    def test_to_gpu_ids_str_with_groups_only(self):
        gpu_ids = GpuGroup.to_gpu_ids_str([GpuGroup.AMPERE_48, GpuGroup.AMPERE_24])
        assert set(gpu_ids.split(",")) == {"AMPERE_48", "AMPERE_24"}

    def test_to_gpu_ids_str_with_specific_type_implies_pool_and_negates_others(self):
        gpu_ids = GpuGroup.to_gpu_ids_str([GpuType.NVIDIA_L4])

        assert set(gpu_ids.split(",")) == {
            "AMPERE_24",
            "-NVIDIA_RTX_A5000",
            "-NVIDIA_GEFORCE_RTX_3090",
        }

    def test_to_gpu_ids_str_when_pool_is_explicit_no_negations(self):
        gpu_ids = GpuGroup.to_gpu_ids_str([GpuGroup.AMPERE_24, GpuType.NVIDIA_L4])
        assert set(gpu_ids.split(",")) == {"AMPERE_24"}


class TestGpuIdsDecoding:
    def test_from_gpu_ids_str_pool_only_returns_group(self):
        parsed = GpuGroup.from_gpu_ids_str("AMPERE_24")
        assert parsed == [GpuGroup.AMPERE_24]

    def test_from_gpu_ids_str_pool_with_negation_expands_to_types(self):
        parsed = GpuGroup.from_gpu_ids_str("AMPERE_24,-NVIDIA_L4")
        assert parsed == [GpuType.NVIDIA_RTX_A5000, GpuType.NVIDIA_GEFORCE_RTX_3090]

    def test_from_gpu_ids_str_skips_invalid_tokens(self):
        parsed = GpuGroup.from_gpu_ids_str("AMPERE_24,INVALID_GPU,-NOT_A_TYPE")
        assert GpuGroup.AMPERE_24 in parsed
        assert all(item != "INVALID_GPU" for item in parsed)


class TestGpuTypeIds:
    @pytest.mark.parametrize(
        "token, expected",
        [
            ("NVIDIA_L4", GpuType.NVIDIA_L4),
            ("NVIDIA L4", GpuType.NVIDIA_L4),
        ],
    )
    def test_from_id_accepts_name_and_value(self, token, expected):
        assert GpuType.from_id(token) == expected

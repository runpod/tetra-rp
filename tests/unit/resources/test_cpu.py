"""
Unit tests for CPU utilities and constants.
"""

from tetra_rp.core.resources.cpu import (
    CpuInstanceType,
    CPU_INSTANCE_DISK_LIMITS,
    calculate_max_disk_size,
    get_max_disk_size_for_instances,
)


class TestCpuInstanceDiskLimits:
    """Test CPU instance disk limits constants and utilities."""

    def test_cpu_instance_disk_limits_mapping(self):
        """Test that all CPU instance types have disk limits defined."""
        expected_limits = {
            CpuInstanceType.CPU3G_1_4: 10,
            CpuInstanceType.CPU3G_2_8: 20,
            CpuInstanceType.CPU3G_4_16: 40,
            CpuInstanceType.CPU3G_8_32: 80,
            CpuInstanceType.CPU3C_1_2: 10,
            CpuInstanceType.CPU3C_2_4: 20,
            CpuInstanceType.CPU3C_4_8: 40,
            CpuInstanceType.CPU3C_8_16: 80,
            CpuInstanceType.CPU5C_1_2: 15,
            CpuInstanceType.CPU5C_2_4: 30,
            CpuInstanceType.CPU5C_4_8: 60,
            CpuInstanceType.CPU5C_8_16: 120,
        }

        assert CPU_INSTANCE_DISK_LIMITS == expected_limits

    def test_get_max_disk_size_single_instance(self):
        """Test getting max disk size for single instance type."""
        result = get_max_disk_size_for_instances([CpuInstanceType.CPU3G_1_4])
        assert result == 10

        result = get_max_disk_size_for_instances([CpuInstanceType.CPU5C_8_16])
        assert result == 120

    def test_get_max_disk_size_multiple_instances(self):
        """Test getting max disk size for multiple instance types (returns minimum)."""
        result = get_max_disk_size_for_instances(
            [
                CpuInstanceType.CPU3G_1_4,  # 10GB
                CpuInstanceType.CPU3G_2_8,  # 20GB
            ]
        )
        assert result == 10  # Should return minimum

        result = get_max_disk_size_for_instances(
            [
                CpuInstanceType.CPU5C_4_8,  # 60GB
                CpuInstanceType.CPU3G_8_32,  # 80GB
                CpuInstanceType.CPU5C_8_16,  # 120GB
            ]
        )
        assert result == 60  # Should return minimum

    def test_get_max_disk_size_empty_list(self):
        """Test getting max disk size for empty list returns None."""
        result = get_max_disk_size_for_instances([])
        assert result is None

        result = get_max_disk_size_for_instances(None)
        assert result is None

    def test_calculate_max_disk_size_cpu3g_cpu3c(self):
        """Test programmatic calculation for CPU3G and CPU3C instances."""
        # CPU3G/CPU3C use 10GB per vCPU
        assert calculate_max_disk_size(CpuInstanceType.CPU3G_1_4) == 10  # 1 × 10
        assert calculate_max_disk_size(CpuInstanceType.CPU3G_2_8) == 20  # 2 × 10
        assert calculate_max_disk_size(CpuInstanceType.CPU3G_4_16) == 40  # 4 × 10
        assert calculate_max_disk_size(CpuInstanceType.CPU3G_8_32) == 80  # 8 × 10

        assert calculate_max_disk_size(CpuInstanceType.CPU3C_1_2) == 10  # 1 × 10
        assert calculate_max_disk_size(CpuInstanceType.CPU3C_2_4) == 20  # 2 × 10
        assert calculate_max_disk_size(CpuInstanceType.CPU3C_4_8) == 40  # 4 × 10
        assert calculate_max_disk_size(CpuInstanceType.CPU3C_8_16) == 80  # 8 × 10

    def test_calculate_max_disk_size_cpu5c(self):
        """Test programmatic calculation for CPU5C instances."""
        # CPU5C uses 15GB per vCPU
        assert calculate_max_disk_size(CpuInstanceType.CPU5C_1_2) == 15  # 1 × 15
        assert calculate_max_disk_size(CpuInstanceType.CPU5C_2_4) == 30  # 2 × 15
        assert calculate_max_disk_size(CpuInstanceType.CPU5C_4_8) == 60  # 4 × 15
        assert calculate_max_disk_size(CpuInstanceType.CPU5C_8_16) == 120  # 8 × 15

    def test_programmatic_limits_match_dictionary(self):
        """Test that programmatically calculated limits match the generated dictionary."""
        for instance_type in CpuInstanceType:
            calculated = calculate_max_disk_size(instance_type)
            from_dict = CPU_INSTANCE_DISK_LIMITS[instance_type]
            assert calculated == from_dict, (
                f"Mismatch for {instance_type.value}: calculated={calculated}, dict={from_dict}"
            )

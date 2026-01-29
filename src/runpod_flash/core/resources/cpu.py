from enum import Enum
from typing import List, Optional


class CpuInstanceType(str, Enum):
    """Valid CPU instance types.

    Format: {generation}{type}-{vcpu}-{memory_gb}
    Based on Runpod backend validation logic:
    - memoryInGb = vcpuCount * flavor.ramMultiplier

    RAM Multipliers (DEV environment):
    - cpu3g: 4.0 (1 vCPU = 4GB, 2 vCPU = 8GB, etc.)
    - cpu3c: 2.0 (1 vCPU = 2GB, 2 vCPU = 4GB, etc.)
    - cpu5c: 2.0 (1 vCPU = 2GB, 2 vCPU = 4GB, etc.)
    """

    # 3rd Generation General Purpose (RAM multiplier: 4.0)

    CPU3G_1_4 = "cpu3g-1-4"
    """1 vCPU, 4GB RAM, max 10GB container disk"""

    CPU3G_2_8 = "cpu3g-2-8"
    """2 vCPU, 8GB RAM, max 20GB container disk"""

    CPU3G_4_16 = "cpu3g-4-16"
    """4 vCPU, 16GB RAM, max 40GB container disk"""

    CPU3G_8_32 = "cpu3g-8-32"
    """8 vCPU, 32GB RAM, max 80GB container disk"""

    # 3rd Generation Compute-Optimized (RAM multiplier: 2.0)

    CPU3C_1_2 = "cpu3c-1-2"
    """1 vCPU, 2GB RAM, max 10GB container disk"""

    CPU3C_2_4 = "cpu3c-2-4"
    """2 vCPU, 4GB RAM, max 20GB container disk"""

    CPU3C_4_8 = "cpu3c-4-8"
    """4 vCPU, 8GB RAM, max 40GB container disk"""

    CPU3C_8_16 = "cpu3c-8-16"
    """8 vCPU, 16GB RAM, max 80GB container disk"""

    # 5th Generation Compute-Optimized (RAM multiplier: 2.0)

    CPU5C_1_2 = "cpu5c-1-2"
    """1 vCPU, 2GB RAM, max 15GB container disk"""

    CPU5C_2_4 = "cpu5c-2-4"
    """2 vCPU, 4GB RAM, max 30GB container disk"""

    CPU5C_4_8 = "cpu5c-4-8"
    """4 vCPU, 8GB RAM, max 60GB container disk"""

    CPU5C_8_16 = "cpu5c-8-16"
    """8 vCPU, 16GB RAM, max 120GB container disk"""


def calculate_max_disk_size(instance_type: CpuInstanceType) -> int:
    """
    Calculate the maximum container disk size for a CPU instance type.

    Formula:
    - CPU3G/CPU3C: vCPU count × 10GB
    - CPU5C: vCPU count × 15GB

    Args:
        instance_type: CPU instance type enum

    Returns:
        Maximum container disk size in GB

    Example:
        >>> calculate_max_disk_size(CpuInstanceType.CPU3G_1_4)
        10
        >>> calculate_max_disk_size(CpuInstanceType.CPU5C_2_4)
        30
    """
    # Parse the instance type string to extract vCPU count
    # Format: "cpu{generation}{type}-{vcpu}-{memory}"
    instance_str = instance_type.value
    parts = instance_str.split("-")

    if len(parts) != 3:
        raise ValueError(f"Invalid instance type format: {instance_str}")

    vcpu_count = int(parts[1])

    # Determine disk multiplier based on generation
    if instance_str.startswith("cpu5c"):
        disk_multiplier = 15  # CPU5C: 15GB per vCPU
    elif instance_str.startswith(("cpu3g", "cpu3c")):
        disk_multiplier = 10  # CPU3G/CPU3C: 10GB per vCPU
    else:
        raise ValueError(f"Unknown CPU generation/type: {instance_str}")

    return vcpu_count * disk_multiplier


# CPU Instance Type Disk Limits (calculated programmatically)
CPU_INSTANCE_DISK_LIMITS = {
    instance_type: calculate_max_disk_size(instance_type)
    for instance_type in CpuInstanceType
}


def get_max_disk_size_for_instances(
    instance_types: Optional[List[CpuInstanceType]],
) -> Optional[int]:
    """
    Calculate the maximum container disk size for a list of CPU instance types.

    Returns the minimum disk limit across all instance types to ensure compatibility
    with all specified instances.

    Args:
        instance_types: List of CPU instance types, or None

    Returns:
        Maximum allowed disk size in GB, or None if no CPU instances specified

    Example:
        >>> get_max_disk_size_for_instances([CpuInstanceType.CPU3G_1_4])
        10
        >>> get_max_disk_size_for_instances([CpuInstanceType.CPU3G_1_4, CpuInstanceType.CPU3G_2_8])
        10
    """
    if not instance_types:
        return None

    disk_limits = [
        CPU_INSTANCE_DISK_LIMITS[instance_type] for instance_type in instance_types
    ]
    return min(disk_limits)

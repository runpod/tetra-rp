from enum import Enum


class CpuInstanceType(str, Enum):
    """Valid CPU instance types."""

    # Format: {generation}{type}-{vcpu}-{memory_gb}
    CPU3G_1_2 = "cpu3g-1-2"  # 3rd gen general purpose, 1 vCPU, 2GB RAM
    CPU3G_2_4 = "cpu3g-2-4"  # 3rd gen general purpose, 2 vCPU, 4GB RAM
    CPU3G_4_8 = "cpu3g-4-8"  # 3rd gen general purpose, 4 vCPU, 8GB RAM
    CPU3G_8_16 = "cpu3g-8-16"  # 3rd gen general purpose, 8 vCPU, 16GB RAM

    CPU3C_1_2 = "cpu3c-1-2"  # 3rd gen compute-optimized, 1 vCPU, 2GB RAM
    CPU3C_2_4 = "cpu3c-2-4"  # 3rd gen compute-optimized, 2 vCPU, 4GB RAM
    CPU3C_4_8 = "cpu3c-4-8"  # 3rd gen compute-optimized, 4 vCPU, 8GB RAM
    CPU3C_8_16 = "cpu3c-8-16"  # 3rd gen compute-optimized, 8 vCPU, 16GB RAM

    CPU5G_1_4 = "cpu5g-1-4"  # 5th gen general purpose, 1 vCPU, 4GB RAM
    CPU5G_2_8 = "cpu5g-2-8"  # 5th gen general purpose, 2 vCPU, 8GB RAM
    CPU5G_4_16 = "cpu5g-4-16"  # 5th gen general purpose, 4 vCPU, 16GB RAM
    CPU5G_8_32 = "cpu5g-8-32"  # 5th gen general purpose, 8 vCPU, 32GB RAM

    CPU5C_1_4 = "cpu5c-1-4"  # 5th gen compute-optimized, 1 vCPU, 4GB RAM
    CPU5C_2_8 = "cpu5c-2-8"  # 5th gen compute-optimized, 2 vCPU, 8GB RAM
    CPU5C_4_16 = "cpu5c-4-16"  # 5th gen compute-optimized, 4 vCPU, 16GB RAM
    CPU5C_8_32 = "cpu5c-8-32"  # 5th gen compute-optimized, 8 vCPU, 32GB RAM

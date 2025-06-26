from enum import Enum


class CpuInstanceType(str, Enum):
    """Valid CPU instance types.

    Format: {generation}{type}-{vcpu}-{memory_gb}
    Based on Runpod backend validation logic:
    - memoryInGb = vcpuCount * flavor.ramMultiplier

    RAM Multipliers (DEV environment):
    - cpu3g: 4.0 (1 vCPU = 4GB, 2 vCPU = 8GB, etc.)
    - cpu3c: 2.0 (1 vCPU = 2GB, 2 vCPU = 4GB, etc.)
    - cpu5c: 2.0 (1 vCPU = 2GB, 2 vCPU = 4GB, etc.)
    - cpu5g: Not available
    """

    # 3rd Generation General Purpose (RAM multiplier: 4.0)
    CPU3G_1_4 = "cpu3g-1-4"  # 1 vCPU, 4GB RAM
    CPU3G_2_8 = "cpu3g-2-8"  # 2 vCPU, 8GB RAM
    CPU3G_4_16 = "cpu3g-4-16"  # 4 vCPU, 16GB RAM
    CPU3G_8_32 = "cpu3g-8-32"  # 8 vCPU, 32GB RAM

    # 3rd Generation Compute-Optimized (RAM multiplier: 2.0)
    CPU3C_1_2 = "cpu3c-1-2"  # 1 vCPU, 2GB RAM
    CPU3C_2_4 = "cpu3c-2-4"  # 2 vCPU, 4GB RAM
    CPU3C_4_8 = "cpu3c-4-8"  # 4 vCPU, 8GB RAM
    CPU3C_8_16 = "cpu3c-8-16"  # 8 vCPU, 16GB RAM

    # 5th Generation Compute-Optimized (RAM multiplier: 2.0)
    CPU5C_1_2 = "cpu5c-1-2"  # 1 vCPU, 2GB RAM
    CPU5C_2_4 = "cpu5c-2-4"  # 2 vCPU, 4GB RAM
    CPU5C_4_8 = "cpu5c-4-8"  # 4 vCPU, 8GB RAM
    CPU5C_8_16 = "cpu5c-8-16"  # 8 vCPU, 16GB RAM

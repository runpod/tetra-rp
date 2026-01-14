from typing import Optional, List
from pydantic import BaseModel
from enum import Enum


class GpuLowestPrice(BaseModel):
    minimumBidPrice: Optional[float] = None
    uninterruptablePrice: Optional[float] = None


class GpuTypeModel(BaseModel):
    id: str
    displayName: str
    memoryInGb: int


class GpuTypeDetail(GpuTypeModel):
    communityCloud: Optional[bool] = None
    communityPrice: Optional[float] = None
    communitySpotPrice: Optional[float] = None
    cudaCores: Optional[int] = None
    lowestPrice: Optional[GpuLowestPrice] = None
    manufacturer: Optional[str] = None
    maxGpuCount: Optional[int] = None
    oneMonthPrice: Optional[float] = None
    oneWeekPrice: Optional[float] = None
    secureCloud: Optional[bool] = None
    securePrice: Optional[float] = None
    secureSpotPrice: Optional[float] = None
    threeMonthPrice: Optional[float] = None


# TODO: this should be fetched from an API
class GpuGroup(Enum):
    ANY = "any"
    """Any GPU"""

    ADA_24 = "ADA_24"
    """NVIDIA GeForce RTX 4090"""

    ADA_32_PRO = "ADA_32_PRO"
    """NVIDIA GeForce RTX 5090"""

    ADA_48_PRO = "ADA_48_PRO"
    """NVIDIA RTX 6000 Ada Generation, NVIDIA L40, NVIDIA L40S"""

    ADA_80_PRO = "ADA_80_PRO"
    """NVIDIA H100 PCIe, NVIDIA H100 80GB HBM3, NVIDIA H100 NVL"""

    AMPERE_16 = "AMPERE_16"
    """NVIDIA RTX A4000, NVIDIA RTX A4500, NVIDIA RTX 4000 Ada Generation, NVIDIA RTX 2000 Ada Generation"""

    AMPERE_24 = "AMPERE_24"
    """NVIDIA RTX A5000, NVIDIA L4, NVIDIA GeForce RTX 3090"""

    AMPERE_48 = "AMPERE_48"
    """NVIDIA A40, NVIDIA RTX A6000"""

    AMPERE_80 = "AMPERE_80"
    """NVIDIA A100 80GB PCIe, NVIDIA A100-SXM4-80GB"""

    HOPPER_141 = "HOPPER_141"
    """NVIDIA H200"""

    @classmethod
    def all(cls) -> List["GpuGroup"]:
        """Returns all GPU groups."""
        return [cls.AMPERE_48] + [g for g in cls if g != cls.ANY]

    @classmethod
    def to_gpu_ids_str(cls, gpu_types: List[GpuType | GpuGroup]) -> str:
        """
        The API expects a comma-separated list of pool IDs, with GPU ID negations (-4090, -3090, etc.). So to convert a list of GPU types to a string of pool IDs, we need to:
        1. Convert the GPU types to pool IDs
        2. Add a negation for each GPU type that is not in the list
        3. Join the pool IDs with a comma
        """
        pool_ids = set()

        for gpu_type in gpu_types:
            if isinstance(gpu_type, GpuGroup):
                pool_id = gpu_type.value
            else:
                pool_id = _pool_from_gpu_type(gpu_type)

            if pool_id:
                pool_ids.add(pool_id)

        for pool_id in pool_ids:
            for gpu_type in POOLS_TO_TYPES[pool_id]:
                if gpu_type not in gpu_types:
                    pool_ids.add(f"-{gpu_type}")

        return ",".join(pool_ids)

    @classmethod
    def from_gpu_ids_str(cls, gpu_ids_str: str) -> List[GpuGroup | GpuType]:
        """
        Convert a comma-separated list of pool IDs to a list of GPU types.
        """
        ids = gpu_ids_str.split(",")
        pool_ids = []
        gpu_types = []
        negated_gpu_types = []
        for id in ids:
            if id.startswith("-") and GpuType.is_gpu_type(id[1:]):
                negated_gpu_types.append(GpuType(id[1:]))
            elif GpuType.is_gpu_type(id):
                gpu_types.append(GpuType(id))
            else:
                pool_ids.append(id)

        ids = []

        for pool_id in pool_ids:
            pool_gpus = POOLS_TO_TYPES[pool_id]
            # check if there are any negated gpu types in the pool
            if any(gpu_type in negated_gpu_types for gpu_type in pool_gpus):
                # add the gpu types that are not in the negated gpu types
                ids.extend(
                    [
                        gpu_type
                        for gpu_type in pool_gpus
                        if gpu_type not in negated_gpu_types
                    ]
                )
            else:
                ids.extend(pool_id)

        ids.extend(gpu_types)
        return ids


# TODO: fetch from central registry at some point
class GpuType(Enum):
    ANY = "any"
    """Any GPU"""

    A100_PCIE_40GB = "A100-PCIE-40GB"
    AMD_INSTINCT_MI300X_OAM = "AMD Instinct MI300X OAM"
    GEFORCE_RTX_3070 = "GeForce RTX 3070"
    GEFORCE_RTX_3080 = "GeForce RTX 3080"
    GEFORCE_RTX_3090 = "GeForce RTX 3090"
    NVIDIA_A100_80GB_PCIe = "NVIDIA A100 80GB PCIe"
    NVIDIA_A100_PCIE_40GB = "NVIDIA A100-PCIE-40GB"
    NVIDIA_A100_SXM4_40GB = "NVIDIA A100-SXM4-40GB"
    NVIDIA_A100_SXM4_80GB = "NVIDIA A100-SXM4-80GB"
    NVIDIA_A30 = "NVIDIA A30"
    NVIDIA_A40 = "NVIDIA A40"
    NVIDIA_A5000_ADA = "NVIDIA A5000 Ada"
    NVIDIA_B200 = "NVIDIA B200"
    NVIDIA_GEFORCE_GT_1030 = "NVIDIA GeForce GT 1030"
    NVIDIA_GEFORCE_GTX_1050_TI = "NVIDIA GeForce GTX 1050 Ti"
    NVIDIA_GEFORCE_GTX_1060_6GB = "NVIDIA GeForce GTX 1060 6GB"
    NVIDIA_GEFORCE_GTX_1070_TI = "NVIDIA GeForce GTX 1070 Ti"
    NVIDIA_GEFORCE_GTX_1080_TI = "NVIDIA GeForce GTX 1080 Ti"
    NVIDIA_GEFORCE_GTX_1660 = "NVIDIA GeForce GTX 1660"
    NVIDIA_GEFORCE_GTX_980 = "NVIDIA GeForce GTX 980"
    NVIDIA_GEFORCE_RTX_3060 = "NVIDIA GeForce RTX 3060"
    NVIDIA_GEFORCE_RTX_3060_TI = "NVIDIA GeForce RTX 3060 Ti"
    NVIDIA_GEFORCE_RTX_3070 = "NVIDIA GeForce RTX 3070"
    NVIDIA_GEFORCE_RTX_3070_TI = "NVIDIA GeForce RTX 3070 Ti"
    NVIDIA_GEFORCE_RTX_3080 = "NVIDIA GeForce RTX 3080"
    NVIDIA_GEFORCE_RTX_3080_TI = "NVIDIA GeForce RTX 3080 Ti"
    NVIDIA_GEFORCE_RTX_3080TI = "NVIDIA GeForce RTX 3080TI"
    NVIDIA_GEFORCE_RTX_3090 = "NVIDIA GeForce RTX 3090"
    NVIDIA_GEFORCE_RTX_3090_TI = "NVIDIA GeForce RTX 3090 Ti"
    NVIDIA_GEFORCE_RTX_4070_TI = "NVIDIA GeForce RTX 4070 Ti"
    NVIDIA_GEFORCE_RTX_4080 = "NVIDIA GeForce RTX 4080"
    NVIDIA_GEFORCE_RTX_4080_SUPER = "NVIDIA GeForce RTX 4080 SUPER"
    NVIDIA_GEFORCE_RTX_4090 = "NVIDIA GeForce RTX 4090"
    NVIDIA_GEFORCE_RTX_4090_TI = "NVIDIA GeForce RTX 4090 Ti"
    NVIDIA_GEFORCE_RTX_5070_TI = "NVIDIA GeForce RTX 5070 Ti"
    NVIDIA_GEFORCE_RTX_5080 = "NVIDIA GeForce RTX 5080"
    NVIDIA_GEFORCE_RTX_5090 = "NVIDIA GeForce RTX 5090"
    NVIDIA_GRAPHICS_DEVICE = "NVIDIA Graphics Device"
    NVIDIA_H100_80GB_HBM3 = "NVIDIA H100 80GB HBM3"
    NVIDIA_H100_NVL = "NVIDIA H100 NVL"
    NVIDIA_H100_PCIe = "NVIDIA H100 PCIe"
    NVIDIA_H200 = "NVIDIA H200"
    NVIDIA_H200_NVL = "NVIDIA H200 NVL"
    NVIDIA_L4 = "NVIDIA L4"
    NVIDIA_L40 = "NVIDIA L40"
    NVIDIA_L40S = "NVIDIA L40S"
    NVIDIA_PH402_SKU_200 = "NVIDIA PH402 SKU 200"
    NVIDIA_RTX_2000_ADA_GENERATION = "NVIDIA RTX 2000 Ada Generation"
    NVIDIA_RTX_3080 = "NVIDIA RTX 3080"
    NVIDIA_RTX_3080_TI = "NVIDIA RTX 3080 Ti"
    NVIDIA_RTX_4000_ADA_GENERATION = "NVIDIA RTX 4000 Ada Generation"
    NVIDIA_RTX_4000_SFF_ADA_GENERATION = "NVIDIA RTX 4000 SFF Ada Generation"
    NVIDIA_RTX_4500_ADA_GENERATION = "NVIDIA RTX 4500 Ada Generation"
    NVIDIA_RTX_5000 = "NVIDIA RTX 5000"
    NVIDIA_RTX_5000_ADA_GENERATION = "NVIDIA RTX 5000 Ada Generation"
    NVIDIA_RTX_6000_ADA_GENERATION = "NVIDIA RTX 6000 Ada Generation"
    NVIDIA_RTX_A2000 = "NVIDIA RTX A2000"
    NVIDIA_RTX_A2000_12GB = "NVIDIA RTX A2000 12GB"
    NVIDIA_RTX_A30 = "NVIDIA RTX A30"
    NVIDIA_RTX_A4000 = "NVIDIA RTX A4000"
    NVIDIA_RTX_A4500 = "NVIDIA RTX A4500"
    NVIDIA_RTX_A5000 = "NVIDIA RTX A5000"
    NVIDIA_RTX_A5000_ADA = "NVIDIA RTX A5000 Ada"
    NVIDIA_RTX_A5000_ADA_GENERATION = "NVIDIA RTX A5000 Ada Generation"
    NVIDIA_RTX_A6000 = "NVIDIA RTX A6000"
    NVIDIA_RTX_PRO_2000_BLACKWELL = "NVIDIA RTX PRO 2000 Blackwell"
    NVIDIA_RTX_PRO_4000_BLACKWELL = "NVIDIA RTX PRO 4000 Blackwell"
    NVIDIA_RTX_PRO_6000_BLACKWELL_MAX_Q_WORKSTATION_EDITION = (
        "NVIDIA RTX PRO 6000 Blackwell Max-Q Workstation Edition"
    )
    NVIDIA_RTX_PRO_6000_BLACKWELL_SERVER_EDITION = (
        "NVIDIA RTX PRO 6000 Blackwell Server Edition"
    )
    NVIDIA_RTX_PRO_6000_BLACKWELL_WORKSTATION_EDITION = (
        "NVIDIA RTX PRO 6000 Blackwell Workstation Edition"
    )
    NVIDIA_QUADRO_GV100 = "Quadro GV100"
    NVIDIA_QUADRO_RTX_4000 = "Quadro RTX 4000"
    NVIDIA_QUADRO_RTX_5000 = "Quadro RTX 5000"
    NVIDIA_QUADRO_RTX_6000 = "Quadro RTX 6000"
    NVIDIA_TESLA_K80 = "Tesla K80"
    NVIDIA_TESLA_T4 = "Tesla T4"
    NVIDIA_TESLA_V100_FHHL_16GB = "Tesla V100-FHHL-16GB"
    NVIDIA_TESLA_V100_PCIE_16GB = "Tesla V100-PCIE-16GB"
    NVIDIA_TESLA_V100_PCIE_32GB = "Tesla V100-PCIE-32GB"
    NVIDIA_TESLA_V100_SMX2_16GB = "Tesla V100-SMX2-16GB"
    NVIDIA_TESLA_V100_SXM2_16GB = "Tesla V100-SXM2-16GB"
    NVIDIA_TESLA_V100_SXM2_32GB = "Tesla V100-SXM2-32GB"
    NVIDIA_TESLA_V100_SXM3_32GB = "Tesla V100-SXM3-32GB"
    NVIDIA_TESLA_V100_PCIE_32GB = "Testa V100-PCIE-32GB"
    V100_PCIE_16GB = "V100-PCIE-16GB"

    @classmethod
    def all(cls) -> List["GpuType"]:
        """Returns all GPU types."""
        return [g for g in cls if g != cls.ANY]

    @classmethod
    def is_gpu_type(cls, gpu_type: str) -> bool:
        """
        Check if a string is a valid GPU type.
        """
        return gpu_type in cls.__members__


POOLS_TO_TYPES = {
    GpuGroup.ADA_24: [GpuType.NVIDIA_GEFORCE_RTX_4090],
    GpuGroup.ADA_32_PRO: [GpuType.NVIDIA_GEFORCE_RTX_5090],
    GpuGroup.ADA_48_PRO: [GpuType.NVIDIA_RTX_6000_ADA_GENERATION],
    GpuGroup.ADA_80_PRO: [GpuType.NVIDIA_H100_80GB_HBM3],
    GpuGroup.AMPERE_16: [
        GpuType.NVIDIA_RTX_A4000,
        GpuType.NVIDIA_RTX_A4500,
        GpuType.NVIDIA_RTX_4000_ADA_GENERATION,
        GpuType.NVIDIA_RTX_2000_ADA_GENERATION,
    ],
    GpuGroup.AMPERE_24: [
        GpuType.NVIDIA_RTX_A5000,
        GpuType.NVIDIA_L4,
        GpuType.NVIDIA_GEFORCE_RTX_3090,
    ],
    GpuGroup.AMPERE_48: [GpuType.NVIDIA_A40, GpuType.NVIDIA_RTX_A6000],
    GpuGroup.AMPERE_80: [GpuType.NVIDIA_A100_80GB_PCIe, GpuType.NVIDIA_A100_SXM4_80GB],
    GpuGroup.HOPPER_141: [GpuType.NVIDIA_H200],
}


def _pool_from_gpu_type(gpu_type: GpuType) -> str:
    for group, types in POOLS_TO_TYPES.items():
        if gpu_type in types:
            return group
    return None

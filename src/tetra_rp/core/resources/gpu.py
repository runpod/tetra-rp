from typing import Optional
from pydantic import BaseModel
from enum import Enum

class GpuLowestPrice(BaseModel):
    minimumBidPrice: Optional[float] = None
    uninterruptablePrice: Optional[float] = None


class GpuType(BaseModel):
    id: str
    displayName: str
    memoryInGb: int


class GpuTypeDetail(GpuType):
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
class GpuGroups(Enum):
    ADA_24 = "ADA_24" # "NVIDIA GeForce RTX 4090"
    ADA_48_PRO = "ADA_48_PRO" # "NVIDIA RTX 6000 Ada Generation, NVIDIA L40, NVIDIA L40S"
    ADA_80_PRO = "ADA_80_PRO" # "NVIDIA H100 PCIe, NVIDIA H100 80GB HBM3, NVIDIA H100 NVL"
    AMPERE_16 = "AMPERE_16" # "NVIDIA RTX A4000, NVIDIA RTX A4500, NVIDIA RTX 4000 Ada Generation, NVIDIA RTX 2000 Ada Generation"
    AMPERE_24 = "AMPERE_24" # "NVIDIA RTX A5000, NVIDIA L4, NVIDIA GeForce RTX 3090"
    AMPERE_48 = "AMPERE_48" # "NVIDIA A40, NVIDIA RTX A6000"
    AMPERE_80 = "AMPERE_80" # "NVIDIA A100 80GB PCIe, NVIDIA A100-SXM4-80GB"
    HOPPER_141 = "HOPPER_141" # "NVIDIA H200"

    @classmethod
    def list(cls) -> list[str]:
        """Returns all GPU group values as a list of strings."""
        return [g.value for g in cls]

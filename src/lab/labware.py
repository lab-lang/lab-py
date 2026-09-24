"""Reusable logical labware specifications, independent of a robot or deck site."""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class LabwareKind(Enum):
    COLD_BLOCK = "cold_block"
    PCR_PLATE = "pcr_plate"
    TUBE_RACK = "tube_rack"
    CONICAL_RACK = "conical_rack"
    CULTURE_PLATE = "culture_plate"


@dataclass(frozen=True, slots=True, kw_only=True)
class LabwareSpec:
    """A labware family, well geometry, and logical capacity per well in microliters.

    Backends select physical labware and validate its usable capacities separately.
    """

    kind: LabwareKind
    rows: int
    columns: int
    capacity_ul: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.kind, LabwareKind):
            raise TypeError("Labware kind must be a LabwareKind member.")
        if type(self.rows) is not int or type(self.columns) is not int:
            raise ValueError("Rows and columns must be positive integers.")
        if self.rows < 1 or self.columns < 1 or self.rows > 26:
            raise ValueError("Rows and columns must be positive integers, with at most 26 rows.")
        if (
            not isinstance(self.capacity_ul, Decimal)
            or not self.capacity_ul.is_finite()
            or self.capacity_ul <= 0
        ):
            raise ValueError("Capacity must be a positive finite Decimal number of microliters.")


@dataclass(frozen=True, slots=True, kw_only=True)
class ContainerSpec:
    """A named logical container. Allocation can describe it before choosing a site."""

    id: str
    labware: LabwareSpec

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("Container id must be nonempty text.")
        if not isinstance(self.labware, LabwareSpec):
            raise TypeError("Container labware must be a LabwareSpec.")


COLD_BLOCK_24 = LabwareSpec(
    kind=LabwareKind.COLD_BLOCK, rows=4, columns=6, capacity_ul=Decimal(1500)
)
PCR_PLATE_96 = LabwareSpec(kind=LabwareKind.PCR_PLATE, rows=8, columns=12, capacity_ul=Decimal(100))
TUBE_RACK_24 = LabwareSpec(kind=LabwareKind.TUBE_RACK, rows=4, columns=6, capacity_ul=Decimal(1500))
CONICAL_RACK_15 = LabwareSpec(
    kind=LabwareKind.CONICAL_RACK, rows=3, columns=5, capacity_ul=Decimal(15000)
)
CULTURE_PLATE_96 = LabwareSpec(
    kind=LabwareKind.CULTURE_PLATE, rows=8, columns=12, capacity_ul=Decimal(200)
)

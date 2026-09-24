"""Column-major well addresses, matching Opentrons ``labware.wells()``."""

from decimal import Decimal

from lab.protocol import Plate, Well
from lab.units import magnitude


def microliters(value: object) -> Decimal:
    return magnitude(value, "microliter")


def uri_name(uri: str) -> str:
    """Name segment used by the OT-2 assembly and transformation protocols."""
    if "/" in uri:
        return uri.split("/")[-2]
    return uri


def well_at(plate: Plate, index: int) -> Well:
    rows = plate.shape[0]
    count = rows * plate.shape[1]
    if index < 0 or index >= count:
        raise ValueError(f"Well index {index} is outside {plate.name}")
    row = index % rows
    column = index // rows
    return plate[f"{chr(65 + row)}{column + 1}"]


def well_name(index: int, rows: int = 8) -> str:
    return f"{chr(65 + index % rows)}{index // rows + 1}"

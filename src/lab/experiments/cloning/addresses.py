"""Column-major well addresses, matching Opentrons ``labware.wells()``."""

from decimal import Decimal

from lab.protocol import Plate, Well
from lab.units import magnitude


def microliters(value: object) -> Decimal:
    return magnitude(value, "microliter")


def uri_name(uri: str) -> str:
    """Name segment of a material URI.

    A versioned identity such as ``https://sbolcanvas.org/pSB1C3/1`` uses the segment before
    the version. An unversioned identity such as ``https://vsv.bio/backbone/pvsv-dg`` uses the
    last segment.
    """
    parts = [part for part in uri.split("/") if part]
    if parts and parts[0].endswith(":"):
        parts = parts[1:]
    if not parts:
        return uri
    if len(parts) >= 2 and parts[-1].isdigit():
        return parts[-2]
    return parts[-1]


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

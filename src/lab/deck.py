"""A handler-neutral deck. A backend assigns slots, carriers, and labware."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

Kind = Literal["cold_block", "pcr_plate", "tube_rack", "conical_rack", "culture_plate"]
Site = Literal[
    "temperature_module",
    "thermocycler",
    "plates",
    "more_plates",
    "tube_rack",
    "reservoir",
]

_KINDS = frozenset({"cold_block", "pcr_plate", "tube_rack", "conical_rack", "culture_plate"})
_SITES = frozenset(
    {"temperature_module", "thermocycler", "plates", "more_plates", "tube_rack", "reservoir"}
)
_PAIRS = frozenset(
    {
        ("cold_block", "temperature_module"),
        ("pcr_plate", "thermocycler"),
        ("culture_plate", "thermocycler"),
        ("pcr_plate", "plates"),
        ("pcr_plate", "more_plates"),
        ("tube_rack", "tube_rack"),
        ("conical_rack", "reservoir"),
    }
)


@dataclass(frozen=True, slots=True, kw_only=True)
class Container:
    """One container's geometry, kind, and site.

    ``plates`` and ``more_plates`` are the two open-deck plate runs. ``tube_rack``
    and ``reservoir`` are the holder and the large-volume rack. A temperature
    module and a thermocycler each hold one container.
    """

    id: str
    rows: int
    columns: int
    capacity_ul: Decimal
    kind: Kind
    site: Site

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("Container id must be nonempty text.")
        if self.kind not in _KINDS or self.site not in _SITES:
            raise ValueError("Unknown container kind or site.")
        if (self.kind, self.site) not in _PAIRS:
            raise ValueError(f"A {self.kind} cannot sit on {self.site}.")
        if type(self.rows) is not int or type(self.columns) is not int:
            raise ValueError("Rows and columns must be positive integers.")
        if self.rows < 1 or self.columns < 1 or self.rows > 26:
            raise ValueError("Rows and columns must be positive integers.")
        if type(self.capacity_ul) is not Decimal or self.capacity_ul <= 0:
            raise ValueError("Capacity must be a positive number of microliters.")


@dataclass(frozen=True, slots=True, kw_only=True)
class Deck:
    """Containers a protocol uses. Compilation lowers the deck for one handler."""

    containers: tuple[Container, ...]

    def __post_init__(self) -> None:
        if not self.containers:
            raise ValueError("A deck needs at least one container.")
        ids = [container.id for container in self.containers]
        if len(ids) != len(set(ids)):
            raise ValueError("Deck container ids must be unique.")
        for site in ("temperature_module", "thermocycler"):
            count = sum(container.site == site for container in self.containers)
            if count > 1:
                raise ValueError(f"A deck has one {site.replace('_', ' ')}.")

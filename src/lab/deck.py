"""A handler-neutral deck. A backend assigns slots, carriers, and labware."""

from dataclasses import dataclass
from enum import Enum

from lab.labware import ContainerSpec, LabwareKind


class DeckSite(Enum):
    """Logical placement groups. Each backend owns their physical positions."""

    TEMPERATURE_MODULE = "temperature_module"
    THERMOCYCLER = "thermocycler"
    PLATES = "plates"
    MORE_PLATES = "more_plates"
    TUBE_RACK = "tube_rack"
    RESERVOIR = "reservoir"


_COMPATIBLE_KINDS = {
    DeckSite.TEMPERATURE_MODULE: frozenset({LabwareKind.COLD_BLOCK}),
    DeckSite.THERMOCYCLER: frozenset({LabwareKind.PCR_PLATE, LabwareKind.CULTURE_PLATE}),
    DeckSite.PLATES: frozenset({LabwareKind.PCR_PLATE}),
    DeckSite.MORE_PLATES: frozenset({LabwareKind.PCR_PLATE}),
    DeckSite.TUBE_RACK: frozenset({LabwareKind.TUBE_RACK}),
    DeckSite.RESERVOIR: frozenset({LabwareKind.CONICAL_RACK}),
}


@dataclass(frozen=True, slots=True, kw_only=True)
class Container(ContainerSpec):
    """A named container placed at a typed logical site.

    ``DeckSite.PLATES`` and ``DeckSite.MORE_PLATES`` are the two open-deck plate
    runs. ``DeckSite.TUBE_RACK`` and ``DeckSite.RESERVOIR`` are the holder and the
    large-volume rack. A temperature module and a thermocycler each hold one container.
    """

    site: DeckSite

    def __post_init__(self) -> None:
        ContainerSpec.__post_init__(self)
        if not isinstance(self.site, DeckSite):
            raise TypeError("Container site must be a DeckSite member.")
        if self.labware.kind not in _COMPATIBLE_KINDS[self.site]:
            raise ValueError(f"A {self.labware.kind.value} cannot sit on {self.site.value}.")


@dataclass(frozen=True, slots=True, kw_only=True)
class Deck:
    """Containers a protocol uses. Compilation lowers the deck for one handler."""

    containers: tuple[Container, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.containers, tuple) or any(
            not isinstance(container, Container) for container in self.containers
        ):
            raise TypeError("Deck containers must be a tuple of placed Container objects.")
        if not self.containers:
            raise ValueError("A deck needs at least one container.")
        ids = [container.id for container in self.containers]
        if len(ids) != len(set(ids)):
            raise ValueError("Deck container ids must be unique.")
        for site in (DeckSite.TEMPERATURE_MODULE, DeckSite.THERMOCYCLER):
            count = sum(container.site == site for container in self.containers)
            if count > 1:
                raise ValueError(f"A deck has one {site.value.replace('_', ' ')}.")

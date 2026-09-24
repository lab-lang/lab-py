"""Logical containers and Lab-owned physical layouts for liquid handlers."""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any

from lab.equipment import (
    CARRIER_SITE_COUNTS,
    MODULE_SITE_COUNTS,
    CarrierModel,
    LabwareModel,
    LiquidHandler,
    ModuleModel,
    Mount,
    PipetteModel,
    TipRackModel,
)
from lab.labware import ContainerSpec, LabwareKind


class DeckSite(Enum):
    """Logical placement groups used by built-in layout presets."""

    TEMPERATURE_MODULE = "temperature_module"
    THERMOCYCLER = "thermocycler"
    PLATES = "plates"
    MORE_PLATES = "more_plates"
    TUBE_RACK = "tube_rack"
    RESERVOIR = "reservoir"


_COMPATIBLE_KINDS = {
    DeckSite.TEMPERATURE_MODULE: frozenset({LabwareKind.COLD_BLOCK}),
    DeckSite.THERMOCYCLER: frozenset({LabwareKind.PCR_PLATE, LabwareKind.CULTURE_PLATE}),
    DeckSite.PLATES: frozenset({LabwareKind.PLATE, LabwareKind.PCR_PLATE}),
    DeckSite.MORE_PLATES: frozenset({LabwareKind.PLATE, LabwareKind.PCR_PLATE}),
    DeckSite.TUBE_RACK: frozenset({LabwareKind.TUBE_RACK}),
    DeckSite.RESERVOIR: frozenset({LabwareKind.CONICAL_RACK}),
}


@dataclass(frozen=True, slots=True, kw_only=True)
class Container(ContainerSpec):
    """A named container assigned to a logical placement group.

    ``DeckSite.PLATES`` and ``DeckSite.MORE_PLATES`` are the two open-deck plate
    runs. ``DeckSite.TUBE_RACK`` and ``DeckSite.RESERVOIR`` are the holder and the
    large-volume rack. Explicit layouts specify the actual holders and devices.
    """

    site: DeckSite

    def __post_init__(self) -> None:
        ContainerSpec.__post_init__(self)
        if not isinstance(self.site, DeckSite):
            raise TypeError("Container site must be a DeckSite member.")
        if self.labware.kind not in _COMPATIBLE_KINDS[self.site]:
            raise ValueError(f"A {self.labware.kind.value} cannot sit on {self.site.value}.")


def _name(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Equipment and container identifiers must be nonempty text.")


def _tuple(values: tuple[Any, ...], member: type, label: str) -> None:
    if not isinstance(values, tuple) or any(not isinstance(value, member) for value in values):
        raise TypeError(f"{label} must be a tuple of {member.__name__} objects.")


@dataclass(frozen=True, slots=True)
class Slot:
    name: str

    def __post_init__(self) -> None:
        _name(self.name)


@dataclass(frozen=True, slots=True)
class Rail:
    index: int

    def __post_init__(self) -> None:
        if type(self.index) is not int or self.index < 1:
            raise ValueError("Rail index must be a positive integer.")


@dataclass(frozen=True, slots=True)
class HolderSite:
    holder: str
    index: int = 0

    def __post_init__(self) -> None:
        _name(self.holder)
        if type(self.index) is not int or self.index < 0:
            raise ValueError("Holder site index must be a nonnegative integer.")


Position = Slot | Rail | HolderSite


@dataclass(frozen=True, slots=True, kw_only=True)
class Carrier:
    id: str
    model: CarrierModel
    location: Position


@dataclass(frozen=True, slots=True, kw_only=True)
class Module:
    id: str
    model: ModuleModel
    location: Position


@dataclass(frozen=True, slots=True, kw_only=True)
class TipRack:
    id: str
    model: TipRackModel
    location: Position


@dataclass(frozen=True, slots=True, kw_only=True)
class Placement:
    """Bind a logical container to a physical model and location in a layout.

    ``wells`` optionally lists physical well names in logical row-major order.
    """

    container: str
    model: LabwareModel
    location: Position
    wells: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class Pipette:
    model: PipetteModel
    mount: Mount
    tip_racks: tuple[str, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class Channel:
    """An independently addressable channel; limits are in microliters."""

    index: int
    min_volume_ul: Decimal
    max_volume_ul: Decimal
    tip_racks: tuple[str, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class DeckLayout:
    """A physical configuration expressed entirely in Lab types.

    Targets validate supported equipment, positions, footprints, and capabilities.
    External thermal resources explicitly require a runtime device handoff.
    """

    liquid_handler: LiquidHandler
    placements: tuple[Placement, ...]
    carriers: tuple[Carrier, ...] = ()
    modules: tuple[Module, ...] = ()
    tip_racks: tuple[TipRack, ...] = ()
    pipettes: tuple[Pipette, ...] = ()
    channels: tuple[Channel, ...] = ()
    external_thermal_resources: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.liquid_handler, LiquidHandler):
            raise TypeError("A layout requires a LiquidHandler member.")
        for values, member in (
            (self.placements, Placement),
            (self.carriers, Carrier),
            (self.modules, Module),
            (self.tip_racks, TipRack),
            (self.pipettes, Pipette),
            (self.channels, Channel),
        ):
            _tuple(values, member, member.__name__)
        equipment: tuple[Carrier | Module | TipRack, ...] = (
            *self.carriers,
            *self.modules,
            *self.tip_racks,
        )
        ids = [item.id for item in equipment]
        for identifier in ids:
            _name(identifier)
        if len(set(ids)) != len(ids):
            raise ValueError("Layout equipment ids must be unique.")
        containers = [item.container for item in self.placements]
        for identifier in containers:
            _name(identifier)
        if len(set(containers)) != len(containers):
            raise ValueError("Each container needs exactly one placement in a layout.")
        if set(ids) & set(containers):
            raise ValueError("Equipment and container ids must be distinct.")
        for values, model_type in (
            (self.carriers, CarrierModel),
            (self.modules, ModuleModel),
            (self.tip_racks, TipRackModel),
            (self.placements, LabwareModel),
        ):
            for model_item in values:
                if not isinstance(model_item.model, model_type):
                    raise TypeError(f"Use a {model_type.__name__} member.")
        holder_items: tuple[Carrier | Module, ...] = (*self.carriers, *self.modules)
        holders = {item.id: item for item in holder_items}
        occupied: set[Position] = set()
        positioned: tuple[Carrier | Module | TipRack | Placement, ...] = (
            *equipment,
            *self.placements,
        )
        for item in positioned:
            position = item.location
            if not isinstance(position, (Slot, Rail, HolderSite)):
                raise TypeError("A location must be a Slot, Rail, or HolderSite.")
            if position in occupied:
                raise ValueError(f"Layout location {position!r} is occupied more than once.")
            occupied.add(position)
            if isinstance(position, HolderSite):
                if position.holder not in holders:
                    raise ValueError(f"Unknown holder {position.holder!r}.")
                holder = holders[position.holder]
                limit = (
                    CARRIER_SITE_COUNTS[holder.model]
                    if isinstance(holder, Carrier)
                    else MODULE_SITE_COUNTS[holder.model]
                )
                if position.index >= limit:
                    raise ValueError(f"Holder {position.holder!r} has {limit} sites.")
        # Reject cycles even when holders were declared in a different order.
        for holder in holders.values():
            seen = {holder.id}
            position = holder.location
            while isinstance(position, HolderSite):
                if position.holder in seen:
                    raise ValueError("Layout holder relationships must not contain a cycle.")
                seen.add(position.holder)
                position = holders[position.holder].location
        for placement in self.placements:
            _tuple(placement.wells, str, "Physical wells")
            if len(set(placement.wells)) != len(placement.wells):
                raise ValueError("Physical well mappings must be unique.")
            for well in placement.wells:
                _name(well)
        tips = {rack.id for rack in self.tip_racks}
        assigned: set[str] = set()
        heads: tuple[Pipette | Channel, ...] = (*self.pipettes, *self.channels)
        for head in heads:
            _tuple(head.tip_racks, str, "Head tip racks")
            if not head.tip_racks or any(rack not in tips for rack in head.tip_racks):
                raise ValueError("Every pipette or channel needs declared tip racks.")
            if len(set(head.tip_racks)) != len(head.tip_racks):
                raise ValueError("A head's tip rack list must not contain duplicates.")
            assigned.update(head.tip_racks)
        if assigned != tips:
            raise ValueError("Every tip rack must be assigned to a pipette or channel.")
        for pipette in self.pipettes:
            if not isinstance(pipette.model, PipetteModel) or not isinstance(pipette.mount, Mount):
                raise TypeError("Use PipetteModel and Mount members.")
        if len({pipette.mount for pipette in self.pipettes}) != len(self.pipettes):
            raise ValueError("Pipette mounts must be unique.")
        for channel in self.channels:
            if type(channel.index) is not int or channel.index < 0:
                raise ValueError("Channel index must be a nonnegative integer.")
            limits = (channel.min_volume_ul, channel.max_volume_ul)
            if any(not isinstance(v, Decimal) or not v.is_finite() or v <= 0 for v in limits):
                raise ValueError("Channel volume limits must be positive finite Decimals.")
            if channel.min_volume_ul > channel.max_volume_ul:
                raise ValueError("Channel minimum volume exceeds maximum volume.")
        if len({channel.index for channel in self.channels}) != len(self.channels):
            raise ValueError("Channel indices must be unique.")
        _tuple(self.external_thermal_resources, str, "External thermal resources")
        if not set(self.external_thermal_resources) <= set(containers):
            raise ValueError("External thermal resources must name placed containers.")


@dataclass(frozen=True, slots=True, kw_only=True)
class Deck:
    """Shared container requirements with optional physical layouts for each handler."""

    containers: tuple[ContainerSpec, ...]
    layouts: tuple[DeckLayout, ...] = ()

    def __post_init__(self) -> None:
        _tuple(self.containers, ContainerSpec, "Deck containers")
        _tuple(self.layouts, DeckLayout, "Deck layouts")
        if not self.containers:
            raise ValueError("A deck needs at least one container.")
        ids = [container.id for container in self.containers]
        if len(ids) != len(set(ids)):
            raise ValueError("Deck container ids must be unique.")
        handlers = [layout.liquid_handler for layout in self.layouts]
        if len(set(handlers)) != len(handlers):
            raise ValueError("A deck can have only one layout per liquid handler.")
        specs = {container.id: container.labware for container in self.containers}
        for layout in self.layouts:
            if {placement.container for placement in layout.placements} != set(ids):
                raise ValueError("Each layout must place exactly the deck's containers.")
            for placement in layout.placements:
                spec = specs[placement.container]
                if placement.wells and len(placement.wells) != spec.rows * spec.columns:
                    raise ValueError("A physical well mapping must cover every logical well.")

    def layout_for(self, liquid_handler: LiquidHandler) -> DeckLayout | None:
        return next(
            (layout for layout in self.layouts if layout.liquid_handler == liquid_handler), None
        )

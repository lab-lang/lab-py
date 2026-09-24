"""Validate a Lab deck and lower its selected layout into a backend configuration."""

from collections.abc import Sequence
from decimal import Decimal

from lab.deck import Container, Deck, DeckLayout, DeckSite, HolderSite
from lab.equipment import LabwareModel, ModuleModel
from lab.labware import LabwareKind
from lab.targets.liquid_handler import LiquidHandler
from lab.targets.opentrons import Opentrons
from lab.targets.opentrons import lower_deck as lower_opentrons
from lab.targets.opentrons import lower_layout as lower_opentrons_layout
from lab.targets.star import STAR
from lab.targets.star import lower_deck as lower_star
from lab.targets.star import lower_layout as lower_star_layout
from lab.validation import CompileError


def lower_deck(
    deck: Deck, liquid_handler: LiquidHandler, volumes: Sequence[Decimal] = ()
) -> Opentrons | STAR:
    """Resolve Lab equipment and placements for the selected liquid handler."""
    if not isinstance(deck, Deck):
        raise TypeError("Pass a Deck.")
    if not isinstance(liquid_handler, LiquidHandler):
        raise TypeError("Pass LiquidHandler.OT2, LiquidHandler.FLEX, or LiquidHandler.STAR.")
    liquid = tuple(volumes)
    layout = deck.layout_for(liquid_handler)
    if layout is not None:
        _validate_requirements(deck, layout)
        if liquid_handler == LiquidHandler.STAR:
            return lower_star_layout(deck, layout)
        return lower_opentrons_layout(layout)
    if deck.layouts:
        raise CompileError(f"No {liquid_handler.value} layout is configured on this Deck.")
    if any(not isinstance(container, Container) for container in deck.containers):
        raise CompileError("Provide a DeckLayout or assign containers to preset DeckSite groups.")
    if liquid_handler == LiquidHandler.OT2:
        return lower_opentrons(deck, robot="OT-2", volumes=liquid)
    if liquid_handler == LiquidHandler.FLEX:
        return lower_opentrons(deck, robot="Flex", volumes=liquid)
    if liquid_handler == LiquidHandler.STAR:
        return lower_star(deck, volumes=liquid)
    raise TypeError("Pass LiquidHandler.OT2, LiquidHandler.FLEX, or LiquidHandler.STAR.")


_MODEL_KINDS = {
    LabwareModel.CORNING_96_360_UL: {LabwareKind.PLATE},
    LabwareModel.NEST_12_RESERVOIR_15_ML: {LabwareKind.RESERVOIR},
    LabwareModel.NEST_96_PCR_100_UL: {LabwareKind.PCR_PLATE, LabwareKind.CULTURE_PLATE},
    LabwareModel.OPENTRONS_96_PCR_200_UL: {LabwareKind.PCR_PLATE, LabwareKind.CULTURE_PLATE},
    LabwareModel.BIORAD_96_PCR_200_UL: {LabwareKind.PCR_PLATE, LabwareKind.CULTURE_PLATE},
    LabwareModel.AZENTA_96_PCR_200_UL: {LabwareKind.PCR_PLATE, LabwareKind.CULTURE_PLATE},
    LabwareModel.OPENTRONS_24_COLD_BLOCK: {LabwareKind.COLD_BLOCK},
    LabwareModel.OPENTRONS_24_TUBE_RACK: {LabwareKind.TUBE_RACK},
    LabwareModel.OPENTRONS_15_CONICAL_RACK: {LabwareKind.CONICAL_RACK},
}


def _validate_requirements(deck: Deck, layout: DeckLayout) -> None:
    specs = {container.id: container for container in deck.containers}
    modules = {module.id: module for module in layout.modules}
    for placement in layout.placements:
        container = specs[placement.container]
        if container.labware.kind not in _MODEL_KINDS[placement.model]:
            raise CompileError(
                f"{container.id}: {placement.model.value} does not satisfy "
                f"the {container.labware.kind.value} requirement."
            )
        site = container.site if isinstance(container, Container) else None
        thermal = container.labware.kind == LabwareKind.COLD_BLOCK or site in (
            DeckSite.TEMPERATURE_MODULE,
            DeckSite.THERMOCYCLER,
        )
        if not thermal or container.id in layout.external_thermal_resources:
            continue
        holder = placement.location.holder if isinstance(placement.location, HolderSite) else None
        module = modules.get(holder) if holder else None
        if module is None:
            raise CompileError(
                f"{container.id} requires a thermal module or external thermal handoff."
            )
        if site == DeckSite.THERMOCYCLER and module.model not in (
            ModuleModel.THERMOCYCLER_GEN1,
            ModuleModel.THERMOCYCLER_GEN2,
        ):
            raise CompileError(f"{container.id} requires a thermocycler.")

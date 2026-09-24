"""Lower one abstract deck for OT-2, Flex, or STAR."""

from collections.abc import Sequence
from decimal import Decimal

from lab.deck import Deck
from lab.targets.liquid_handler import LiquidHandler
from lab.targets.opentrons import Opentrons
from lab.targets.opentrons import lower_deck as lower_opentrons
from lab.targets.star import STAR
from lab.targets.star import lower_deck as lower_star


def lower_deck(
    deck: Deck, liquid_handler: LiquidHandler, volumes: Sequence[Decimal] = ()
) -> Opentrons | STAR:
    """Bind ``deck`` to the labware, modules, and pipettes ``liquid_handler`` uses."""
    if not isinstance(deck, Deck):
        raise TypeError("Pass a Deck.")
    if not isinstance(liquid_handler, LiquidHandler):
        raise TypeError("Pass LiquidHandler.OT2, LiquidHandler.FLEX, or LiquidHandler.STAR.")
    liquid = tuple(volumes)
    if liquid_handler == LiquidHandler.OT2:
        return lower_opentrons(deck, robot="OT-2", volumes=liquid)
    if liquid_handler == LiquidHandler.FLEX:
        return lower_opentrons(deck, robot="Flex", volumes=liquid)
    if liquid_handler == LiquidHandler.STAR:
        return lower_star(deck, volumes=liquid)
    raise TypeError("Pass LiquidHandler.OT2, LiquidHandler.FLEX, or LiquidHandler.STAR.")

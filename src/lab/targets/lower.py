"""Lower one abstract deck for OT-2, Flex, or STAR."""

from collections.abc import Sequence
from decimal import Decimal

from lab.deck import Deck
from lab.targets.handler import Handler
from lab.targets.opentrons import Opentrons
from lab.targets.opentrons import lower_deck as lower_opentrons
from lab.targets.star import STAR
from lab.targets.star import lower_deck as lower_star


def lower_deck(deck: Deck, handler: Handler, volumes: Sequence[Decimal] = ()) -> Opentrons | STAR:
    """Bind ``deck`` to the labware, modules, and pipettes ``handler`` uses."""
    if not isinstance(deck, Deck):
        raise TypeError("Pass a Deck.")
    if not isinstance(handler, Handler):
        raise TypeError("Pass Handler.OT2, Handler.FLEX, or Handler.STAR.")
    liquid = tuple(volumes)
    if handler == Handler.OT2:
        return lower_opentrons(deck, robot="OT-2", volumes=liquid)
    if handler == Handler.FLEX:
        return lower_opentrons(deck, robot="Flex", volumes=liquid)
    if handler == Handler.STAR:
        return lower_star(deck, volumes=liquid)
    raise TypeError("Pass Handler.OT2, Handler.FLEX, or Handler.STAR.")

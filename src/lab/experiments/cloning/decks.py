"""Abstract decks for this experiment.

A deck places named containers using reusable labware specifications and typed sites.
The ids match the plates declared by the stage protocols. Compilation lowers the
deck for an OT-2, a Flex, or a STAR.
"""

from lab.deck import Container, Deck, DeckSite
from lab.labware import (
    COLD_BLOCK_24,
    CONICAL_RACK_15,
    CULTURE_PLATE_96,
    PCR_PLATE_96,
    TUBE_RACK_24,
)


def assembly_deck() -> Deck:
    """Cold reagents beside a PCR plate of assembly products."""
    return Deck(
        containers=(
            Container(
                id="reagents",
                labware=COLD_BLOCK_24,
                site=DeckSite.TEMPERATURE_MODULE,
            ),
            Container(
                id="products",
                labware=PCR_PLATE_96,
                site=DeckSite.THERMOCYCLER,
            ),
        )
    )


def transformation_deck(*, on_module: bool = False) -> Deck:
    """DNA, competent-cell tubes, and a PCR plate of heat-shock reactions.

    ``on_module`` puts the DNA on the temperature module. Leave it false when
    the DNA already occupies a 96-well plate.
    """
    dna = (
        Container(
            id="dna",
            labware=COLD_BLOCK_24,
            site=DeckSite.TEMPERATURE_MODULE,
        )
        if on_module
        else Container(
            id="dna",
            labware=PCR_PLATE_96,
            site=DeckSite.PLATES,
        )
    )
    return Deck(
        containers=(
            dna,
            Container(
                id="tubes",
                labware=TUBE_RACK_24,
                site=DeckSite.TUBE_RACK,
            ),
            Container(
                id="products",
                labware=PCR_PLATE_96,
                site=DeckSite.THERMOCYCLER,
            ),
        )
    )


def plating_deck(*, second_dilution: bool = False, second_agar: bool = False) -> Deck:
    """Cultures, dilution plates, agar, and a broth reservoir."""
    containers = [
        Container(
            id="sources",
            labware=CULTURE_PLATE_96,
            site=DeckSite.THERMOCYCLER,
        ),
        Container(
            id="dilutions",
            labware=PCR_PLATE_96,
            site=DeckSite.PLATES,
        ),
        Container(
            id="agar",
            labware=PCR_PLATE_96,
            site=DeckSite.MORE_PLATES,
        ),
        Container(
            id="broth",
            labware=CONICAL_RACK_15,
            site=DeckSite.RESERVOIR,
        ),
    ]
    if second_dilution:
        containers.append(
            Container(
                id="dilutions_2",
                labware=PCR_PLATE_96,
                site=DeckSite.PLATES,
            )
        )
    if second_agar:
        containers.append(
            Container(
                id="agar_2",
                labware=PCR_PLATE_96,
                site=DeckSite.MORE_PLATES,
            )
        )
    return Deck(containers=tuple(containers))

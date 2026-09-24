"""Abstract decks for this experiment.

A deck names containers by id, geometry, kind, and site. The ids match the
plates declared by the stage protocols. Compilation lowers the deck for an
OT-2, a Flex, or a STAR.
"""

from decimal import Decimal

from lab.deck import Container, Deck


def assembly_deck() -> Deck:
    """Cold reagents beside a PCR plate of assembly products."""
    return Deck(
        containers=(
            Container(
                id="reagents",
                rows=4,
                columns=6,
                capacity_ul=Decimal(1500),
                kind="cold_block",
                site="temperature_module",
            ),
            Container(
                id="products",
                rows=8,
                columns=12,
                capacity_ul=Decimal(100),
                kind="pcr_plate",
                site="thermocycler",
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
            rows=4,
            columns=6,
            capacity_ul=Decimal(1500),
            kind="cold_block",
            site="temperature_module",
        )
        if on_module
        else Container(
            id="dna",
            rows=8,
            columns=12,
            capacity_ul=Decimal(100),
            kind="pcr_plate",
            site="plates",
        )
    )
    return Deck(
        containers=(
            dna,
            Container(
                id="tubes",
                rows=4,
                columns=6,
                capacity_ul=Decimal(1500),
                kind="tube_rack",
                site="tube_rack",
            ),
            Container(
                id="products",
                rows=8,
                columns=12,
                capacity_ul=Decimal(100),
                kind="pcr_plate",
                site="thermocycler",
            ),
        )
    )


def plating_deck(*, second_dilution: bool = False, second_agar: bool = False) -> Deck:
    """Cultures, dilution plates, agar, and a broth reservoir."""
    containers = [
        Container(
            id="sources",
            rows=8,
            columns=12,
            capacity_ul=Decimal(200),
            kind="culture_plate",
            site="thermocycler",
        ),
        Container(
            id="dilutions",
            rows=8,
            columns=12,
            capacity_ul=Decimal(100),
            kind="pcr_plate",
            site="plates",
        ),
        Container(
            id="agar",
            rows=8,
            columns=12,
            capacity_ul=Decimal(100),
            kind="pcr_plate",
            site="more_plates",
        ),
        Container(
            id="broth",
            rows=3,
            columns=5,
            capacity_ul=Decimal(15000),
            kind="conical_rack",
            site="reservoir",
        ),
    ]
    if second_dilution:
        containers.append(
            Container(
                id="dilutions_2",
                rows=8,
                columns=12,
                capacity_ul=Decimal(100),
                kind="pcr_plate",
                site="plates",
            )
        )
    if second_agar:
        containers.append(
            Container(
                id="agar_2",
                rows=8,
                columns=12,
                capacity_ul=Decimal(100),
                kind="pcr_plate",
                site="more_plates",
            )
        )
    return Deck(containers=tuple(containers))

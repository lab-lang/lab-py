"""Water protocols and explicit SDK hardware fixtures for backend tests."""

from lab import Protocol, seconds, uL
from lab.compiler import Target
from lab.targets import STAR, Labware, Manual, Opentrons

_star_import_error: ImportError | None = None
try:
    from pylabrobot.resources import (
        PLT_CAR_L5AC_A00,
        TIP_CAR_480_A00,
        Azenta4titudeFrameStar_96_wellplate_200ul_Vb,
        Cor_96_wellplate_360ul_Fb,
        STARDeck,
        hamilton_96_tiprack_1000uL_filter,
    )
except ImportError as exc:
    _star_import_error = exc


def water_aliquots() -> Protocol:
    p = Protocol(
        "Water aliquots",
        description="Eight water aliquots with one mixing step to exercise the compiler.",
    )
    water = p.container(
        "water", contents="water", volume=300 * uL, capacity=300 * uL, dead_volume=20 * uL
    )
    plate = p.plate("aliquots", capacity=200 * uL)
    for destination in plate.row("A")[:8]:
        p.transfer(water, destination, volume=25 * uL)
    p.mix(plate["A1"], volume=20 * uL, cycles=3)
    p.wait(1 * seconds)
    return p


def target(name: str, *, thermal: bool = False) -> Target:
    if name == "manual":
        return Manual()
    if name in ("ot2", "flex"):
        flex = name == "flex"
        return Opentrons(
            robot="Flex" if flex else "OT-2",
            pipette="flex_1channel_1000" if flex else "p300_single_gen2",
            labware={
                "water": Labware(
                    "corning_96_wellplate_360ul_flat", "D1" if flex else "1", wells=("A1",)
                ),
                "aliquots": (
                    Labware("opentrons_96_wellplate_200ul_pcr_full_skirt", "thermocycler")
                    if thermal
                    else Labware("nest_96_wellplate_200ul_flat", "D2" if flex else "2")
                ),
            },
            tip_racks=(
                Labware(
                    "opentrons_flex_96_tiprack_200ul" if flex else "opentrons_96_tiprack_300ul",
                    "C1" if flex else "3",
                ),
            ),
            thermocycler=(
                ("thermocycler module gen2" if flex else "thermocycler module") if thermal else None
            ),
        )
    if name == "star":
        if _star_import_error is not None:
            raise ImportError(
                "Install lab-python[star] to use the STAR test fixture"
            ) from _star_import_error
        deck = STARDeck()
        tips = hamilton_96_tiprack_1000uL_filter(name="tips")
        tip_carrier = TIP_CAR_480_A00(name="tip_carrier")
        tip_carrier[0] = tips
        deck.assign_child_resource(tip_carrier, rails=3)
        source = Cor_96_wellplate_360ul_Fb(name="water_plate")
        destination = (
            Azenta4titudeFrameStar_96_wellplate_200ul_Vb(name="aliquot_plate")
            if thermal
            else Cor_96_wellplate_360ul_Fb(name="aliquot_plate")
        )
        plates = PLT_CAR_L5AC_A00(name="plates")
        plates[0], plates[1] = source, destination
        deck.assign_child_resource(plates, rails=15)
        return STAR(
            deck=deck,
            labware={"water": source.get_item("A1"), "aliquots": destination},
            tip_racks=(tips,),
            min_volume=20 * uL,
            max_volume=300 * uL,
        )
    raise ValueError(f"Unknown target {name!r}")

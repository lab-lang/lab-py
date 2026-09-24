"""Compile against a supplied PyLabRobot Hamilton deck without connecting to it."""

import json
from dataclasses import dataclass
from decimal import Decimal
from importlib.metadata import version
from typing import Any

from lab.deck import Container as DeckContainer
from lab.deck import Deck
from lab.documents import describe
from lab.model import (
    Binding,
    Distribute,
    Location,
    ManualInstruction,
    Mix,
    RecordedProtocol,
    SetTemperature,
    TargetPlan,
    Thermocycle,
    Transfer,
    Wait,
    encode,
)
from lab.targets.liquid_handler import LiquidHandler
from lab.units import magnitude, number, uL
from lab.validation import CompileError, step_error

_sdk_import_error: ImportError | None = None
try:
    from pylabrobot.resources import (
        PLT_CAR_L5AC_A00,
        TIP_CAR_480_A00,
        Azenta4titudeFrameStar_96_wellplate_200ul_Vb,
        CellTreat_24_wellplate_3300ul_Fb,
        Container,
        Cor_Axy_24_wellplate_10mL_Vb,
        ItemizedResource,
        Resource,
        STARDeck,
        TipRack,
        hamilton_96_tiprack_50uL,
        hamilton_96_tiprack_300uL,
    )
    from pylabrobot.resources.hamilton import HamiltonSTARDeck
except ImportError as exc:
    _sdk_import_error = exc


@dataclass
class STAR:
    """Use standard PyLabRobot resources and one of the eight pipetting channels."""

    deck: Any
    labware: dict[str, Any]
    tip_racks: tuple[Any, ...]
    min_volume: Any
    max_volume: Any
    channel: int = 0

    @property
    def liquid_handler(self) -> LiquidHandler:
        return LiquidHandler.STAR

    def prepare(self, protocol: RecordedProtocol) -> TargetPlan:
        if _sdk_import_error is not None:
            raise ImportError(
                "Install lab-python[star] to compile for Hamilton STAR"
            ) from _sdk_import_error
        if not isinstance(self.deck, HamiltonSTARDeck):
            raise CompileError("STAR requires a PyLabRobot STARDeck or STARLetDeck")
        if type(self.channel) is not int or not 0 <= self.channel < 8:
            raise CompileError("STAR channel must be an integer from 0 to 7")
        minimum = magnitude(self.min_volume, "microliter")
        maximum = magnitude(self.max_volume, "microliter")
        if minimum > maximum:
            raise CompileError("Minimum volume exceeds maximum volume")
        if set(self.labware) != {resource.name for resource in protocol.resources}:
            raise CompileError("Labware bindings must match the protocol's resources exactly")

        def on_deck(resource: Any) -> None:
            if self.deck.get_resource(resource.name) is not resource:
                raise CompileError(f"{resource.name!r} does not belong to the supplied deck")

        bindings = []
        refs: dict[Location, str] = {}
        for resource in protocol.resources:
            physical = self.labware[resource.name]
            on_deck(physical)
            for well in resource.wells:
                if isinstance(physical, Container) and len(resource.wells) == 1:
                    container = physical
                elif isinstance(physical, ItemizedResource):
                    try:
                        container = physical.get_item(well)
                    except (IndexError, ValueError, KeyError) as exc:
                        raise CompileError(f"{well} is not present in {physical.name}") from exc
                else:
                    raise CompileError("Bind one container or an indexed collection of wells")
                if not isinstance(container, Container):
                    raise CompileError(f"{container.name} cannot contain liquid")
                on_deck(container)
                location = Location(resource.name, well)
                refs[location] = f"deck.get_resource({container.name!r})"
                bindings.append(
                    Binding(
                        location,
                        container.name,
                        Decimal(str(container.max_volume)),
                        resource.dead_volume,
                    )
                )
        tips = []
        seen: set[str] = set()
        for rack in self.tip_racks:
            if not isinstance(rack, TipRack):
                raise CompileError("Tips must be supplied as PyLabRobot TipRack objects")
            on_deck(rack)
            for spot in rack.get_all_items():
                if spot.name in seen:
                    raise CompileError("A tip rack may only be supplied once")
                seen.add(spot.name)
                if spot.has_tip():
                    tips.append(spot)
        deck_data = self.deck.serialize()
        # Ensure the artifact can reconstruct its geometry without serialized Python callbacks.
        Resource.deserialize(json.loads(json.dumps(deck_data)))
        # PyLabRobot 0.2.1 indexes children by the insertion order of its "ordering" mapping.
        # Preserve the SDK's JSON verbatim even when the enclosing plan sorts its own keys.
        serialized_deck = json.dumps(deck_data, separators=(",", ":"), allow_nan=False)
        configuration = {
            "sdk_version": version("pylabrobot"),
            "deck_json": serialized_deck,
            "channel": self.channel,
            "min_volume_ul": number(minimum),
            "max_volume_ul": number(maximum),
            "tip_policy": "fresh tip per transfer or mix",
            "tips": [spot.name for spot in tips],
            "bindings": encode(tuple(bindings)),
        }
        commands = []
        tip_index = 0
        for index, step in enumerate(protocol.steps):
            commands.append(f"print({describe(step)!r})")
            if isinstance(step, (Transfer, Mix, Distribute)):
                if tip_index >= len(tips):
                    raise step_error(index, step, "Not enough fresh tips")
                spot = tips[tip_index]
                tip_index += 1
                tip_max = Decimal(str(spot.get_tip().maximal_volume))
                if not minimum <= step.volume <= min(maximum, tip_max):
                    raise step_error(
                        index, step, "Volume is outside the configured channel/tip range"
                    )
                amount = number(step.volume)
                channels = f"use_channels=[{self.channel}]"
                commands.append(
                    f"await lh.pick_up_tips([deck.get_resource({spot.name!r})], {channels})"
                )
                if isinstance(step, Transfer):
                    commands.extend(
                        (
                            f"await lh.aspirate([{refs[step.source]}], "
                            f"vols=[{amount}], {channels})",
                            f"await lh.dispense([{refs[step.destination]}], "
                            f"vols=[{amount}], {channels})",
                        )
                    )
                elif isinstance(step, Distribute):
                    for destination in step.destinations:
                        commands.extend(
                            (
                                f"await lh.aspirate([{refs[step.source]}], "
                                f"vols=[{amount}], {channels})",
                                f"await lh.dispense([{refs[destination]}], "
                                f"vols=[{amount}], {channels})",
                            )
                        )
                else:
                    commands.extend(
                        (
                            f"for _ in range({step.cycles}):",
                            f"    await lh.aspirate([{refs[step.location]}], "
                            f"vols=[{amount}], {channels})",
                            f"    await lh.dispense([{refs[step.location]}], "
                            f"vols=[{amount}], {channels})",
                        )
                    )
                commands.append(f"await lh.discard_tips({channels}, allow_nonzero_volume=False)")
            elif isinstance(step, Wait):
                commands.append(f"await sleep({number(step.seconds)})")
            elif isinstance(step, Thermocycle):
                plate = self.labware[step.resource]
                if not isinstance(plate, ItemizedResource):
                    raise step_error(index, step, "A thermal resource must bind a whole plate")
                if any(
                    name != step.resource and (other is plate or plate in other.get_all_children())
                    for name, other in self.labware.items()
                ) or any(
                    name != step.resource and other in plate.get_all_children()
                    for name, other in self.labware.items()
                ):
                    raise step_error(index, step, "The thermal plate must have its own binding")
                profile = ", ".join(
                    f"({number(hold.celsius)}, {number(hold.seconds)})" for hold in step.profile
                )
                lid = "None" if step.lid_celsius is None else number(step.lid_celsius)
                commands.append(
                    f"await thermocycle(deck.get_resource({plate.name!r}), "
                    f"profile=[{profile}], cycles={step.cycles}, lid_temperature={lid})"
                )
            elif isinstance(step, ManualInstruction):
                commands.append(f"confirm({step.text!r})")
            elif isinstance(step, SetTemperature):
                plate = self.labware[step.resource]
                if not isinstance(plate, ItemizedResource):
                    raise step_error(index, step, "A held temperature must bind a whole plate")
                commands.append(
                    f"await thermocycle(deck.get_resource({plate.name!r}), "
                    f"profile=[({number(step.celsius)}, 0)], cycles=1, lid_temperature=None)"
                )
            else:
                raise step_error(index, step, "Unsupported step")
        initialize = []
        for resource in protocol.resources:
            fills = {fill.well: fill.volume for fill in resource.fills}
            for well in resource.wells:
                value = number(fills.get(well, Decimal(0)))
                initialize.append(
                    f"{refs[Location(resource.name, well)]}.tracker.set_volume({value})"
                )
        has_thermal = any(
            isinstance(step, (Thermocycle, SetTemperature)) for step in protocol.steps
        )
        thermal_import = "from inspect import iscoroutinefunction\n" if has_thermal else ""
        source = (
            '"""Generated PyLabRobot protocol. Direct execution uses a software backend."""\n\n'
            "import asyncio\nimport json\nfrom importlib.metadata import version\n"
            f"{thermal_import}\n"
            "from pylabrobot.liquid_handling import LiquidHandler\n"
            "from pylabrobot.liquid_handling.backends import LiquidHandlerChatterboxBackend\n"
            "from pylabrobot.resources import Resource\n\n"
            f"DECK_JSON = {serialized_deck!r}\n"
            f"SDK_VERSION = {version('pylabrobot')!r}\n\n"
            "async def run(backend, *, confirm=None, thermocycle=None, sleep=asyncio.sleep):\n"
            "    if version('pylabrobot') != SDK_VERSION:\n"
            "        raise RuntimeError(f'This artifact requires pylabrobot=={SDK_VERSION}')\n"
        )
        if any(isinstance(step, ManualInstruction) for step in protocol.steps):
            source += (
                "    if confirm is None:\n"
                "        raise ValueError('Supply confirm for explicit operator steps')\n"
            )
        if has_thermal:
            source += (
                "    if not iscoroutinefunction(thermocycle):\n"
                "        raise ValueError('Supply an async thermocycle callback for the external "
                "thermal device; it must return the plate to its original position')\n"
            )
        source += (
            "    deck = Resource.deserialize(json.loads(DECK_JSON))\n"
            + "\n".join(f"    {line}" for line in initialize)
            + "\n    lh = LiquidHandler(backend=backend, deck=deck)\n"
            "    await lh.setup()\n"
            "    try:\n"
            + "\n".join(f"        {line}" for line in commands)
            + "\n    finally:\n        await lh.stop()\n"
            "    return lh\n\n"
        )
        if has_thermal:
            source += (
                "async def preview_thermocycle(plate, *, profile, cycles, lid_temperature):\n"
                "    print(f'Simulation only: thermal profile for {plate.name}: {profile}; "
                "{cycles} cycles; lid {lid_temperature} C')\n\n"
            )
        thermal_callback = ", thermocycle=preview_thermocycle" if has_thermal else ""
        source += (
            "if __name__ == '__main__':\n"
            "    asyncio.run(run(LiquidHandlerChatterboxBackend(), confirm=input"
            f"{thermal_callback}))\n"
        )
        return TargetPlan(
            "Hamilton STAR (PyLabRobot)",
            tuple(bindings),
            json.dumps(configuration, sort_keys=True),
            source,
            (
                f"Hamilton deck with {self.deck.num_rails} rails; channel index {self.channel}",
                *(
                    (
                        "External thermal device: supply an async callback; return the plate "
                        "to its original deck position before pipetting resumes",
                    )
                    if has_thermal
                    else ()
                ),
                *(
                    f"{child.name}: {child.model or type(child).__name__} at {child.location} mm"
                    for child in self.deck.children
                    if child.name not in {"trash", "trash96", "core_gripper", "teaching_rack"}
                ),
                f"{tip_index} fresh tips from {', '.join(rack.name for rack in self.tip_racks)}",
            ),
        )


def lower_deck(deck: Deck, *, volumes: tuple[Decimal, ...]) -> STAR:
    """Bind a deck to STAR carriers, plates, and one tip size."""
    if _sdk_import_error is not None:
        raise ImportError(
            "Install lab-python[star] to compile for Hamilton STAR"
        ) from _sdk_import_error
    plates = {container.id: _star_plate(container) for container in deck.containers}
    widest = max(volumes, default=Decimal(1))
    if widest <= 50:
        tips = hamilton_96_tiprack_50uL(name="tips")
        minimum, maximum = 1, 50
    else:
        tips = hamilton_96_tiprack_300uL(name="tips")
        minimum, maximum = 1, 300
    robot = STARDeck()
    tip_carrier = TIP_CAR_480_A00(name="tip_carrier")
    tip_carrier[0] = tips
    robot.assign_child_resource(tip_carrier, rails=3)
    carrier = PLT_CAR_L5AC_A00(name="plates")
    overflow = PLT_CAR_L5AC_A00(name="more_plates")
    for index, plate in enumerate(plates.values()):
        (carrier if index < 5 else overflow)[index if index < 5 else index - 5] = plate
    robot.assign_child_resource(carrier, rails=15)
    if len(plates) > 5:
        robot.assign_child_resource(overflow, rails=30)
    return STAR(
        deck=robot,
        labware=plates,
        tip_racks=(tips,),
        min_volume=minimum * uL,
        max_volume=maximum * uL,
    )


def _star_plate(container: DeckContainer) -> Any:
    name = f"{container.id}_plate"
    if container.kind in {"cold_block", "tube_rack"}:
        if container.rows > 4 or container.columns > 6:
            raise CompileError(f"{container.id} does not fit a 24-well plate")
        return CellTreat_24_wellplate_3300ul_Fb(name=name)
    if container.kind in {"pcr_plate", "culture_plate"}:
        if container.rows > 8 or container.columns > 12:
            raise CompileError(f"{container.id} does not fit a 96-well plate")
        return Azenta4titudeFrameStar_96_wellplate_200ul_Vb(name=name)
    if container.kind == "conical_rack":
        if container.rows > 4 or container.columns > 6:
            raise CompileError(f"{container.id} does not fit a 24-well reservoir")
        return Cor_Axy_24_wellplate_10mL_Vb(name=name)
    raise CompileError(f"No STAR labware for {container.kind}")

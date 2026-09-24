import builtins
import hashlib
import json
from dataclasses import replace
from decimal import Decimal
from io import StringIO

import pytest

import lab
from lab import CompileError, Protocol, celsius, seconds, uL
from lab.targets import Labware, LiquidHandler, Manual
from tests.target_fixture import target, water_aliquots
from tests.thermal_fixture import thermal_aliquots

try:
    from opentrons.protocol_api import ThermocyclerContext
    from opentrons.simulate import simulate
except ImportError:
    _has_opentrons = False
else:
    _has_opentrons = True

try:
    from pylabrobot.liquid_handling.backends import SerializingBackend
    from pylabrobot.liquid_handling.backends.hamilton.STAR_chatterbox import STARChatterboxBackend
    from pylabrobot.resources import Resource, set_volume_tracking
except ImportError:
    _has_star = False
else:
    _has_star = True

requires_opentrons = pytest.mark.skipif(not _has_opentrons, reason="Opentrons SDK not installed")
requires_star = pytest.mark.skipif(not _has_star, reason="PyLabRobot SDK not installed")


def compiled(protocol, hardware):
    declared = getattr(hardware, "liquid_handler", None)
    if isinstance(declared, LiquidHandler):
        return lab.compile(protocol, hardware, liquid_handler=declared)
    return lab.compile(protocol, hardware)


@pytest.mark.integration
@requires_opentrons
@pytest.mark.parametrize("name", ["ot2", "flex"])
def test_generated_opentrons_runs_in_official_simulator(name):
    p = water_aliquots()
    bundle = compiled(p, target(name))
    log, _ = simulate(StringIO(bundle.files["protocol.py"]))
    texts = [event["payload"]["text"] for event in log]
    assert sum(text.startswith("Aspirating 25.0") for text in texts) == 8
    assert sum(text.startswith("Dispensing 25.0") for text in texts) == 8
    destinations = [
        text.split(" into ", 1)[1].split(" of ", 1)[0]
        for text in texts
        if text.startswith("Dispensing 25.0")
    ]
    assert destinations == [f"A{index}" for index in range(1, 9)]
    assert sum(text.startswith("Picking up tip") for text in texts) == 9
    assert sum(text.startswith("Dropping tip") for text in texts) == 9
    assert any(text.startswith("Mixing 3 times with a volume of 20.0") for text in texts)
    data = json.loads(bundle.plan_json)
    assert data["source_sha256"] == hashlib.sha256(bundle.files["protocol.py"].encode()).hexdigest()
    assert dict(bundle.final_volumes)[lab.model.Location("water", "A1")] == Decimal(100)
    assert any("A1" in text and "plate" in text.lower() for text in texts)


def test_core_does_not_import_robot_sdks(monkeypatch):
    original = builtins.__import__

    def guarded(name, *args, **kwargs):
        if name.startswith(("opentrons", "pylabrobot")):
            raise AssertionError("Manual compilation must not import a robot SDK")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded)
    assert lab.compile(water_aliquots(), Manual()).target.name == "Manual"


@pytest.mark.integration
@requires_opentrons
@pytest.mark.parametrize("name", ["ot2", "flex"])
def test_opentrons_missing_bindings_conflicts_and_tips(name):
    t = target(name)
    t.labware.pop("water")
    with pytest.raises(CompileError, match="exactly"):
        compiled(water_aliquots(), t)
    t = target(name)
    t.tip_racks = ()
    with pytest.raises(CompileError, match="fresh tips"):
        compiled(water_aliquots(), t)
    t = target(name)
    t.labware["aliquots"] = replace(t.labware["aliquots"], slot=t.labware["water"].slot)
    with pytest.raises(CompileError, match="Conflicting labware"):
        compiled(water_aliquots(), t)
    t = target(name)
    t.tip_racks = (replace(t.tip_racks[0], wells=("A1", "A1")),)
    with pytest.raises(CompileError, match="only be supplied once"):
        compiled(water_aliquots(), t)


@pytest.mark.integration
@requires_opentrons
def test_opentrons_range_trash_and_config_freezing():
    t = target("flex")
    t.labware["water"] = replace(t.labware["water"], slot="A3")
    with pytest.raises(CompileError, match="Unavailable"):
        compiled(water_aliquots(), t)
    t = target("ot2")
    t.tip_racks = (Labware("opentrons_flex_96_tiprack_200ul", "3"),)
    with pytest.raises(CompileError, match="requires"):
        compiled(water_aliquots(), t)
    t = target("ot2")
    bundle = compiled(water_aliquots(), t)
    frozen = bundle.files
    t.labware.clear()
    assert bundle.files == frozen
    p = Protocol("Below range")
    a = p.container("water", contents="water", volume=100 * uL, capacity=300 * uL)
    b = p.plate("aliquots", capacity=200 * uL)
    p.transfer(a, b["A1"], volume=1 * uL)
    with pytest.raises(CompileError, match="outside"):
        compiled(p, target("ot2"))


@pytest.mark.integration
@requires_star
async def test_star_executes_real_pylabrobot_frontend_and_tracks_volumes():
    class Recorder(SerializingBackend):
        def __init__(self):
            super().__init__(num_channels=8)
            self.events = []

        async def send_command(self, command, data=None):
            self.events.append((command, data))
            return None

    async def no_wait(_):
        pass

    t = target("star")
    bundle = compiled(water_aliquots(), t)
    saved_deck = Resource.deserialize(
        json.loads(json.loads(bundle.plan_json)["target"]["configuration"]["deck_json"])
    )
    assert saved_deck.get_resource("aliquot_plate").get_item("A2").name == "aliquot_plate_well_A2"
    before = bundle.files
    t.labware.clear()
    assert bundle.files == before
    namespace = {"__name__": "_generated_protocol"}
    exec(builtins.compile(bundle.files["protocol.py"], "generated_star.py", "exec"), namespace)
    backend = Recorder()
    set_volume_tracking(True)
    try:
        handler = await namespace["run"](backend, sleep=no_wait)
    finally:
        set_volume_tracking(False)
    actions = [
        (name, data)
        for name, data in backend.events
        if name in ("pick_up_tips", "aspirate", "dispense", "drop_tips")
    ]
    names = [name for name, _ in actions]
    assert names[:32] == ["pick_up_tips", "aspirate", "dispense", "drop_tips"] * 8
    assert names[32:] == [
        "pick_up_tips",
        "aspirate",
        "dispense",
        "aspirate",
        "dispense",
        "aspirate",
        "dispense",
        "drop_tips",
    ]
    assert [data["channels"][0]["volume"] for name, data in actions if name == "aspirate"] == (
        [25] * 8 + [20] * 3
    )
    picked = [
        data["channels"][0]["resource_name"] for name, data in actions if name == "pick_up_tips"
    ]
    assert len(set(picked)) == 9
    assert backend.events[0][0] == "setup"
    assert backend.events[-1][0] == "stop"
    assert handler.deck.get_resource("water_plate").get_item("A1").tracker.get_used_volume() == 100
    for name in ("A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8"):
        assert (
            handler.deck.get_resource("aliquot_plate").get_item(name).tracker.get_used_volume()
            == 25
        )


@pytest.mark.integration
@requires_star
def test_star_missing_tips_range_and_deck_membership():
    t = target("star")
    t.tip_racks = ()
    with pytest.raises(CompileError, match="fresh tips"):
        compiled(water_aliquots(), t)
    t = target("star")
    t.max_volume = 20 * uL
    with pytest.raises(CompileError, match="outside"):
        compiled(water_aliquots(), t)
    t = target("star")
    foreign = target("star")
    t.labware["water"] = foreign.labware["water"]
    with pytest.raises(CompileError, match="does not belong"):
        compiled(water_aliquots(), t)


@pytest.mark.integration
@requires_star
@pytest.mark.parametrize("thermal,tips,actions", [(False, 9, 11), (True, 6, 7)])
async def test_star_firmware_generation_without_hardware(capsys, thermal, tips, actions):
    p = thermal_aliquots() if thermal else water_aliquots()
    bundle = compiled(p, target("star", thermal=thermal))
    namespace = {"__name__": "_generated"}
    exec(builtins.compile(bundle.files["protocol.py"], "star.py", "exec"), namespace)

    async def no_wait(_):
        pass

    await namespace["run"](
        STARChatterboxBackend(), sleep=no_wait, thermocycle=namespace.get("preview_thermocycle")
    )
    commands = capsys.readouterr().out.splitlines()
    assert sum(line.startswith("C0TP") for line in commands) == tips
    assert sum(line.startswith("C0AS") for line in commands) == actions
    assert sum(line.startswith("C0DS") for line in commands) == actions
    assert sum(line.startswith("C0TR") for line in commands) == tips


@pytest.mark.integration
@requires_star
async def test_star_manual_preflight_and_failure_cleanup():
    class FailingBackend(SerializingBackend):
        def __init__(self):
            super().__init__(num_channels=8)
            self.events = []

        async def send_command(self, command, data=None):
            self.events.append(command)
            if command == "aspirate":
                raise RuntimeError("Synthetic backend failure")
            return None

    p = water_aliquots()
    p.manual("Inspect the water aliquots without changing their contents.")
    namespace = {"__name__": "_generated"}
    bundle = compiled(p, target("star"))
    exec(builtins.compile(bundle.files["protocol.py"], "star.py", "exec"), namespace)
    backend = FailingBackend()
    with pytest.raises(ValueError, match="Supply confirm"):
        await namespace["run"](backend)
    assert backend.events == []
    with pytest.raises(RuntimeError, match="Synthetic backend failure"):
        await namespace["run"](backend, confirm=lambda text: None)
    assert backend.events[-1] == "stop"
    assert backend.events.count("aspirate") == 1


@pytest.mark.integration
@requires_opentrons
@pytest.mark.parametrize("name", ["ot2", "flex"])
def test_operator_pause_survives_opentrons_generation(name):
    p = water_aliquots()
    message = "Inspect the water aliquots without changing their contents."
    p.manual(message)
    bundle = compiled(p, target(name))
    log, _ = simulate(StringIO(bundle.files["protocol.py"]))
    assert any(
        message in entry["payload"]["text"] and entry["payload"]["text"].startswith("Pausing")
        for entry in log
    )


@pytest.mark.integration
@requires_opentrons
@pytest.mark.parametrize(
    "name,module",
    [
        ("ot2", "thermocycler module"),
        ("ot2", "thermocycler module gen2"),
        ("flex", "thermocycler module gen2"),
    ],
)
def test_stages_with_thermal_profiles_in_official_simulator(name, module):
    t = target(name, thermal=True)
    t.thermocycler = module
    bundle = compiled(thermal_aliquots(), t)
    source = bundle.files["protocol.py"]
    log, _ = simulate(StringIO(source))
    texts = [event["payload"]["text"] for event in log]
    assert sum(text.startswith("Picking up tip") for text in texts) == 6
    assert sum(text.startswith("Dropping tip") for text in texts) == 6
    assert "block_max_volume=100" in source
    assert "block_max_volume=50" in source
    profiles = [
        event for event in log if event["payload"]["text"].startswith("Thermocycler starting")
    ]
    assert len(profiles) == 2
    assert profiles[0]["payload"]["steps"] == [
        {"temperature": 25, "hold_time_seconds": 1},
        {"temperature": 30, "hold_time_seconds": 1},
    ]
    assert profiles[1]["payload"]["steps"] == [{"temperature": 25, "hold_time_seconds": 1}]
    dispenses = [text for text in texts if text.startswith("Dispensing 25.0")]
    assert [text.split(" into ", 1)[1].split(" of ", 1)[0] for text in dispenses[-2:]] == [
        "A3",
        "A4",
    ]


@pytest.mark.integration
@requires_opentrons
@pytest.mark.parametrize("name,slot", [("ot2", "8"), ("flex", "A1")])
def test_thermal_module_reserves_its_deck_footprint(name, slot):
    t = target(name, thermal=True)
    t.labware["water"] = replace(t.labware["water"], slot=slot)
    with pytest.raises(CompileError, match="Unavailable"):
        compiled(thermal_aliquots(), t)


@pytest.mark.integration
@requires_opentrons
def test_thermal_binding_and_limits():
    with pytest.raises(CompileError, match="must be on the thermocycler"):
        compiled(thermal_aliquots(), target("ot2"))
    t = target("flex", thermal=True)
    t.thermocycler = "thermocycler module"
    with pytest.raises(CompileError, match="GEN2"):
        compiled(thermal_aliquots(), t)
    t = target("ot2", thermal=True)
    t.labware["aliquots"] = replace(t.labware["aliquots"], load_name="nest_96_wellplate_200ul_flat")
    with pytest.raises(CompileError, match="PCR plate"):
        compiled(thermal_aliquots(), t)
    p = Protocol("Out of range")
    p.container("water", capacity=300 * uL)
    plate = p.plate("aliquots", capacity=200 * uL)
    p.load(plate["A1"], "water", volume=50 * uL)
    p.thermocycle(plate, [(celsius(120), 1 * seconds)])
    with pytest.raises(CompileError, match="block range"):
        compiled(p, target("ot2", thermal=True))


@pytest.mark.integration
@requires_opentrons
def test_opentrons_deactivates_after_thermal_failure(monkeypatch):
    events = []
    original_deactivate = ThermocyclerContext.deactivate

    def fail_profile(self, *args, **kwargs):
        events.append("profile")
        raise RuntimeError("Synthetic thermal failure")

    def deactivate(self):
        events.append("deactivate")
        return original_deactivate(self)

    monkeypatch.setattr(ThermocyclerContext, "execute_profile", fail_profile)
    monkeypatch.setattr(ThermocyclerContext, "deactivate", deactivate)
    bundle = compiled(thermal_aliquots(), target("ot2", thermal=True))
    with pytest.raises(Exception, match="Synthetic thermal failure"):
        simulate(StringIO(bundle.files["protocol.py"]))
    assert events == ["profile", "deactivate"]


@pytest.mark.integration
@requires_star
async def test_star_external_thermal_handoff_is_awaited_and_required():
    events = []

    class Recorder(SerializingBackend):
        async def send_command(self, command, data=None):
            events.append(command)

    async def thermocycle(plate, *, profile, cycles, lid_temperature):
        events.append("thermal")
        amounts = [plate.get_item(well).tracker.get_used_volume() for well in ("A1", "A2")]
        thermal_calls.append((amounts, profile, cycles, lid_temperature))

    bundle = compiled(thermal_aliquots(), target("star", thermal=True))
    namespace = {"__name__": "_generated"}
    exec(builtins.compile(bundle.files["protocol.py"], "stages_star.py", "exec"), namespace)
    backend = Recorder(num_channels=8)
    with pytest.raises(ValueError, match="async thermocycle"):
        await namespace["run"](backend)
    with pytest.raises(ValueError, match="async thermocycle"):
        await namespace["run"](backend, thermocycle=lambda *args, **kwargs: None)
    assert not events
    thermal_calls = []
    set_volume_tracking(True)
    try:
        handler = await namespace["run"](backend, thermocycle=thermocycle)
    finally:
        set_volume_tracking(False)
    assert thermal_calls == [
        ([100, 0], [(25, 1), (30, 1)], 2, 40),
        ([50, 50], [(25, 1)], 1, None),
    ]
    thermal_positions = [i for i, event in enumerate(events) if event == "thermal"]
    assert all(events[i - 1] == "drop_tips" for i in thermal_positions)
    assert all(events[i + 1] == "pick_up_tips" for i in thermal_positions)
    plate = handler.deck.get_resource("aliquot_plate")
    assert [plate.get_item(f"A{i}").tracker.get_used_volume() for i in range(1, 5)] == [
        50,
        0,
        25,
        25,
    ]


@pytest.mark.integration
@requires_star
async def test_star_thermal_failure_stops_before_later_transfers():
    events = []

    class Recorder(SerializingBackend):
        async def send_command(self, command, data=None):
            events.append(command)

    async def fail_thermal(plate, **kwargs):
        raise RuntimeError("Synthetic thermal failure")

    bundle = compiled(thermal_aliquots(), target("star", thermal=True))
    namespace = {"__name__": "_generated"}
    exec(builtins.compile(bundle.files["protocol.py"], "stages_star.py", "exec"), namespace)
    with pytest.raises(RuntimeError, match="Synthetic thermal failure"):
        await namespace["run"](Recorder(num_channels=8), thermocycle=fail_thermal)
    assert events.count("pick_up_tips") == 3
    assert events[-1] == "stop"

"""Snapshot, validate, prepare a target, and emit a self-contained bundle."""

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any
from typing import Protocol as Interface

import lab.documents as documents
from lab._version import __version__
from lab.deck import Deck
from lab.model import Distribute, Location, Mix, RecordedProtocol, TargetPlan, Transfer, encode
from lab.protocol import Protocol
from lab.targets.liquid_handler import LiquidHandler
from lab.targets.lower import lower_deck
from lab.validation import logical_bindings, validate


class Target(Interface):
    def prepare(self, protocol: RecordedProtocol) -> TargetPlan: ...


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"


@dataclass(frozen=True)
class Compilation:
    protocol: RecordedProtocol
    target: TargetPlan
    final_volumes: tuple[tuple[Location, Decimal], ...]

    @property
    def plan_json(self) -> str:
        return canonical_json(
            {
                "format": "lab.plan.v1",
                "compiler_version": __version__,
                "units": {"volume": "microliter", "duration": "second", "temperature": "celsius"},
                "protocol": encode(self.protocol),
                "target": {
                    "name": self.target.name,
                    "configuration": json.loads(self.target.configuration_json),
                    "bindings": encode(self.target.bindings),
                    "setup": list(self.target.setup),
                },
                "final_volumes": [
                    {"location": encode(location), "volume": encode(volume)}
                    for location, volume in self.final_volumes
                ],
                "source_sha256": (
                    hashlib.sha256(self.target.source.encode()).hexdigest()
                    if self.target.source is not None
                    else None
                ),
            }
        )

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.plan_json.encode()).hexdigest()

    @property
    def files(self) -> dict[str, str]:
        result = {"plan.json": self.plan_json, "protocol.html": documents.render(self)}
        if self.target.source is not None:
            result["protocol.py"] = self.target.source
        return result

    def write(self, directory: str | Path) -> Path:
        """Write a bundle. Refuse to replace any different existing artifact."""
        directory = Path(directory)
        files = self.files
        for name, text in files.items():
            path = directory / name
            if path.exists() and path.read_text() != text:
                raise FileExistsError(f"{path} already contains a different artifact")
        directory.mkdir(parents=True, exist_ok=True)
        for name, text in files.items():
            (directory / name).write_text(text, encoding="utf-8")
        return directory


def compile(
    protocol: Protocol, hardware: Target | Deck, *, liquid_handler: LiquidHandler | None = None
) -> Compilation:
    """Compile offline for one piece of hardware.

    A ``Deck`` is lowered for ``liquid_handler`` into that robot's labware, modules, and
    pipettes. Robot hardware names its ``LiquidHandler``; pass that same member.
    A document target such as ``Manual()`` has no robot, so ``liquid_handler`` is omitted.
    """
    if isinstance(hardware, Deck):
        if not isinstance(liquid_handler, LiquidHandler):
            raise TypeError(
                "Pass liquid_handler=LiquidHandler.OT2, LiquidHandler.FLEX, or LiquidHandler.STAR."
            )
        liquid = tuple(
            step.volume for step in protocol.steps if isinstance(step, (Transfer, Mix, Distribute))
        )
        hardware = lower_deck(hardware, liquid_handler, liquid)
    declared = getattr(hardware, "liquid_handler", None)
    if isinstance(declared, LiquidHandler) and liquid_handler != declared:
        raise TypeError(
            f"This hardware is LiquidHandler.{declared.name}. "
            f"Pass liquid_handler=LiquidHandler.{declared.name}."
        )
    if liquid_handler is not None and not isinstance(declared, LiquidHandler):
        raise TypeError("This hardware does not name a LiquidHandler.")
    if liquid_handler is not None and not isinstance(liquid_handler, LiquidHandler):
        raise TypeError("Pass LiquidHandler.OT2, LiquidHandler.FLEX, or LiquidHandler.STAR.")
    recorded = protocol.snapshot()
    validate(recorded, logical_bindings(recorded))
    prepared = hardware.prepare(recorded)
    volumes = validate(recorded, prepared.bindings)
    return Compilation(recorded, prepared, tuple(volumes.items()))

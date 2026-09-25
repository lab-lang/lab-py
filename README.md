<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/the-lab-compiler/lab-py/master/docs/assets/brand/wordmark-full-dark.svg">
    <img alt="The Lab Compiler" src="https://raw.githubusercontent.com/the-lab-compiler/lab-py/master/docs/assets/brand/wordmark-full-light.svg" width="620">
  </picture>
</p>

<p align="center">
  <em>A compiler for biological engineering. Describe experiments in Python, check the protocol, and produce a document or a robot program.</em>
</p>

Lab Compiler is the Python compiler for laboratory work. A program names materials, wells, and steps. Compilation checks volumes, units, and bindings, then writes a printable document and code for the handler you name.

Protocol containers, steps, and decks are expressed in Lab types. A `Deck` holds shared container requirements and can include a `DeckLayout` for each liquid handler. Compilation selects the layout, checks the handler's capabilities, and translates Lab equipment and placements into Opentrons or PyLabRobot configuration. Supported presets handle simple layouts. You do not need to construct SDK deck objects.

## Install

Lab Compiler supports Python 3.11 and 3.12. Install the `lab-compiler` distribution and import it as `lab`:

```sh
python -m pip install lab-compiler
```

The base package compiles printable documents. Install the optional SDK for your robot target:

```sh
python -m pip install "lab-compiler[opentrons]"  # OT-2 and Flex
python -m pip install "lab-compiler[star]"       # Hamilton STAR
```

Use `"lab-compiler[opentrons,star]"` to install both SDKs.

## Write a protocol

You define the strain, chassis, and plasmids. The library provides typed requests and reusable cloning stages. This example compiles a heat-shock transformation using material identifiers supplied by the user.

```python
from lab.experiments.cloning import transformation_deck
from lab.protocols import (
    Part,
    ProtocolCompiler,
    TransformationReaction,
    TransformationRequest,
)
from lab.targets import LiquidHandler

request = TransformationRequest(
    id="my-transformation",
    reactions=(
        TransformationReaction(
            id="reaction-1",
            strain=Part("https://example.org/my-strain/1"),
            chassis=Part("https://example.org/my-cells/1"),
            plasmids=[Part("https://example.org/my-plasmid/1")],
        ),
    ),
)
compiled = ProtocolCompiler().compile(
    request,
    hardware=transformation_deck(on_module=True),
    liquid_handler=LiquidHandler.OT2,
)
compiled.write("build/transformation")
```

`TransformationReaction` names an output strain, its chassis, and its plasmids as `Part` IRIs. The compiler assigns wells and records the transfers, heat shock, and recovery steps. The result includes an output manifest for downstream stages. The [cloning example](https://github.com/the-lab-compiler/lab-py/blob/master/examples/cloning.py) defines its materials and reactions directly and links assembly, transformation, and plating.

`transformation_deck(on_module=True)` names the 24-well DNA block, the cell tubes, and the reaction plate. This is an Opentrons preset; the example uses `LiquidHandler.OT2`. For a document with no robot, import `Manual` from `lab.targets` and use `ProtocolCompiler().compile(request, hardware=Manual())`.

## Describe a deck

This OT-2 deck places two 96-well plates in slots 1 and 2, a 300 µL tip rack in slot 3, and a P300 pipette on the left mount. It uses the same equipment and placement types as the [deck layouts example](https://github.com/the-lab-compiler/lab-py/blob/master/examples/deck_layouts.py).

```python
from lab.deck import Deck, DeckLayout, Pipette, Placement, Slot, TipRack
from lab.equipment import LabwareModel, LiquidHandler, Mount, PipetteModel, TipRackModel
from lab.labware import PLATE_96, ContainerSpec

deck = Deck(
    containers=(
        ContainerSpec(id="sources", labware=PLATE_96),
        ContainerSpec(id="assay", labware=PLATE_96),
    ),
    layouts=(
        DeckLayout(
            liquid_handler=LiquidHandler.OT2,
            placements=(
                Placement(
                    container="sources",
                    model=LabwareModel.CORNING_96_360_UL,
                    location=Slot("1"),
                ),
                Placement(
                    container="assay",
                    model=LabwareModel.CORNING_96_360_UL,
                    location=Slot("2"),
                ),
            ),
            tip_racks=(
                TipRack(
                    id="tips",
                    model=TipRackModel.OPENTRONS_300_UL,
                    location=Slot("3"),
                ),
            ),
            pipettes=(
                Pipette(
                    model=PipetteModel.P300_SINGLE_GEN2,
                    mount=Mount.LEFT,
                    tip_racks=("tips"),
                ),
            ),
        ),
    ),
)
```

The container ids, `sources` and `assay`, match the names used by the protocol. `DeckLayout` assigns each container a physical model and position, and connects the pipette to its tip rack. A deck can include additional layouts for Flex or STAR using the same container ids.

## Describe physical layouts in Lab

Use `DeckLayout` when equipment or placement needs to be explicit. Each layout names its `LiquidHandler` and places the same shared containers. All objects below belong to Lab:

| Object | Purpose |
| --- | --- |
| `Placement` | A container's physical labware model, position, and optional well mapping |
| `Slot`, `Rail`, `HolderSite` | A deck slot, carrier rail, or indexed site on a named holder |
| `Carrier`, `Module` | Equipment that occupies a position and holds other resources |
| `TipRack` | A tip model and its position |
| `Pipette`, `Channel` | A mounted pipette or independent channel, with its assigned tip racks |

Equipment models are typed identifiers from `lab.equipment`; each backend resolves the models it supports. A STAR layout can place a carrier at `Rail(20)` and a plate at `HolderSite("plates", 3)`. An Opentrons layout can place the same logical container at `Slot("2")` or on a named module. The shared model does not impose one thermal device on every handler. Targets enforce their supported device counts, models, locations, and module footprints.

The [deck layouts example](https://github.com/the-lab-compiler/lab-py/blob/master/examples/deck_layouts.py) prepares duplicate BSA standards and purified protein samples in a flat-bottom assay plate using a reservoir of prepared BCA working reagent. `protocol()` describes the transfers; `deck()` shares the container requirements and calls `opentrons_layout()` for OT-2 and Flex and `hamilton_layout()` for STAR. The logical source wells map to physical wells `B1`–`B12` on each handler; STAR also specifies carriers, rails, and occupied carrier sites. Mixing, incubation, and absorbance reading remain an explicit operator handoff following the [Pierce BCA guide](https://www.thermofisher.com/TFS-Assets/LSG/manuals/MAN0011430_Pierce_BCA_Protein_Asy_UG.pdf). The example imports only Lab types and the Python standard library, with layouts to adapt to installed equipment.

```python
from examples.deck_layouts import deck, protocol
from lab import compile
from lab.targets import LiquidHandler

compiled = compile(protocol(), deck(), liquid_handler=LiquidHandler.STAR)
```

The compiler rejects missing layouts, conflicting placements, invalid holder references, incompatible labware, and unsupported target features. It preserves the authored Lab deck in `plan.json` alongside the resolved backend configuration. Physical geometry comes from the selected equipment definitions; the STAR backend constructs and serializes the PyLabRobot resource hierarchy internally.

For Opentrons, place thermal labware on a supported `Module`. STAR thermal operations currently use an external device integration: declare the container in `DeckLayout.external_thermal_resources` and supply the async `thermocycle` callback when the generated `run()` executes. The callback controls the device and returns the plate to its original position. Compilation checks the declaration; the software preview only reports the request. Unsupported on-deck thermal models produce an error.

## Try it

The examples live in the source repository. To run them with Python 3.12 and both optional SDKs:

```sh
git clone https://github.com/the-lab-compiler/lab-py.git
cd lab-py
uv sync --locked --all-extras
uv run python -m examples.cloning --target manual
uv run python -m examples.cloning --target ot2
uv run python -m examples.deck_layouts --target star
uv run python -m examples.deck_layouts --target ot2
uv run python -m examples.deck_layouts --target flex
```

A bundle is `protocol.html`, `plan.json`, and `protocol.py` when the target is a robot. `ProtocolCompiler` also writes `manifest.json` with the planned outputs. The cloning example writes separate `assembly`, `transformation`, and `plating` bundles under `build/cloning/<target>` or the directory supplied with `--out`, including for the manual target. The shared deck example writes to `build/decks/<target>` or its `--out` directory. Compilation never connects to hardware. Rebuilding identical files succeeds. A different plan in the same directory is rejected.

## Status

Lab Compiler is an early prototype. It checks a plan and emits a document or device program for the OT-2, Flex, and STAR. Software checks are not calibration, collision safety, or qualification of a physical run. Generated instructions need a person and a facility before anyone uses them at the bench.

## Development

```sh
uv sync --locked --all-extras
uv run --no-sync ruff check .
uv run --no-sync mypy
uv run --no-sync pytest
```

See the [release guide](https://github.com/the-lab-compiler/lab-py/blob/master/docs/releasing.md) for package validation and PyPI publishing.

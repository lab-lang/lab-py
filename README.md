<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/brand/wordmark-full-dark.svg">
    <img alt="The Lab Compiler" src="docs/assets/brand/wordmark-full-light.svg" width="620">
  </picture>
</p>

<p align="center">
  <em>A compiler for biological engineering. Describe experiments in Python, check the protocol, and produce a document or a robot program.</em>
</p>

Lab Compiler is the Python compiler for laboratory work. A program names materials, wells, and steps. Compilation checks volumes, units, and bindings, then writes a printable document and code for the handler you name.

The same plan renders for an Opentrons OT-2, an Opentrons Flex, or a Hamilton STAR. You describe the deck by container and site. Compilation lowers it to that handler's pipettes, modules, carriers, and labware. `Handler.OT2`, `Handler.FLEX`, and `Handler.STAR` are peers. A concrete deck for one of them cannot be compiled as another.

## Write a protocol

You define the strain, chassis, and plasmids. The library provides typed requests and reusable cloning stages. This example compiles a heat-shock transformation using material identifiers supplied by the user.

```python
from lab.experiments.cloning import transformation_deck
from lab.protocols import (
    MaterialRef,
    ProtocolCompiler,
    TransformationReaction,
    TransformationRequest,
)
from lab.targets import Handler

request = TransformationRequest(
    id="my-transformation",
    reactions=(
        TransformationReaction(
            id="reaction-1",
            strain=MaterialRef(identity="my-strain", label="My strain"),
            chassis=MaterialRef(identity="my-cells", label="My competent cells"),
            plasmids=(MaterialRef(identity="my-plasmid", label="My plasmid"),),
        ),
    ),
)
compiled = ProtocolCompiler().compile(
    request,
    hardware=transformation_deck(on_module=True),
    handler=Handler.STAR,
)
compiled.write("build/transformation")
```

`MaterialRef` carries your material's identity and display label. `TransformationReaction` associates an output strain with its chassis and plasmids. The compiler assigns wells and records the transfers, heat shock, and recovery steps. The result includes an output manifest for downstream stages. Sample designs live in [examples/cloning.py](examples/cloning.py); the [staged example](examples/stages.py) links assembly, transformation, and plating.

`transformation_deck(on_module=True)` names the 24-well DNA block, the cell tubes, and the reaction plate. Compilation lowers that deck for the handler you pass. This recipe's 2 µL transfers lower for `Handler.OT2` and `Handler.STAR`. A concrete deck for one handler cannot be compiled as another. For a document with no robot, import `Manual` from `lab.targets` and use `ProtocolCompiler().compile(request, hardware=Manual())`.

## Try it

Python 3.12. Robot SDKs are optional.

```sh
uv sync --all-extras
uv run python -m examples.stages --target manual
uv run python -m examples.stages --target ot2
uv run python -m examples.stages --target star
```

A bundle is `protocol.html`, `plan.json`, and `protocol.py` when the target is a robot. `ProtocolCompiler` also writes `manifest.json` with the planned outputs. Compilation never connects to hardware. Rebuilding identical files succeeds. A different plan in the same directory is rejected.

## Status

Lab Compiler is an early prototype. It checks a plan and emits a document or device program for the OT-2, Flex, and STAR. Software checks are not calibration, collision safety, or qualification of a physical run. Generated instructions need a person and a facility before anyone uses them at the bench.

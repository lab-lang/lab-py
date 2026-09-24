"""Write the Golden Gate, heat-shock, and plating workflow."""

import argparse

import lab
from examples.cloning import (
    ASSEMBLIES,
    STRAINS,
    example_assembly_request,
    example_transformation_request,
)
from lab.experiments.cloning import (
    assembly_deck,
    golden_gate,
    plating_deck,
    transformation_deck,
)
from lab.protocols import PlatingRequest, ProtocolCompiler
from lab.targets import LiquidHandler, Manual


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        choices=("manual", *(liquid_handler.value for liquid_handler in LiquidHandler)),
        default="manual",
    )
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    if args.target == "manual":
        bundle = lab.compile(golden_gate(ASSEMBLIES, STRAINS), Manual())
        path = bundle.write(args.out or "build/stages/manual")
        print(f"{bundle.target.name}: {path} ({bundle.digest[:12]})")
        return
    liquid_handler = LiquidHandler(args.target)
    compiler = ProtocolCompiler()
    assembled = compiler.compile(
        example_assembly_request(), hardware=assembly_deck(), liquid_handler=liquid_handler
    )
    transformed = compiler.compile(
        example_transformation_request(),
        inputs=assembled.manifest,
        hardware=transformation_deck(),
        liquid_handler=liquid_handler,
    )
    plated = compiler.compile(
        PlatingRequest(
            id="plating",
            sample_ids=tuple(sample.id for sample in transformed.manifest.samples),
            source_stage_id=transformed.manifest.protocol_id,
        ),
        inputs=transformed.manifest,
        hardware=plating_deck(),
        liquid_handler=liquid_handler,
    )
    for name, compiled in (
        ("assembly", assembled),
        ("transformation", transformed),
        ("plating", plated),
    ):
        path = compiled.write(args.out or f"build/stages/{liquid_handler.value}/{name}")
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()

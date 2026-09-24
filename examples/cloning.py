"""Write the Golden Gate, heat-shock, and plating workflow."""

import argparse
from pathlib import Path

from lab.experiments.cloning import (
    assembly_deck,
    plating_deck,
    transformation_deck,
)
from lab.protocols import (
    AssemblyReaction,
    AssemblyRequest,
    MaterialRef,
    PlatingRequest,
    ProtocolCompiler,
    TransformationReaction,
    TransformationRequest,
)
from lab.targets import LiquidHandler, Manual

PSB1C3 = MaterialRef(identity="https://sbolcanvas.org/pSB1C3/1", label="pSB1C3")
J23101 = MaterialRef(identity="https://sbolcanvas.org/J23101/1", label="J23101")
J23106 = MaterialRef(identity="https://sbolcanvas.org/J23106/1", label="J23106")
B0034 = MaterialRef(identity="https://sbolcanvas.org/B0034/1", label="B0034")
GFP = MaterialRef(identity="https://sbolcanvas.org/GFP/1", label="GFP")
RFP = MaterialRef(identity="https://sbolcanvas.org/RFP/1", label="RFP")
B0015 = MaterialRef(identity="https://sbolcanvas.org/B0015/1", label="B0015")
BSAI = MaterialRef(identity="https://SBOL2Build.org/BsaI/1", label="BsaI")
DH5ALPHA = MaterialRef(identity="https://sbolcanvas.org/DH5alpha/1", label="DH5alpha")
BL21 = MaterialRef(identity="https://sbolcanvas.org/BL21/1", label="BL21")
PLASMID_1 = MaterialRef(
    identity="https://SBOL2Build.org/composite_plasmid_1/1", label="composite_plasmid_1"
)
PLASMID_2 = MaterialRef(
    identity="https://SBOL2Build.org/composite_plasmid_2/1", label="composite_plasmid_2"
)

ASSEMBLIES = (
    AssemblyReaction(
        id="assembly-1",
        product=PLASMID_1,
        backbone=PSB1C3,
        parts=(J23101, B0034, GFP, B0015),
        restriction_enzyme=BSAI,
    ),
    AssemblyReaction(
        id="assembly-2",
        product=PLASMID_2,
        backbone=PSB1C3,
        parts=(J23106, B0034, RFP, B0015),
        restriction_enzyme=BSAI,
    ),
)

STRAINS = (
    TransformationReaction(
        id="transformation-1",
        strain=MaterialRef(
            identity="https://SBOL2Build.org/composite_strain_1/1", label="composite_strain_1"
        ),
        chassis=DH5ALPHA,
        plasmids=(PLASMID_1,),
    ),
    TransformationReaction(
        id="transformation-2",
        strain=MaterialRef(
            identity="https://SBOL2Build.org/composite_strain_2/1", label="composite_strain_2"
        ),
        chassis=DH5ALPHA,
        plasmids=(PLASMID_2,),
    ),
    TransformationReaction(
        id="transformation-3",
        strain=MaterialRef(
            identity="https://SBOL2Build.org/composite_strain_3/1", label="composite_strain_3"
        ),
        chassis=BL21,
        plasmids=(PLASMID_1,),
    ),
    TransformationReaction(
        id="transformation-4",
        strain=MaterialRef(
            identity="https://SBOL2Build.org/composite_strain_4/1", label="composite_strain_4"
        ),
        chassis=BL21,
        plasmids=(PLASMID_2,),
    ),
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        choices=("manual", LiquidHandler.OT2.value, LiquidHandler.FLEX.value),
        default="manual",
        help="Use a preset or manual plan. See examples.deck_layouts for layouts across handlers.",
    )
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    liquid_handler = None if args.target == "manual" else LiquidHandler(args.target)
    compiler = ProtocolCompiler()
    assembled = compiler.compile(
        AssemblyRequest(id="sbol-loop-assembly", reactions=ASSEMBLIES),
        hardware=Manual() if liquid_handler is None else assembly_deck(),
        liquid_handler=liquid_handler,
    )
    transformed = compiler.compile(
        TransformationRequest(id="heat-shock", reactions=STRAINS),
        inputs=assembled.manifest,
        hardware=Manual() if liquid_handler is None else transformation_deck(),
        liquid_handler=liquid_handler,
    )
    plated = compiler.compile(
        PlatingRequest(
            id="plating",
            sample_ids=tuple(sample.id for sample in transformed.manifest.samples),
            source_stage_id=transformed.manifest.protocol_id,
        ),
        inputs=transformed.manifest,
        hardware=Manual() if liquid_handler is None else plating_deck(),
        liquid_handler=liquid_handler,
    )
    out = Path(args.out or f"build/cloning/{args.target}")
    for name, compiled in (
        ("assembly", assembled),
        ("transformation", transformed),
        ("plating", plated),
    ):
        path = compiled.write(out / name)
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()

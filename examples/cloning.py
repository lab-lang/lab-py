"""User-defined designs and requests for the staged cloning example."""

from collections.abc import Mapping

from lab.experiments.cloning.addresses import uri_name
from lab.protocols import (
    AssemblyReaction,
    AssemblyRequest,
    MaterialRef,
    TransformationReaction,
    TransformationRequest,
)

ASSEMBLIES: list[Mapping[str, object]] = [
    {
        "Product": "https://SBOL2Build.org/composite_plasmid_1/1",
        "Backbone": "https://sbolcanvas.org/pSB1C3/1",
        "PartsList": [
            "https://sbolcanvas.org/J23101/1",
            "https://sbolcanvas.org/B0034/1",
            "https://sbolcanvas.org/GFP/1",
            "https://sbolcanvas.org/B0015/1",
        ],
        "Restriction Enzyme": "https://SBOL2Build.org/BsaI/1",
    },
    {
        "Product": "https://SBOL2Build.org/composite_plasmid_2/1",
        "Backbone": "https://sbolcanvas.org/pSB1C3/1",
        "PartsList": [
            "https://sbolcanvas.org/J23106/1",
            "https://sbolcanvas.org/B0034/1",
            "https://sbolcanvas.org/RFP/1",
            "https://sbolcanvas.org/B0015/1",
        ],
        "Restriction Enzyme": "https://SBOL2Build.org/BsaI/1",
    },
]

STRAINS: list[Mapping[str, object]] = [
    {
        "Strain": "https://SBOL2Build.org/composite_strain_1/1",
        "Chassis": "https://sbolcanvas.org/DH5alpha/1",
        "Plasmids": ["https://SBOL2Build.org/composite_plasmid_1/1"],
    },
    {
        "Strain": "https://SBOL2Build.org/composite_strain_2/1",
        "Chassis": "https://sbolcanvas.org/DH5alpha/1",
        "Plasmids": ["https://SBOL2Build.org/composite_plasmid_2/1"],
    },
    {
        "Strain": "https://SBOL2Build.org/composite_strain_3/1",
        "Chassis": "https://sbolcanvas.org/BL21/1",
        "Plasmids": ["https://SBOL2Build.org/composite_plasmid_1/1"],
    },
    {
        "Strain": "https://SBOL2Build.org/composite_strain_4/1",
        "Chassis": "https://sbolcanvas.org/BL21/1",
        "Plasmids": ["https://SBOL2Build.org/composite_plasmid_2/1"],
    },
]


def _material(identity: str) -> MaterialRef:
    return MaterialRef(identity=identity, label=uri_name(identity))


def example_assembly_request() -> AssemblyRequest:
    """The two composite plasmids in ``ASSEMBLIES``."""
    reactions = []
    for index, row in enumerate(ASSEMBLIES, start=1):
        parts = row["PartsList"]
        if not isinstance(parts, list):
            raise TypeError("PartsList must be a list.")
        reactions.append(
            AssemblyReaction(
                id=f"assembly-{index}",
                product=_material(str(row["Product"])),
                backbone=_material(str(row["Backbone"])),
                parts=tuple(_material(str(part)) for part in parts),
                restriction_enzyme=_material(str(row["Restriction Enzyme"])),
            )
        )
    return AssemblyRequest(id="sbol-loop-assembly", reactions=tuple(reactions))


def example_transformation_request() -> TransformationRequest:
    """The four strains in ``STRAINS``, each taking one assembled plasmid."""
    reactions = []
    for index, row in enumerate(STRAINS, start=1):
        plasmids = row["Plasmids"]
        if not isinstance(plasmids, list):
            raise TypeError("Plasmids must be a list.")
        reactions.append(
            TransformationReaction(
                id=f"transformation-{index}",
                strain=_material(str(row["Strain"])),
                chassis=_material(str(row["Chassis"])),
                plasmids=tuple(_material(str(plasmid)) for plasmid in plasmids),
            )
        )
    return TransformationRequest(id="heat-shock", reactions=tuple(reactions))

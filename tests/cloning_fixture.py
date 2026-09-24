"""Dictionary inputs for the legacy cloning layout and workflow APIs."""

from collections.abc import Mapping

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

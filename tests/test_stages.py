"""Stage layouts: wells, volumes, and the manual plan that chains them."""

from decimal import Decimal

import pytest

import lab
from examples.cloning import ASSEMBLIES as ASSEMBLY_REACTIONS
from examples.cloning import STRAINS as TRANSFORMATION_REACTIONS
from lab.experiments.cloning import (
    assembly_deck,
    golden_gate,
    layout_assembly,
    layout_transformation,
    plating_deck,
    plating_plates,
    transformation_deck,
)
from lab.experiments.cloning.addresses import well_name
from lab.protocols import (
    BSAI,
    AssemblyReaction,
    AssemblyRequest,
    Part,
    PlatingRequest,
    ProtocolCompiler,
    TransformationReaction,
    TransformationRequest,
)
from lab.targets import Labware, LiquidHandler, Manual
from lab.targets.lower import lower_deck
from tests.cloning_fixture import ASSEMBLIES, STRAINS


def test_sbol_assembly_assigns_column_major_products_and_water():
    layout = layout_assembly(ASSEMBLIES)
    assert list(layout.products) == [
        "https://SBOL2Build.org/composite_plasmid_1/1",
        "https://SBOL2Build.org/composite_plasmid_2/1",
    ]
    assert layout.products["https://SBOL2Build.org/composite_plasmid_1/1"] == (0,)
    assert layout.products["https://SBOL2Build.org/composite_plasmid_2/1"] == (1,)
    assert well_name(0) == "A1"
    assert well_name(1) == "B1"
    water = next(volume for _index, name, volume in layout.stocks if name == "Deionized Water")
    assert water == 4  # 2 µL in each of two five-part reactions


def test_domestication_and_manual_loop_cover_the_other_assembly_inputs():
    domestic = layout_assembly(
        [{"parts": ["part1", "part2"], "backbone": "acceptor", "restriction_enzyme": "BsaI"}]
    )
    assert [well_name(index) for index in domestic.products["part1"]] == ["A1"]
    assert [well_name(index) for index in domestic.products["part2"]] == ["B1"]
    manual = layout_assembly(
        [
            {
                "promoter": ["GVP0008"],
                "rbs": "B0034",
                "cds": "sfGFP",
                "terminator": "B0015",
                "receiver": "Odd_1",
            }
        ]
    )
    assert len(manual.reactions) == 1
    assert manual.reactions[0].destination == 0
    assert "Restriction Enzyme BSAI" in manual.positions
    assert "Odd_1" in manual.positions


def test_heat_shock_labels_follow_cell_dna_then_media():
    layout = layout_transformation(
        STRAINS[:1],
        {"https://SBOL2Build.org/composite_plasmid_1/1": ["A1"]},
        replicates=2,
    )
    assert layout.contents["A1"][0] == "composite_strain_1"
    assert layout.contents["A1"][1] == "Competent_Cell_DH5alpha"
    assert layout.contents["A1"][2] == "composite_plasmid_1"
    assert layout.contents["A1"][-1] == "Media_1"
    assert list(layout.contents) == ["A1", "B1"]


def test_plating_stays_on_one_plate_until_a_half_is_full():
    assert plating_plates(8, 2, 1) == (False, False)
    assert plating_plates(49, 2, 1) == (True, True)


def test_compiler_links_stages_with_a_manifest_not_a_deck_tuple():
    compiler = ProtocolCompiler()
    assembled = compiler.compile(
        AssemblyRequest(id="sbol-loop-assembly", reactions=ASSEMBLY_REACTIONS), hardware=Manual()
    )
    assert assembled.manifest.plasmid_locations()[
        "https://SBOL2Build.org/composite_plasmid_1/1"
    ] == ["A1"]
    assert any(call.method == "aspirate" for call in assembled.program.instructions)
    transformed = compiler.compile(
        TransformationRequest(id="heat-shock", reactions=TRANSFORMATION_REACTIONS),
        inputs=assembled.manifest,
        hardware=Manual(),
    )
    plated = compiler.compile(
        PlatingRequest(
            id="plating",
            sample_ids=tuple(sample.id for sample in transformed.manifest.samples),
            source_stage_id=transformed.manifest.protocol_id,
        ),
        inputs=transformed.manifest,
        hardware=Manual(),
    )
    assert plated.manifest.samples
    assert {call.method for call in plated.program.instructions} >= {"aspirate", "mix"}
    manual = compiler.compile(
        AssemblyRequest(id="sbol-loop-assembly", reactions=ASSEMBLY_REACTIONS), hardware=Manual()
    )
    assert "protocol.html" in manual.files
    assert "protocol.py" not in manual.files


def test_transformation_uses_caller_defined_materials():
    request = TransformationRequest(
        id="custom-transformation",
        reactions=(
            TransformationReaction(
                id="custom-reaction",
                strain=Part("https://example.org/custom-strain/1"),
                chassis=Part("https://example.org/custom-cells/1"),
                plasmids=[Part("https://example.org/custom-plasmid/1")],
            ),
        ),
    )
    compiled = ProtocolCompiler().compile(request, hardware=Manual())
    assert compiled.manifest.protocol_id == request.id
    assert {sample.material_identity for sample in compiled.manifest.samples} == {"custom-strain"}
    assert {
        sample.material_identity for sample in compiled.plan.samples if sample.role == "dna"
    } == {"custom-plasmid"}
    assert all(
        sample.contents[:3] == ("custom-strain", "Competent_Cell_custom-cells", "custom-plasmid")
        for sample in compiled.manifest.samples
    )


def test_assembly_accepts_sbol_parts():
    product = Part("https://vsv.bio/rvsv_dg_outbreak_gp/plasmid")
    insert = Part("https://vsv.bio/rvsv_dg_outbreak_gp/GP")
    reaction = AssemblyReaction(
        id="rvsv_dg_outbreak_gp-assembly",
        product=product,
        backbone=Part("https://vsv.bio/backbone/pvsv-dg"),
        parts=[insert],
        restriction_enzyme=BSAI,
    )
    assert reaction.parts == (insert,)
    compiled = ProtocolCompiler().compile(
        AssemblyRequest(id="rvsv_dg_outbreak_gp", reactions=(reaction,)),
        hardware=Manual(),
    )
    assert compiled.manifest.plasmid_locations()[product.iri] == ["A1"]
    assert any(sample.label == "Restriction Enzyme BsaI" for sample in compiled.plan.samples)


def test_part_iri_and_part_sequence_are_checked():
    assert Part("https://sbolcanvas.org/GFP/1").iri == "https://sbolcanvas.org/GFP/1"
    with pytest.raises(ValueError, match="Part IRI"):
        Part("GFP")
    with pytest.raises(ValueError, match="Part IRI"):
        Part("ATGCTAA")
    plasmid = Part("https://SBOL2Build.org/composite_plasmid_1/1")
    with pytest.raises(TypeError, match="Parts"):
        AssemblyReaction(
            id="assembly",
            product=plasmid,
            backbone=plasmid,
            parts="https://sbolcanvas.org/GFP/1",
            restriction_enzyme=BSAI,
        )
    strain = Part("https://example.org/custom-strain/1")
    with pytest.raises(TypeError, match="Plasmids"):
        TransformationReaction(
            id="transformation",
            strain=strain,
            chassis=strain,
            plasmids="https://example.org/custom-plasmid/1",
        )


@pytest.mark.parametrize("designs", [{}, {"assemblies": ASSEMBLIES}, {"strains": STRAINS}])
def test_chained_plan_requires_both_design_inputs(designs):
    with pytest.raises(TypeError, match="required positional argument"):
        golden_gate(**designs)


def test_compiling_a_deck_requires_a_liquid_handler():
    protocol = golden_gate(ASSEMBLIES, STRAINS)
    with pytest.raises(TypeError):
        lab.compile(protocol, assembly_deck())
    with pytest.raises(TypeError):
        lab.compile(protocol, assembly_deck(), liquid_handler="ot2")  # type: ignore[arg-type]


def test_cloning_deck_presets_lower_to_the_same_containers_for_opentrons():
    for liquid_handler in (LiquidHandler.OT2, LiquidHandler.FLEX):
        assert set(lower_deck(assembly_deck(), liquid_handler).labware) == {"reagents", "products"}
        assert set(lower_deck(transformation_deck(), liquid_handler).labware) == {
            "dna",
            "tubes",
            "products",
        }
        assert set(lower_deck(plating_deck(), liquid_handler).labware) == {
            "sources",
            "dilutions",
            "agar",
            "broth",
        }
    with pytest.raises(TypeError):
        lower_deck(assembly_deck(), "ot2")  # type: ignore[arg-type]


def test_ot2_lowering_uses_the_cloning_slots():
    assembly = lower_deck(assembly_deck(), LiquidHandler.OT2, (Decimal(2), Decimal(20)))
    assert assembly.labware["reagents"] == Labware(
        "opentrons_24_aluminumblock_nest_1.5ml_snapcap",
        "1",
        module="temperature module",
    )
    assert assembly.labware["products"].load_name == "nest_96_wellplate_100ul_pcr_full_skirt"
    assert assembly.labware["products"].slot == "thermocycler"
    assert assembly.pipette == "p20_single_gen2"
    assert assembly.tip_racks[0].slot == "2"

    shock = lower_deck(transformation_deck(), LiquidHandler.OT2, (Decimal(2), Decimal(60)))
    assert shock.labware["dna"].slot == "2"
    assert shock.labware["tubes"].slot == "3"
    assert shock.pipette == "p300_single_gen2"
    assert shock.mount == "right"
    assert shock.small_pipette == "p20_single_gen2"
    assert shock.tip_racks[0].slot == "6"
    assert shock.small_tip_racks[0].slot == "9"

    chilled = lower_deck(
        transformation_deck(on_module=True), LiquidHandler.OT2, (Decimal(2), Decimal(60))
    )
    assert chilled.labware["dna"].slot == "1"
    assert chilled.labware["dna"].module == "temperature module"

    plating = lower_deck(
        plating_deck(second_dilution=True, second_agar=True),
        LiquidHandler.OT2,
        (Decimal(2),),
    )
    assert {name: item.slot for name, item in plating.labware.items()} == {
        "sources": "thermocycler",
        "dilutions": "2",
        "agar": "5",
        "broth": "4",
        "dilutions_2": "3",
        "agar_2": "6",
    }
    assert plating.tip_racks[0].slot == "9"
    assert plating.labware["sources"].load_name == "biorad_96_wellplate_200ul_pcr"


def test_protocol_compiler_rejects_unsupported_star_preset_equipment():
    with pytest.raises(lab.CompileError, match="No STAR preset.*Lab DeckLayout"):
        ProtocolCompiler().compile(
            AssemblyRequest(id="sbol-loop-assembly", reactions=ASSEMBLY_REACTIONS),
            hardware=assembly_deck(),
            liquid_handler=LiquidHandler.STAR,
        )


def test_chained_plan_compiles_and_conserves_volume():
    bundle = lab.compile(golden_gate(ASSEMBLIES, STRAINS), Manual())
    initial = sum(fill.volume for resource in bundle.protocol.resources for fill in resource.fills)
    assert sum(volume for _location, volume in bundle.final_volumes) == initial
    transferred = [
        step.volume for step in bundle.protocol.steps if getattr(step, "volume", None) == 2
    ]
    assert transferred

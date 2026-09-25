"""Plan a request and allocate wells. A handler renders the same plan for its robot.

Planning does not know which pipette is mounted. Allocation names container roles
and geometry, not labware load names. Pass a Lab ``Deck`` with a supported preset or
handler-specific layouts, or a concrete backend ``Target`` for low-level integration.
"""

import json
from dataclasses import dataclass, replace
from decimal import Decimal
from itertools import groupby
from pathlib import Path

from lab.compiler import Target
from lab.compiler import compile as compile_protocol
from lab.deck import Deck
from lab.experiments.cloning.addresses import uri_name, well_name
from lab.experiments.cloning.stages.assembly import (
    AssemblyLayout,
    build_assembly,
    layout_assembly,
)
from lab.experiments.cloning.stages.plating import build_plating
from lab.experiments.cloning.stages.transformation import (
    TransformationLayout,
    build_transformation,
    layout_transformation,
)
from lab.labware import (
    COLD_BLOCK_24,
    CONICAL_RACK_15,
    CULTURE_PLATE_96,
    PCR_PLATE_96,
    TUBE_RACK_24,
    ContainerSpec,
)
from lab.protocol import Protocol
from lab.protocols.allocation import (
    AllocatedProtocolPlan,
    OutputManifest,
    SamplePlacement,
    WellRef,
)
from lab.protocols.materials import Sample, SamplePoint
from lab.protocols.plans import ProtocolPlan
from lab.protocols.program import Call, Program, Reference
from lab.protocols.requests import (
    AssemblyRequest,
    PlatingRequest,
    ProtocolRequest,
    TransformationRequest,
)
from lab.protocols.steps import (
    Distribute,
    Hold,
    Mix,
    RunTemperatureProgram,
    SetTemperature,
    Step,
    Transfer,
)
from lab.targets.liquid_handler import LiquidHandler


class _Ids:
    def __init__(self) -> None:
        self._n = 0

    def __call__(self, prefix: str) -> str:
        self._n += 1
        return f"{prefix}-{self._n}"


@dataclass(frozen=True, slots=True, kw_only=True)
class CompiledProtocol:
    plan: ProtocolPlan
    allocation: AllocatedProtocolPlan
    program: Program
    manifest: OutputManifest
    files: dict[str, str]

    def write(self, directory: str | Path) -> Path:
        """Write the handler's files and the manifest. Refuse to replace a different file."""
        directory = Path(directory)
        files = {
            **self.files,
            "manifest.json": json.dumps(self.manifest.to_dict(), indent=2, sort_keys=True) + "\n",
        }
        for name, text in files.items():
            path = directory / name
            if path.exists() and path.read_text(encoding="utf-8") != text:
                raise FileExistsError(f"{path} already contains a different artifact")
        directory.mkdir(parents=True, exist_ok=True)
        for name, text in files.items():
            (directory / name).write_text(text, encoding="utf-8")
        return directory


@dataclass(frozen=True, slots=True, kw_only=True)
class ProtocolCompiler:
    """One compiler for every method. Stages connect through ``OutputManifest``."""

    def plan(
        self,
        request: ProtocolRequest,
        *,
        inputs: OutputManifest | None = None,
    ) -> ProtocolPlan:
        return self._prepare(request, inputs=inputs)[0]

    def compile(
        self,
        request: ProtocolRequest,
        *,
        inputs: OutputManifest | None = None,
        hardware: Target | Deck,
        liquid_handler: LiquidHandler | None = None,
    ) -> CompiledProtocol:
        """Allocate the plan and render it for this hardware."""
        plan, allocated, protocol = self._prepare(request, inputs=inputs)
        files = dict(compile_protocol(protocol, hardware, liquid_handler=liquid_handler).files)
        return CompiledProtocol(
            plan=plan,
            allocation=allocated,
            program=_lower(plan, allocated),
            manifest=allocated.output_manifest(),
            files=files,
        )

    def _prepare(
        self,
        request: ProtocolRequest,
        *,
        inputs: OutputManifest | None,
    ) -> tuple[ProtocolPlan, AllocatedProtocolPlan, Protocol]:
        if isinstance(request, AssemblyRequest):
            if inputs is not None:
                raise ValueError("Assembly does not accept an upstream output manifest.")
            rows = _assembly_rows(request)
            assembly_layout = layout_assembly(rows)
            plan, allocated = _assembly_plan(request, assembly_layout)
            protocol, _products = build_assembly(rows, name=request.id)
            return plan, allocated, protocol
        if isinstance(request, TransformationRequest):
            locations = None if inputs is None else inputs.plasmid_locations()
            rows = _strain_rows(request)
            transformation_layout = layout_transformation(rows, locations)
            plan, allocated = _transformation_plan(request, transformation_layout)
            protocol, _contents = build_transformation(rows, locations, name=request.id)
            return plan, allocated, protocol
        if isinstance(request, PlatingRequest):
            if inputs is None:
                raise ValueError("Plating requires a source manifest.")
            if set(request.sample_ids) != {sample.id for sample in inputs.samples}:
                raise ValueError("Plating request samples must match the source manifest.")
            plan, allocated = _plating_plan(request, inputs)
            protocol = build_plating(
                inputs.bacterium_locations(),
                name=request.id,
                replicates=1,
                number_dilutions=2,
            )
            return plan, allocated, protocol
        raise TypeError(f"Unsupported protocol request: {type(request).__name__}")


def _assembly_rows(request: AssemblyRequest) -> list[dict[str, object]]:
    return [
        {
            "Product": reaction.product,
            "Backbone": reaction.backbone,
            "PartsList": list(reaction.parts),
            "Restriction Enzyme": reaction.restriction_enzyme,
        }
        for reaction in request.reactions
    ]


def _strain_rows(request: TransformationRequest) -> list[dict[str, object]]:
    return [
        {
            "Strain": reaction.strain,
            "Chassis": reaction.chassis,
            "Plasmids": list(reaction.plasmids),
        }
        for reaction in request.reactions
    ]


def _assembly_plan(
    request: AssemblyRequest, layout: AssemblyLayout
) -> tuple[ProtocolPlan, AllocatedProtocolPlan]:
    new = _Ids()
    stocks: list[Sample] = []
    stock_of: dict[str, str] = {}
    for _index, material, volume in layout.stocks:
        sample = Sample(
            id=new("stock"),
            material_identity=f"stock:{material}",
            label=material,
            initial_volume_ul=volume,
            role="reagent",
        )
        stocks.append(sample)
        stock_of[material] = sample.id
    products: list[tuple[Sample, int]] = []
    steps: list[Step] = [
        SetTemperature(id=new("temperature"), container_id="reagents", celsius=Decimal(4)),
        SetTemperature(id=new("temperature"), container_id="products", celsius=Decimal(4)),
    ]
    for reaction in layout.reactions:
        parents = tuple(
            dict.fromkeys(stock_of[material] for material, _volume, _mix in reaction.additions)
        )
        product = Sample(
            id=new("product"),
            material_identity=reaction.product_key,
            label=_label(reaction.product_key),
            parent_ids=parents,
            role="product",
        )
        products.append((product, reaction.destination))
        for material, volume, mix in reaction.additions:
            if mix:
                steps.append(
                    Mix(
                        id=new("mix"),
                        location=SamplePoint(sample_id=stock_of[material]),
                        volume_ul=volume,
                        repetitions=3,
                    )
                )
            steps.append(
                Transfer(
                    id=new("transfer"),
                    source=SamplePoint(sample_id=stock_of[material]),
                    destination=SamplePoint(sample_id=product.id),
                    volume_ul=volume,
                )
            )
        cycles = int(layout.total / Decimal(10))
        if cycles:
            steps.append(
                Mix(
                    id=new("mix"),
                    location=SamplePoint(sample_id=product.id),
                    volume_ul=min(layout.total, Decimal(20)),
                    repetitions=cycles,
                )
            )
    steps.extend(
        (
            RunTemperatureProgram(
                id=new("program"),
                container_id="products",
                holds=(
                    Hold(celsius=Decimal(42), minutes=Decimal(2)),
                    Hold(celsius=Decimal(16), minutes=Decimal(5)),
                ),
                cycles=75,
                lid_celsius=Decimal(42),
                block_volume_ul=Decimal(30),
            ),
            RunTemperatureProgram(
                id=new("program"),
                container_id="products",
                holds=(
                    Hold(celsius=Decimal(60), minutes=Decimal(10)),
                    Hold(celsius=Decimal(80), minutes=Decimal(10)),
                ),
                cycles=1,
                lid_celsius=Decimal(42),
                block_volume_ul=Decimal(30),
            ),
            SetTemperature(id=new("temperature"), container_id="products", celsius=Decimal(4)),
        )
    )
    plan = ProtocolPlan(
        id=request.id,
        request_id=request.id,
        samples=(*stocks, *(sample for sample, _dest in products)),
        input_sample_ids=tuple(sample.id for sample in stocks),
        output_sample_ids=tuple(sample.id for sample, _dest in products),
        steps=tuple(steps),
    )
    placements = [
        *(
            SamplePlacement(
                sample_id=sample.id,
                location=WellRef(container_id="reagents", well_name=well_name(index, 4)),
            )
            for sample, (index, _material, _volume) in zip(stocks, layout.stocks, strict=True)
        ),
        *(
            SamplePlacement(
                sample_id=sample.id,
                location=WellRef(container_id="products", well_name=well_name(destination)),
            )
            for sample, destination in products
        ),
    ]
    allocated = AllocatedProtocolPlan(
        protocol=plan,
        containers=(
            ContainerSpec(
                id="reagents",
                labware=COLD_BLOCK_24,
            ),
            ContainerSpec(
                id="products",
                labware=PCR_PLATE_96,
            ),
        ),
        placements=tuple(placements),
    )
    return plan, allocated


def _transformation_plan(
    request: TransformationRequest, layout: TransformationLayout
) -> tuple[ProtocolPlan, AllocatedProtocolPlan]:
    new = _Ids()
    dna: list[Sample] = []
    dna_at: dict[str, str] = {}
    for well, plasmid, volume in layout.dna_stocks:
        if well in dna_at:
            continue
        sample = Sample(
            id=new("dna"),
            material_identity=plasmid,
            label=plasmid,
            initial_volume_ul=volume,
            role="dna",
        )
        dna.append(sample)
        dna_at[well] = sample.id
    cells: list[Sample] = []
    cell_at: dict[int, str] = {}
    for index, material, volume in layout.cell_stocks:
        sample = Sample(
            id=new("cells"),
            material_identity=f"cells:{material}",
            label=material,
            initial_volume_ul=volume,
            role="cells",
        )
        cells.append(sample)
        cell_at[index] = sample.id
    media: list[Sample] = []
    media_at: dict[int, str] = {}
    for index, material, volume in layout.media_stocks:
        sample = Sample(
            id=new("media"),
            material_identity=f"media:{material}",
            label=material,
            initial_volume_ul=volume,
            role="media",
        )
        media.append(sample)
        media_at[index] = sample.id
    reactions: list[tuple[Sample, int]] = []
    for move in layout.cell_moves:
        well = well_name(move.destination)
        reactions.append(
            (
                Sample(
                    id=new("reaction"),
                    material_identity=move.strain,
                    label=move.strain,
                    parent_ids=(cell_at[move.tube_index],),
                    role="reaction",
                    contents=layout.contents[well],
                ),
                move.destination,
            )
        )
    steps: list[Step] = []
    if layout.chill_dna:
        steps.append(SetTemperature(id=new("temperature"), container_id="dna", celsius=Decimal(4)))
    steps.append(SetTemperature(id=new("temperature"), container_id="products", celsius=Decimal(4)))
    reaction_at = {destination: sample.id for sample, destination in reactions}
    for tube_index, group in groupby(layout.cell_moves, key=lambda move: move.tube_index):
        destinations = [move.destination for move in group]
        steps.append(
            Mix(
                id=new("mix"),
                location=SamplePoint(sample_id=cell_at[tube_index]),
                volume_ul=Decimal(50),
                repetitions=3,
            )
        )
        for destination in destinations:
            steps.append(
                Transfer(
                    id=new("transfer"),
                    source=SamplePoint(sample_id=cell_at[tube_index]),
                    destination=SamplePoint(sample_id=reaction_at[destination]),
                    volume_ul=layout.cell_volume,
                )
            )
    for dna_move in layout.dna_moves:
        steps.append(
            Mix(
                id=new("mix"),
                location=SamplePoint(sample_id=dna_at[dna_move.source_well]),
                volume_ul=layout.dna_volume,
                repetitions=3,
            )
        )
        steps.append(
            Transfer(
                id=new("transfer"),
                source=SamplePoint(sample_id=dna_at[dna_move.source_well]),
                destination=SamplePoint(sample_id=reaction_at[dna_move.destination]),
                volume_ul=layout.dna_volume,
            )
        )
    steps.append(
        RunTemperatureProgram(
            id=new("program"),
            container_id="products",
            holds=(
                Hold(celsius=Decimal(4), minutes=Decimal(30)),
                Hold(celsius=Decimal(42), minutes=Decimal(1)),
                Hold(celsius=Decimal(4), minutes=Decimal(2)),
            ),
            cycles=1,
            block_volume_ul=Decimal(30),
        )
    )
    by_tube: dict[int, list[int]] = {}
    for media_move in layout.media_moves:
        by_tube.setdefault(media_move.tube_index, []).append(media_move.destination)
    for tube_index, destinations in by_tube.items():
        steps.append(
            Distribute(
                id=new("distribute"),
                source=SamplePoint(sample_id=media_at[tube_index]),
                destinations=tuple(
                    SamplePoint(sample_id=reaction_at[destination]) for destination in destinations
                ),
                volume_ul=layout.media_volume,
                air_gap_ul=Decimal(10),
            )
        )
    steps.append(
        RunTemperatureProgram(
            id=new("program"),
            container_id="products",
            holds=(Hold(celsius=Decimal(37), minutes=Decimal(60)),),
            cycles=1,
            block_volume_ul=Decimal(30),
        )
    )
    samples = (*dna, *cells, *media, *(sample for sample, _dest in reactions))
    plan = ProtocolPlan(
        id=request.id,
        request_id=request.id,
        samples=samples,
        input_sample_ids=tuple(sample.id for sample in (*dna, *cells, *media)),
        output_sample_ids=tuple(sample.id for sample, _dest in reactions),
        steps=tuple(steps),
    )
    placements = [
        *(
            SamplePlacement(
                sample_id=dna_at[well],
                location=WellRef(container_id="dna", well_name=well),
            )
            for well, _plasmid, _volume in layout.dna_stocks
            if well in dna_at
        ),
        *(
            SamplePlacement(
                sample_id=cell_at[index],
                location=WellRef(container_id="tubes", well_name=well_name(index, 4)),
            )
            for index, _material, _volume in layout.cell_stocks
        ),
        *(
            SamplePlacement(
                sample_id=media_at[index],
                location=WellRef(container_id="tubes", well_name=well_name(index, 4)),
            )
            for index, _material, _volume in layout.media_stocks
        ),
        *(
            SamplePlacement(
                sample_id=sample.id,
                location=WellRef(container_id="products", well_name=well_name(destination)),
            )
            for sample, destination in reactions
        ),
    ]
    # DNA stocks can repeat a well; placements must be unique.
    unique: dict[str, SamplePlacement] = {}
    for placement in placements:
        unique.setdefault(placement.sample_id, placement)
    allocated = AllocatedProtocolPlan(
        protocol=plan,
        containers=(
            ContainerSpec(
                id="dna",
                labware=COLD_BLOCK_24 if layout.chill_dna else PCR_PLATE_96,
            ),
            ContainerSpec(
                id="tubes",
                labware=TUBE_RACK_24,
            ),
            ContainerSpec(
                id="products",
                labware=PCR_PLATE_96,
            ),
        ),
        placements=tuple(unique[sample.id] for sample in samples),
    )
    return plan, allocated


def _plating_plan(
    request: PlatingRequest, inputs: OutputManifest
) -> tuple[ProtocolPlan, AllocatedProtocolPlan]:
    by_id = {sample.id: sample for sample in inputs.samples}
    sources = tuple(replace(by_id[sample_id], parent_ids=()) for sample_id in request.sample_ids)
    source_well = {
        placement.sample_id: placement.location.well_name for placement in inputs.placements
    }
    new = _Ids()
    broth = Sample(
        id=new("broth"),
        material_identity="liquid_broth",
        label="liquid_broth",
        initial_volume_ul=Decimal(10000),
        role="broth",
    )
    count = len(sources)
    split = count > 48
    first: list[Sample] = []
    second: list[Sample] = []
    spots: list[tuple[Sample, str, str]] = []
    steps: list[Step] = [
        SetTemperature(id=new("temperature"), container_id="sources", celsius=Decimal(4))
    ]
    for source in sources:
        dilution = Sample(
            id=new("dilution"),
            material_identity=f"dilution:{source.id}",
            label=source.label,
            parent_ids=(broth.id, source.id),
            role="dilution",
            dilution=1,
        )
        first.append(dilution)
        steps.append(
            Transfer(
                id=new("transfer"),
                source=SamplePoint(sample_id=broth.id),
                destination=SamplePoint(sample_id=dilution.id),
                volume_ul=Decimal(18),
            )
        )
        other = Sample(
            id=new("dilution"),
            material_identity=f"dilution-2:{source.id}",
            label=source.label,
            parent_ids=(broth.id, dilution.id),
            role="dilution",
            dilution=2,
        )
        second.append(other)
        steps.append(
            Transfer(
                id=new("transfer"),
                source=SamplePoint(sample_id=broth.id),
                destination=SamplePoint(sample_id=other.id),
                volume_ul=Decimal(18),
            )
        )
    for index, source in enumerate(sources):
        steps.append(
            Transfer(
                id=new("transfer"),
                source=SamplePoint(sample_id=source.id),
                destination=SamplePoint(sample_id=first[index].id),
                volume_ul=Decimal(2),
            )
        )
        steps.append(
            Mix(
                id=new("mix"),
                location=SamplePoint(sample_id=first[index].id),
                volume_ul=Decimal(19),
                repetitions=5,
            )
        )
        steps.append(
            Transfer(
                id=new("transfer"),
                source=SamplePoint(sample_id=first[index].id),
                destination=SamplePoint(sample_id=second[index].id),
                volume_ul=Decimal(2),
            )
        )
        steps.append(
            Mix(
                id=new("mix"),
                location=SamplePoint(sample_id=second[index].id),
                volume_ul=Decimal(19),
                repetitions=5,
            )
        )
        for dilution_index, dilution in ((1, first[index]), (2, second[index])):
            spot = Sample(
                id=new("colony"),
                material_identity=source.material_identity,
                label=source.label,
                parent_ids=(dilution.id,),
                role="colony",
                contents=source.contents,
                replicate=1,
                dilution=dilution_index,
            )
            container = "agar" if dilution_index == 1 or not split else "agar_2"
            well = well_name(index if dilution_index == 1 or split else 48 + index)
            spots.append((spot, container, well))
            steps.append(
                Transfer(
                    id=new("transfer"),
                    source=SamplePoint(sample_id=dilution.id),
                    destination=SamplePoint(sample_id=spot.id),
                    volume_ul=Decimal(4),
                )
            )
    samples = (*sources, broth, *first, *second, *(spot for spot, _container, _well in spots))
    plan = ProtocolPlan(
        id=request.id,
        request_id=request.id,
        samples=samples,
        input_sample_ids=tuple(sample.id for sample in (*sources, broth)),
        output_sample_ids=tuple(spot.id for spot, _container, _well in spots),
        steps=tuple(steps),
    )
    placements = [
        *(
            SamplePlacement(
                sample_id=source.id,
                location=WellRef(container_id="sources", well_name=source_well[source.id]),
            )
            for source in sources
        ),
        SamplePlacement(sample_id=broth.id, location=WellRef(container_id="broth", well_name="A1")),
        *(
            SamplePlacement(
                sample_id=dilution.id,
                location=WellRef(container_id="dilutions", well_name=well_name(index)),
            )
            for index, dilution in enumerate(first)
        ),
        *(
            SamplePlacement(
                sample_id=dilution.id,
                location=WellRef(
                    container_id="dilutions_2" if split else "dilutions",
                    well_name=well_name(index if split else 48 + index),
                ),
            )
            for index, dilution in enumerate(second)
        ),
        *(
            SamplePlacement(
                sample_id=spot.id,
                location=WellRef(container_id=container, well_name=well),
            )
            for spot, container, well in spots
        ),
    ]
    containers = [
        ContainerSpec(
            id="sources",
            labware=CULTURE_PLATE_96,
        ),
        ContainerSpec(
            id="dilutions",
            labware=PCR_PLATE_96,
        ),
        ContainerSpec(
            id="agar",
            labware=PCR_PLATE_96,
        ),
        ContainerSpec(
            id="broth",
            labware=CONICAL_RACK_15,
        ),
    ]
    if split:
        containers.extend(
            (
                ContainerSpec(
                    id="dilutions_2",
                    labware=PCR_PLATE_96,
                ),
                ContainerSpec(
                    id="agar_2",
                    labware=PCR_PLATE_96,
                ),
            )
        )
    return plan, AllocatedProtocolPlan(
        protocol=plan, containers=tuple(containers), placements=tuple(placements)
    )


def _lower(plan: ProtocolPlan, allocation: AllocatedProtocolPlan) -> Program:
    where = {placement.sample_id: placement.location for placement in allocation.placements}

    def ref(sample_id: str) -> Reference:
        location = where[sample_id]
        return Reference(name=location.container_id, well=location.well_name)

    calls: list[Call] = []
    for step in plan.steps:
        if isinstance(step, Transfer):
            calls.append(
                Call(
                    target="pipette",
                    method="aspirate",
                    args=(step.volume_ul, ref(step.source.sample_id)),
                )
            )
            calls.append(
                Call(
                    target="pipette",
                    method="dispense",
                    args=(step.volume_ul, ref(step.destination.sample_id)),
                )
            )
        elif isinstance(step, Mix):
            calls.append(
                Call(
                    target="pipette",
                    method="mix",
                    args=(step.repetitions, step.volume_ul, ref(step.location.sample_id)),
                )
            )
        elif isinstance(step, Distribute):
            calls.append(
                Call(
                    target="pipette",
                    method="distribute",
                    kwargs=(
                        ("volume_ul", step.volume_ul),
                        ("source", ref(step.source.sample_id)),
                        (
                            "destinations",
                            tuple(ref(point.sample_id) for point in step.destinations),
                        ),
                        ("air_gap_ul", step.air_gap_ul),
                    ),
                )
            )
        elif isinstance(step, SetTemperature):
            calls.append(
                Call(target=step.container_id, method="set_temperature", args=(step.celsius,))
            )
        elif isinstance(step, RunTemperatureProgram):
            calls.append(
                Call(
                    target=step.container_id,
                    method="execute_profile",
                    kwargs=(
                        ("holds", tuple((hold.celsius, hold.minutes) for hold in step.holds)),
                        ("repetitions", step.cycles),
                        ("block_max_volume_ul", step.block_volume_ul),
                    ),
                )
            )
    return Program(instructions=tuple(calls))


def _label(identity: str) -> str:
    return uri_name(identity) if "/" in identity else identity

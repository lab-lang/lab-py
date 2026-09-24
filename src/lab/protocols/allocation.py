"""Where a plan's samples sit. Identity stays on the sample; this only adds a well."""

from dataclasses import dataclass
from decimal import Decimal

from lab.protocols.materials import Sample
from lab.protocols.plans import ProtocolPlan


@dataclass(frozen=True, slots=True, kw_only=True)
class WellRef:
    container_id: str
    well_name: str


@dataclass(frozen=True, slots=True, kw_only=True)
class SamplePlacement:
    sample_id: str
    location: WellRef


@dataclass(frozen=True, slots=True, kw_only=True)
class ContainerSpec:
    """Geometry and role of a container. A handler chooses the physical labware."""

    id: str
    rows: int
    columns: int
    capacity_ul: Decimal
    kind: str


@dataclass(frozen=True, slots=True, kw_only=True)
class OutputManifest:
    """Planned outputs of one stage. The next stage consumes this, not a well-name dict."""

    protocol_id: str
    samples: tuple[Sample, ...]
    placements: tuple[SamplePlacement, ...]

    def __post_init__(self) -> None:
        ids = {sample.id for sample in self.samples}
        if (
            len(ids) != len(self.samples)
            or len(self.placements) != len(ids)
            or {placement.sample_id for placement in self.placements} != ids
        ):
            raise ValueError("Manifest samples need unique ids and exactly one placement each.")
        if len({placement.location for placement in self.placements}) != len(self.placements):
            raise ValueError("Manifest sample locations must be unique.")

    def to_dict(self) -> dict[str, object]:
        locations = {placement.sample_id: placement.location for placement in self.placements}
        return {
            "schema_version": "1.0",
            "protocol_id": self.protocol_id,
            "state": "planned",
            "outputs": [
                {
                    "sample_id": sample.id,
                    "material_identity": sample.material.identity,
                    "label": sample.material.label,
                    "parent_sample_ids": list(sample.parent_ids),
                    "replicate": sample.replicate,
                    "source_sample_id": sample.source_sample_id,
                    "contents": list(sample.contents),
                    "container_id": locations[sample.id].container_id,
                    "well_name": locations[sample.id].well_name,
                }
                for sample in self.samples
            ],
        }

    def plasmid_locations(self) -> dict[str, list[str]]:
        locations = {placement.sample_id: placement.location for placement in self.placements}
        if len({placement.location.container_id for placement in self.placements}) > 1:
            raise ValueError("A single-plate handoff cannot represent multiple containers.")
        result: dict[str, list[str]] = {}
        for sample in self.samples:
            result.setdefault(sample.material.identity, []).append(locations[sample.id].well_name)
        return result

    def bacterium_locations(self) -> dict[str, list[str]]:
        if len({placement.location.container_id for placement in self.placements}) > 1:
            raise ValueError("A single-plate handoff cannot represent multiple containers.")
        locations = {placement.sample_id: placement.location for placement in self.placements}
        return {
            locations[sample.id].well_name: list(sample.contents or (sample.material.label,))
            for sample in self.samples
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class AllocatedProtocolPlan:
    protocol: ProtocolPlan
    containers: tuple[ContainerSpec, ...]
    placements: tuple[SamplePlacement, ...]

    def output_manifest(self) -> OutputManifest:
        ids = set(self.protocol.output_sample_ids)
        return OutputManifest(
            protocol_id=self.protocol.id,
            samples=tuple(sample for sample in self.protocol.samples if sample.id in ids),
            placements=tuple(
                placement for placement in self.placements if placement.sample_id in ids
            ),
        )

"""Sample declarations, operations, and artifacts share one immutable snapshot."""

import json
from dataclasses import FrozenInstanceError, replace

import pytest

import lab
from lab import Protocol, uL
from lab.samples import Location, Sample, SamplePlacement
from lab.targets import Manual
from lab.validation import logical_bindings, validate


def declared_protocol():
    protocol = Protocol("aliquot")
    source = protocol.container("source", contents="water", volume=100 * uL, capacity=200 * uL)
    destination = protocol.container("destination", capacity=200 * uL)
    protocol.add_sample(
        Sample(id="stock", material_identity="example:water", label="Water"),
        at=source,
        is_input=True,
    )
    protocol.add_sample(
        Sample(
            id="aliquot", material_identity="example:water", label="Aliquot", parent_ids=("stock",)
        ),
        at=destination,
        is_output=True,
    )
    protocol.transfer(source, destination, volume=10 * uL)
    return protocol


def test_manifest_and_artifacts_are_detached_from_the_builder(tmp_path):
    protocol = declared_protocol()
    compiled = lab.compile(protocol, Manual())
    files, digest = compiled.files, compiled.digest
    manifest = compiled.manifest
    assert manifest.samples == (compiled.protocol.samples[1],)
    assert manifest.placements == (compiled.protocol.placements[1],)
    plan = json.loads(files["plan.json"])
    assert plan["protocol"]["output_sample_ids"] == ["aliquot"]
    assert plan["protocol"]["placements"][1]["location"] == {
        "resource": "destination",
        "well": "A1",
    }
    assert (
        plan["protocol"]["placements"][1]["location"] == plan["protocol"]["steps"][0]["destination"]
    )
    assert json.loads(files["manifest.json"]) == manifest.to_dict()
    assert dict(compiled.final_volumes)[Location("destination", "A1")] == 10
    protocol.add_sample(
        Sample(id="extra", material_identity="example:extra", label="Extra"),
        at=protocol.container("extra", capacity=200 * uL),
        is_output=True,
    )
    protocol.name = "changed"
    assert compiled.files == files
    assert compiled.digest == digest
    assert compiled.manifest == manifest
    with pytest.raises(FrozenInstanceError):
        manifest.samples[0].label = "changed"
    compiled.write(tmp_path)
    compiled.write(tmp_path)
    assert {path.name: path.read_text() for path in tmp_path.iterdir()} == files


def test_changed_manifest_is_checked_before_any_bundle_file_is_written(tmp_path):
    compiled = lab.compile(declared_protocol(), Manual())
    (tmp_path / "manifest.json").write_text("different")
    with pytest.raises(FileExistsError, match="manifest.json"):
        compiled.write(tmp_path)
    assert [path.name for path in tmp_path.iterdir()] == ["manifest.json"]


def test_logical_output_locations_remain_distinct_from_physical_bindings():
    class Remapped:
        def prepare(self, recorded):
            prepared = Manual().prepare(recorded)
            return replace(
                prepared,
                bindings=tuple(
                    replace(binding, physical=f"device/{index}")
                    for index, binding in enumerate(prepared.bindings)
                ),
            )

    compiled = lab.compile(declared_protocol(), Remapped())
    location = compiled.manifest.placements[0].location
    assert location == Location(resource="destination", well="A1")
    assert location == compiled.protocol.steps[0].destination
    assert location == compiled.target.bindings[1].location
    assert dict(compiled.final_volumes)[location] == 10
    assert compiled.target.bindings[1].physical == "device/1"
    output = json.loads(compiled.files["manifest.json"])["outputs"][0]
    assert output["container_id"] == "destination"
    assert output["well_name"] == "A1"


@pytest.mark.parametrize(
    "case",
    [
        "duplicate_sample",
        "missing_placement",
        "unknown_well",
        "unknown_container",
        "shared_well",
        "unknown_output",
        "duplicate_output",
        "unknown_parent",
        "cycle",
    ],
)
def test_inconsistent_sample_snapshots_are_rejected(case):
    recorded = declared_protocol().snapshot()
    source, output = recorded.samples
    if case == "duplicate_sample":
        recorded = replace(recorded, samples=(source, source))
    elif case == "missing_placement":
        recorded = replace(recorded, placements=recorded.placements[:1])
    elif case in {"unknown_well", "unknown_container"}:
        location = Location(
            resource="destination" if case == "unknown_well" else "missing",
            well="Z999" if case == "unknown_well" else "A1",
        )
        recorded = replace(
            recorded,
            placements=(
                recorded.placements[0],
                SamplePlacement(sample_id=output.id, location=location),
            ),
        )
    elif case == "shared_well":
        recorded = replace(
            recorded,
            placements=(
                recorded.placements[0],
                replace(recorded.placements[1], location=recorded.placements[0].location),
            ),
        )
    elif case == "unknown_output":
        recorded = replace(recorded, output_sample_ids=("missing",))
    elif case == "duplicate_output":
        recorded = replace(recorded, output_sample_ids=(output.id, output.id))
    elif case == "unknown_parent":
        recorded = replace(recorded, samples=(source, replace(output, parent_ids=("missing",))))
    else:
        recorded = replace(recorded, samples=(replace(source, parent_ids=(output.id,)), output))
    with pytest.raises(lab.CompileError):
        validate(recorded, logical_bindings(recorded))


def test_compile_rejects_invalid_lineage_before_preparing_a_target():
    protocol = Protocol("invalid lineage")
    well = protocol.container("output", capacity=100 * uL)
    protocol.add_sample(
        Sample(
            id="output", material_identity="example:sample", label="Sample", parent_ids=("missing",)
        ),
        at=well,
        is_output=True,
    )
    protocol.manual("Review sample declarations")

    class Unreachable:
        def prepare(self, recorded):
            pytest.fail("Invalid sample metadata reached the target")

    with pytest.raises(lab.CompileError, match="Unknown parent"):
        lab.compile(protocol, Unreachable())


def test_sample_declarations_use_owned_wells_and_unique_ids_and_locations():
    protocol = declared_protocol()
    other = Protocol("other")
    sample = Sample(id="extra", material_identity="example:sample", label="Sample")
    with pytest.raises(ValueError, match="belong to this protocol"):
        protocol.add_sample(sample, at=other.container("foreign", capacity=100 * uL))
    well = protocol.container("extra", capacity=100 * uL)
    protocol.add_sample(sample, at=well)
    with pytest.raises(ValueError, match="already exists"):
        protocol.add_sample(sample, at=well)
    with pytest.raises(ValueError, match="already declared"):
        protocol.add_sample(replace(sample, id="another"), at=well)


def test_imported_samples_require_a_complete_source_reference():
    with pytest.raises(ValueError, match="both source"):
        Sample(
            id="input",
            material_identity="example:sample",
            label="Input",
            source_sample_id="upstream",
        )
    with pytest.raises(TypeError, match="tuples"):
        Sample(id="input", material_identity="example:sample", label="Input", parent_ids=[])


def test_compilation_takes_one_snapshot():
    class Counted(Protocol):
        snapshots = 0

        def snapshot(self):
            self.snapshots += 1
            return super().snapshot()

    protocol = Counted("one snapshot")
    protocol.manual("Review")
    compiled = lab.compile(protocol, Manual())
    assert protocol.snapshots == 1
    assert compiled.manifest.samples == ()
    assert "manifest.json" not in compiled.files

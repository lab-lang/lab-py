"""Core cloning types: assembly designs, transformation designs, and stage inputs."""

from collections.abc import Sequence
from dataclasses import dataclass

from lab.part import Part


def _part(value: object, *, name: str) -> None:
    if not isinstance(value, Part):
        raise TypeError(f"{name} must be a Part.")


def _parts(values: object, *, name: str) -> tuple[Part, ...]:
    if isinstance(values, (str, Part)) or not isinstance(values, Sequence):
        raise TypeError(f"{name} must be a sequence of parts.")
    if not values:
        raise ValueError(f"{name} must be a nonempty sequence of parts.")
    if not all(isinstance(value, Part) for value in values):
        raise TypeError(f"{name} must be parts.")
    return tuple(values)


BSAI = Part("https://SBOL2Build.org/BsaI/1")


@dataclass(frozen=True, slots=True, kw_only=True)
class Assembly:
    id: str
    product: Part
    backbone: Part
    parts: Sequence[Part]
    restriction_enzyme: Part

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("An assembly requires an id.")
        _part(self.product, name="Product")
        _part(self.backbone, name="Backbone")
        _part(self.restriction_enzyme, name="Restriction enzyme")
        object.__setattr__(self, "parts", _parts(self.parts, name="Parts"))


@dataclass(frozen=True, slots=True, kw_only=True)
class AssemblyRequest:
    id: str
    assemblies: tuple[Assembly, ...]

    def __post_init__(self) -> None:
        if not self.id or not self.assemblies:
            raise ValueError("An assembly request requires an id and assemblies.")
        if not isinstance(self.assemblies, tuple):
            raise TypeError("AssemblyRequest.assemblies must be a tuple.")
        if len({assembly.id for assembly in self.assemblies}) != len(self.assemblies):
            raise ValueError("Assembly ids must be unique within a request.")


@dataclass(frozen=True, slots=True, kw_only=True)
class Transformation:
    id: str
    strain: Part
    chassis: Part
    plasmids: Sequence[Part]

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("A transformation requires an id.")
        _part(self.strain, name="Strain")
        _part(self.chassis, name="Chassis")
        object.__setattr__(self, "plasmids", _parts(self.plasmids, name="Plasmids"))


@dataclass(frozen=True, slots=True, kw_only=True)
class TransformationRequest:
    id: str
    transformations: tuple[Transformation, ...]
    source_stage_id: str | None = None

    def __post_init__(self) -> None:
        if not self.id or not isinstance(self.transformations, tuple) or not self.transformations:
            raise ValueError(
                "A transformation request requires an id and a nonempty transformation tuple."
            )
        if len({transformation.id for transformation in self.transformations}) != len(
            self.transformations
        ):
            raise ValueError("Transformation ids must be unique within a request.")


@dataclass(frozen=True, slots=True, kw_only=True)
class PlatingRequest:
    id: str
    sample_ids: tuple[str, ...]
    source_stage_id: str | None = None

    def __post_init__(self) -> None:
        if not self.id or not isinstance(self.sample_ids, tuple) or not self.sample_ids:
            raise ValueError("A plating request requires an id and a nonempty sample tuple.")
        if len(set(self.sample_ids)) != len(self.sample_ids):
            raise ValueError("Plating source sample ids must be unique.")

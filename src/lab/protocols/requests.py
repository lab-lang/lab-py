"""Immutable method inputs. A request names materials; it does not assign wells."""

from collections.abc import Sequence
from dataclasses import dataclass


def _identity(value: object, *, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a nonempty identity.")


def _identities(values: object, *, name: str) -> tuple[str, ...]:
    if isinstance(values, str) or not isinstance(values, Sequence) or not values:
        raise ValueError(f"{name} must be a nonempty sequence of identities.")
    if not all(isinstance(value, str) and value for value in values):
        raise ValueError(f"{name} must be nonempty identities.")
    return tuple(values)


@dataclass(frozen=True, slots=True, kw_only=True)
class AssemblyReaction:
    id: str
    product: str
    backbone: str
    parts: Sequence[str]
    restriction_enzyme: str

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("An assembly reaction requires an id.")
        _identity(self.product, name="Product")
        _identity(self.backbone, name="Backbone")
        _identity(self.restriction_enzyme, name="Restriction enzyme")
        object.__setattr__(self, "parts", _identities(self.parts, name="Parts"))


@dataclass(frozen=True, slots=True, kw_only=True)
class AssemblyRequest:
    id: str
    reactions: tuple[AssemblyReaction, ...]
    source_stage_id: str | None = None

    def __post_init__(self) -> None:
        if not self.id or not self.reactions:
            raise ValueError("An assembly request requires an id and reactions.")
        if not isinstance(self.reactions, tuple):
            raise TypeError("AssemblyRequest.reactions must be a tuple.")
        if len({reaction.id for reaction in self.reactions}) != len(self.reactions):
            raise ValueError("Reaction ids must be unique within a request.")


@dataclass(frozen=True, slots=True, kw_only=True)
class TransformationReaction:
    id: str
    strain: str
    chassis: str
    plasmids: Sequence[str]

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("A transformation requires an id.")
        _identity(self.strain, name="Strain")
        _identity(self.chassis, name="Chassis")
        object.__setattr__(self, "plasmids", _identities(self.plasmids, name="Plasmids"))


@dataclass(frozen=True, slots=True, kw_only=True)
class TransformationRequest:
    id: str
    reactions: tuple[TransformationReaction, ...]
    source_stage_id: str | None = None

    def __post_init__(self) -> None:
        if not self.id or not isinstance(self.reactions, tuple) or not self.reactions:
            raise ValueError(
                "A transformation request requires an id and a nonempty reaction tuple."
            )
        if len({reaction.id for reaction in self.reactions}) != len(self.reactions):
            raise ValueError("Reaction ids must be unique within a request.")


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


ProtocolRequest = AssemblyRequest | TransformationRequest | PlatingRequest

"""Immutable method inputs. A request names materials; it does not assign wells."""

from collections.abc import Sequence
from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True, slots=True)
class Part:
    """An SBOL part identity."""

    iri: str

    def __post_init__(self) -> None:
        parsed = urlsplit(self.iri)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or not parsed.path.strip("/")
        ):
            raise ValueError(f"Part IRI must be an absolute http(s) URI, got {self.iri!r}.")


BSAI = Part("https://SBOL2Build.org/BsaI/1")


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


@dataclass(frozen=True, slots=True, kw_only=True)
class AssemblyReaction:
    id: str
    product: Part
    backbone: Part
    parts: Sequence[Part]
    restriction_enzyme: Part

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("An assembly reaction requires an id.")
        _part(self.product, name="Product")
        _part(self.backbone, name="Backbone")
        _part(self.restriction_enzyme, name="Restriction enzyme")
        object.__setattr__(self, "parts", _parts(self.parts, name="Parts"))


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

"""Samples keep their identity apart from the well that later holds them."""

from dataclasses import dataclass
from decimal import Decimal

from lab.protocols.requests import MaterialRef


@dataclass(frozen=True, slots=True, kw_only=True)
class Sample:
    id: str
    material: MaterialRef
    parent_ids: tuple[str, ...] = ()
    replicate: int | None = None
    initial_volume_ul: Decimal | None = None
    role: str = "material"
    source_sample_id: str | None = None
    contents: tuple[str, ...] = ()
    dilution: int | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class SamplePoint:
    sample_id: str

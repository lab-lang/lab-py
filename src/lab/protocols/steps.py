"""Logical operations. They name samples, not deck slots or SDK objects."""

from dataclasses import dataclass
from decimal import Decimal

from lab.protocols.materials import SamplePoint


@dataclass(frozen=True, slots=True, kw_only=True)
class Transfer:
    id: str
    source: SamplePoint
    destination: SamplePoint
    volume_ul: Decimal


@dataclass(frozen=True, slots=True, kw_only=True)
class Mix:
    id: str
    location: SamplePoint
    volume_ul: Decimal
    repetitions: int


@dataclass(frozen=True, slots=True, kw_only=True)
class Distribute:
    id: str
    source: SamplePoint
    destinations: tuple[SamplePoint, ...]
    volume_ul: Decimal
    air_gap_ul: Decimal | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Hold:
    celsius: Decimal
    minutes: Decimal


@dataclass(frozen=True, slots=True, kw_only=True)
class RunTemperatureProgram:
    id: str
    container_id: str
    holds: tuple[Hold, ...]
    cycles: int
    lid_celsius: Decimal | None = None
    block_volume_ul: Decimal | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class SetTemperature:
    id: str
    container_id: str
    celsius: Decimal


Step = Transfer | Mix | Distribute | RunTemperatureProgram | SetTemperature

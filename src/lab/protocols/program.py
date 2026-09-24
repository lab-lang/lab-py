"""Logical calls lowered from a plan. A handler turns these into its own script."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class Reference:
    name: str
    well: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Call:
    target: str
    method: str
    args: tuple[object, ...] = ()
    kwargs: tuple[tuple[str, object], ...] = ()
    result: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Program:
    instructions: tuple[Call, ...]

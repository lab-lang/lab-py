"""The liquid handlers this compiler renders for."""

from enum import Enum


class Handler(Enum):
    """A liquid handler. Callers pass a member; there is no default device."""

    OT2 = "ot2"
    FLEX = "flex"
    STAR = "star"

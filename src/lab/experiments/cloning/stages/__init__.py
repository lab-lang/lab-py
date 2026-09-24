"""Golden Gate assembly, heat-shock transformation, and plating.

Each stage exposes ``layout_*`` for well assignment and ``record_*`` to append
steps. ``build_*`` does both for a standalone protocol. Further cloning stages
belong in new modules here and follow that same split.
"""

from lab.experiments.cloning.stages.assembly import (
    AssemblyLayout,
    AssemblyReaction,
    AssemblyVolumes,
    build_assembly,
    layout_assembly,
    record_assembly,
)
from lab.experiments.cloning.stages.plating import (
    PlatingVolumes,
    build_plating,
    plating_plates,
    record_plating,
)
from lab.experiments.cloning.stages.transformation import (
    TransformationLayout,
    build_transformation,
    layout_transformation,
    record_transformation,
)

__all__ = [
    "AssemblyLayout",
    "AssemblyReaction",
    "AssemblyVolumes",
    "PlatingVolumes",
    "TransformationLayout",
    "build_assembly",
    "build_plating",
    "build_transformation",
    "layout_assembly",
    "layout_transformation",
    "plating_plates",
    "record_assembly",
    "record_plating",
    "record_transformation",
]

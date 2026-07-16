from collections.abc import Iterable
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PlannerConcept(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    title: str = Field(min_length=1, max_length=160)
    kind: Literal["conceptual", "coding"]
    summary_markdown: str = Field(min_length=1, max_length=400)
    prerequisites: list[str]
    citations: list[str] = Field(default_factory=list)


class ModuleSkeleton(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    title: str = Field(min_length=1, max_length=160)


class CourseSkeleton(BaseModel):
    """The first, fast planning call: module titles only, no concepts yet."""

    model_config = ConfigDict(extra="forbid")

    course_title: str = Field(min_length=1, max_length=160)
    source_set_hash: str = Field(min_length=1)
    modules: list[ModuleSkeleton] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def unique_module_ids(self) -> "CourseSkeleton":
        if len({module.id for module in self.modules}) != len(self.modules):
            raise ValueError("Module identifiers must be unique.")
        return self


class ModuleConcepts(BaseModel):
    """One module's concepts, generated and persisted after the skeleton."""

    model_config = ConfigDict(extra="forbid")

    concepts: list[PlannerConcept] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def unique_concept_ids(self) -> "ModuleConcepts":
        if len({concept.id for concept in self.concepts}) != len(self.concepts):
            raise ValueError("Concept identifiers must be unique.")
        return self


def validate_course_skeleton(skeleton: CourseSkeleton, source_set_hash: str) -> None:
    if skeleton.source_set_hash != source_set_hash:
        raise ValueError("Planner output does not match this course's source set.")


def validate_module_concepts(
    concepts: Iterable[PlannerConcept],
    available_citations: Iterable[str],
    known_concept_ids: Iterable[str],
) -> None:
    """Validate one module's concepts against everything generated before it.

    A prerequisite may only reference a concept already known: one from an
    earlier module, or an earlier concept within this same module. Because
    modules and their concepts are generated and validated in strict order,
    this makes the overall course graph acyclic by construction -- no
    separate cycle-detection pass is needed.
    """
    available_citations = set(available_citations)
    resolved = set(known_concept_ids)
    for concept in concepts:
        if concept.id in resolved:
            raise ValueError(f"Concept {concept.id} is not unique across the course.")
        if concept.id in concept.prerequisites:
            raise ValueError(f"Concept {concept.id} cannot depend on itself.")
        if not set(concept.prerequisites).issubset(resolved):
            raise ValueError(f"Concept {concept.id} references an unknown or not-yet-generated prerequisite.")
        if available_citations and not concept.citations:
            raise ValueError(f"Concept {concept.id} must cite the supplied source context.")
        if not set(concept.citations).issubset(available_citations):
            raise ValueError(f"Concept {concept.id} cites a chunk outside the source context.")
        resolved.add(concept.id)

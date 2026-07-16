from collections.abc import Iterable
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PlannerConcept(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    title: str = Field(min_length=1, max_length=160)
    kind: Literal["conceptual", "coding"]
    summary_markdown: str = Field(min_length=1, max_length=4000)
    prerequisites: list[str]
    citations: list[str] = Field(min_length=1)


class PlannerModule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    title: str = Field(min_length=1, max_length=160)
    concept_ids: list[str] = Field(min_length=1)


class CoursePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_title: str = Field(min_length=1, max_length=160)
    source_set_hash: str = Field(min_length=1)
    concepts: list[PlannerConcept] = Field(min_length=1, max_length=20)
    modules: list[PlannerModule] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def unique_identifiers(self) -> "CoursePlan":
        if len({concept.id for concept in self.concepts}) != len(self.concepts):
            raise ValueError("Concept identifiers must be unique.")
        if len({module.id for module in self.modules}) != len(self.modules):
            raise ValueError("Module identifiers must be unique.")
        return self


def validate_course_plan(plan: CoursePlan, source_set_hash: str, chunk_ids: Iterable[str]) -> None:
    if plan.source_set_hash != source_set_hash:
        raise ValueError("Planner output does not match this course's source set.")

    concept_ids = {concept.id for concept in plan.concepts}
    available_citations = set(chunk_ids)
    for concept in plan.concepts:
        if concept.id in concept.prerequisites:
            raise ValueError(f"Concept {concept.id} cannot depend on itself.")
        if not set(concept.prerequisites).issubset(concept_ids):
            raise ValueError(f"Concept {concept.id} references an unknown prerequisite.")
        if not set(concept.citations).issubset(available_citations):
            raise ValueError(f"Concept {concept.id} cites a chunk outside the source context.")

    assigned_concepts: list[str] = []
    for module in plan.modules:
        if not set(module.concept_ids).issubset(concept_ids):
            raise ValueError(f"Module {module.id} references an unknown concept.")
        assigned_concepts.extend(module.concept_ids)
    if set(assigned_concepts) != concept_ids or len(assigned_concepts) != len(concept_ids):
        raise ValueError("Every concept must appear in exactly one module.")

    prerequisites = {concept.id: set(concept.prerequisites) for concept in plan.concepts}
    resolved: set[str] = set()
    while prerequisites:
        ready = {concept_id for concept_id, required in prerequisites.items() if required <= resolved}
        if not ready:
            raise ValueError("Course concept prerequisites must be acyclic.")
        resolved.update(ready)
        for concept_id in ready:
            prerequisites.pop(concept_id)

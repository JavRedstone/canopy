from collections.abc import Iterable
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PlannerConcept(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    title: str = Field(min_length=1, max_length=160)
    kind: Literal["conceptual", "coding", "assessment"]
    summary_markdown: str = Field(min_length=1, max_length=400)
    prerequisites: list[str]
    citations: list[str] = Field(default_factory=list)


class OutlineModule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    title: str = Field(min_length=1, max_length=160)
    focus: str = Field(min_length=1, max_length=400)
    # A textbook-style topic usually has several focused activities, never one monolithic
    # lesson -- but the floor stays low so a course with a small total lesson budget can
    # still have more than one module (min_length=1 modules * a high floor here can make
    # the outline's own total-lessons budget mathematically unsatisfiable; see
    # OUTLINE_SYSTEM_PROMPT/validate_course_outline). One lesson per concept, so this is
    # also the concept count for the module. Capped at ModuleConcepts' limit so the target
    # is always achievable in a single concepts call.
    lesson_count: int = Field(ge=2, le=10)


class CourseOutline(BaseModel):
    """The first planning call: audience, objectives, and modules with a scope and a
    planned lesson count each -- but no concepts yet. The per-module lesson counts are
    the course's lesson budget, validated against the learner's requested range."""

    model_config = ConfigDict(extra="forbid")

    course_title: str = Field(min_length=1, max_length=160)
    source_set_hash: str = Field(min_length=1)
    audience: str = Field(min_length=1, max_length=600)
    objectives: list[str] = Field(min_length=1, max_length=8)
    modules: list[OutlineModule] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def unique_module_ids(self) -> "CourseOutline":
        if len({module.id for module in self.modules}) != len(self.modules):
            raise ValueError("Module identifiers must be unique.")
        return self

    @property
    def total_lessons(self) -> int:
        return sum(module.lesson_count for module in self.modules)


class ModuleConcepts(BaseModel):
    """One module's concepts, generated and persisted after the outline."""

    model_config = ConfigDict(extra="forbid")

    concepts: list[PlannerConcept] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def unique_concept_ids(self) -> "ModuleConcepts":
        if len({concept.id for concept in self.concepts}) != len(self.concepts):
            raise ValueError("Concept identifiers must be unique.")
        return self


def validate_course_outline(outline: CourseOutline, source_set_hash: str, lesson_min: int, lesson_max: int) -> None:
    if outline.source_set_hash != source_set_hash:
        raise ValueError("Planner output does not match this course's source set.")
    total = outline.total_lessons
    if not lesson_min <= total <= lesson_max:
        raise ValueError(
            f"The module lesson counts total {total}, but the course must contain between "
            f"{lesson_min} and {lesson_max} lessons. Adjust the number of modules or their "
            f"lesson_count values so the total lands in that range."
        )
    # Once a learner asks for an eight-or-more-activity course, a single module
    # becomes a catch-all "topic" rather than a useful course roadmap. Keep the
    # one-topic option for genuinely short courses (the UI's six-activity end).
    if lesson_max >= 8 and len(outline.modules) < 2:
        raise ValueError(
            "Courses with a maximum budget of 8 or more activities must contain at least two distinct modules."
        )


def validate_module_concepts(
    concepts: Iterable[PlannerConcept],
    available_citations: Iterable[str],
    known_concept_ids: Iterable[str],
    expected_count: int | None = None,
) -> None:
    """Validate one module's concepts against everything generated before it.

    A prerequisite may only reference a concept already known: one from an
    earlier module, or an earlier concept within this same module. Because
    modules and their concepts are generated and validated in strict order,
    this makes the overall course graph acyclic by construction -- no
    separate cycle-detection pass is needed. When ``expected_count`` is given,
    the module must produce exactly that many concepts so the course lands on
    the lesson budget its outline promised.
    """
    concepts = list(concepts)
    if expected_count is not None and len(concepts) != expected_count:
        raise ValueError(
            f"This module must contain exactly {expected_count} concept(s), but {len(concepts)} were generated."
        )
    kinds = [concept.kind for concept in concepts]
    if kinds.count("assessment") > 1:
        raise ValueError("Each topic may have at most one assessment checkpoint.")
    # The 3-lecture/2-lab/lecture-then-lab-then-assessment shape is prompt guidance
    # (MODULE_CONCEPTS_SYSTEM_PROMPT), not a hard requirement here -- a topic that
    # genuinely only needs two lectures or one lab shouldn't fail generation over it.
    # Display order doesn't depend on generation order either: course_map() re-sorts
    # each module's concepts by kind (conceptual, coding, assessment) on every read
    # (see CONCEPT_KIND_PHASE in services/api/app/repository.py), so a learner never
    # sees a lab before a lecture regardless of what order the planner produced them in.
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

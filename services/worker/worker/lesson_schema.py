"""The lesson bundle contract (schema_version 2).

One envelope for every lesson kind, per docs/ARCHITECTURE.md §7.2:

- ``lesson_content``   — what the learner reads (explanation, worked examples, citations).
- ``workspace``        — the coding manifest (files with visibility/editable regions);
                         ``None`` for conceptual lessons.
- ``assessment``       — how mastery evidence is produced: visible/hidden pytest files
                         and a reference solution for the ``apply`` track, quiz items for
                         the ``understand`` track, plus progressive hints.

Hidden tests and the reference solution live in the stored bundle but must never be
returned through learner-facing APIs.
"""

from collections.abc import Iterable
from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Relative, no leading "/", no ".." traversal, must be a .py file directly under the workspace.
_SAFE_PY_PATH = r"^[A-Za-z0-9_][A-Za-z0-9_./-]*\.py$"
_SLUG = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"


def _pytest_discoverable(path: str) -> bool:
    return path.startswith("test_") or path.endswith("_test.py")


class WorkspaceFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(pattern=_SAFE_PY_PATH)
    content: str = Field(min_length=1, max_length=20_000)

    @model_validator(mode="after")
    def path_is_relative_and_contained(self) -> "WorkspaceFile":
        path = PurePosixPath(self.path)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("Workspace file paths must be relative and may not traverse directories.")
        return self


class WorkspaceManifestFile(WorkspaceFile):
    """A file in the learner's workspace.

    ``visible`` files are shown and editable (the starter files the learner fills in);
    ``inspectable`` files are shown read-only as supporting context. ``editable_regions``
    optionally narrows editing to named functions; ``None`` means the whole file.
    """

    visibility: Literal["visible", "inspectable"] = "visible"
    editable_regions: list[str] | None = None


class WorkedExample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=160)
    body_markdown: str = Field(min_length=1, max_length=4000)
    citations: list[str] = Field(default_factory=list)


class QuizOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=500)
    explanation_markdown: str = Field(min_length=1, max_length=1000)


class QuizItem(BaseModel):
    """A quick-check item feeding the ``understand`` mastery track.

    ``mcq`` items use ``options``/``correct_option_index``; ``multi_select`` items use
    ``options``/``correct_option_indices`` (every correct option must be chosen);
    ``fill`` items use ``correct_answers`` (accepted strings, matched
    case-insensitively at grading time); ``short_answer`` items are free-text
    paragraphs graded by an LLM against ``rubric_markdown``. Options carry per-option
    explanations; rubrics are grading material and are never shown to the learner.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=_SLUG, max_length=64)
    kind: Literal["mcq", "multi_select", "fill", "short_answer"]
    prompt_markdown: str = Field(min_length=1, max_length=2000)
    options: list[QuizOption] = Field(default_factory=list, max_length=6)
    correct_option_index: int | None = None
    correct_option_indices: list[int] = Field(default_factory=list, max_length=6)
    correct_answers: list[str] = Field(default_factory=list, max_length=8)
    rubric_markdown: str | None = Field(default=None, max_length=2000)
    explanation_markdown: str = Field(min_length=1, max_length=2000)
    citations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def kind_fields_are_consistent(self) -> "QuizItem":
        if self.kind in {"mcq", "multi_select"}:
            if len(self.options) < 2:
                raise ValueError(f"Quiz item {self.id} needs at least two options.")
            if self.correct_answers or self.rubric_markdown:
                raise ValueError(f"Quiz item {self.id} is choice-based and must not carry correct_answers or a rubric.")
        else:
            if self.options or self.correct_option_index is not None or self.correct_option_indices:
                raise ValueError(f"Quiz item {self.id} is free-text and must not carry options.")

        if self.kind == "mcq":
            if self.correct_option_index is None or not 0 <= self.correct_option_index < len(self.options):
                raise ValueError(f"Quiz item {self.id} needs a correct_option_index within its options.")
            if self.correct_option_indices:
                raise ValueError(f"Quiz item {self.id} is single-choice and must not list correct_option_indices.")
        elif self.kind == "multi_select":
            if self.correct_option_index is not None:
                raise ValueError(f"Quiz item {self.id} is multi-select and must use correct_option_indices.")
            indices = self.correct_option_indices
            if not indices or len(set(indices)) != len(indices) or not all(0 <= index < len(self.options) for index in indices):
                raise ValueError(f"Quiz item {self.id} needs unique correct_option_indices within its options.")
        elif self.kind == "fill":
            if not self.correct_answers:
                raise ValueError(f"Quiz item {self.id} needs at least one accepted answer.")
            if self.rubric_markdown:
                raise ValueError(f"Quiz item {self.id} is fill-in and must not carry a rubric.")
        else:  # short_answer
            if not self.rubric_markdown:
                raise ValueError(f"Quiz item {self.id} needs a rubric_markdown describing a correct answer.")
            if self.correct_answers:
                raise ValueError(f"Quiz item {self.id} is rubric-graded and must not list correct_answers.")
        return self


class LessonContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=160)
    explanation_markdown: str = Field(min_length=1, max_length=12_000)
    citations: list[str] = Field(default_factory=list)
    worked_examples: list[WorkedExample] = Field(default_factory=list, max_length=4)


class Workspace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Pinned until the environment provisioner exists; a resolved immutable ID later.
    environment_id: str = Field(default="python-basic", min_length=1, max_length=200)
    files: list[WorkspaceManifestFile] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def files_are_consistent(self) -> "Workspace":
        paths = [file.path for file in self.files]
        if len(set(paths)) != len(paths):
            raise ValueError("Workspace file paths must be unique.")
        if not any(file.visibility == "visible" for file in self.files):
            raise ValueError("A workspace needs at least one visible (editable) file.")
        return self

    @property
    def visible_paths(self) -> set[str]:
        return {file.path for file in self.files if file.visibility == "visible"}


class Assessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    visible_tests: list[WorkspaceFile] = Field(default_factory=list, max_length=3)
    hidden_tests: list[WorkspaceFile] = Field(default_factory=list, max_length=5)
    quiz_items: list[QuizItem] = Field(default_factory=list, max_length=8)
    hints: list[str] = Field(default_factory=list, max_length=5)
    reference_solution_files: list[WorkspaceFile] = Field(default_factory=list, max_length=10)


class LessonBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[2] = 2
    lesson_content: LessonContent
    workspace: Workspace | None = None
    assessment: Assessment

    @model_validator(mode="after")
    def bundle_is_consistent(self) -> "LessonBundle":
        quiz_ids = [item.id for item in self.assessment.quiz_items]
        if len(set(quiz_ids)) != len(quiz_ids):
            raise ValueError("Quiz item identifiers must be unique within a lesson.")

        if self.workspace is None:
            if self.assessment.visible_tests or self.assessment.hidden_tests or self.assessment.reference_solution_files:
                raise ValueError("A lesson without a workspace cannot carry tests or a reference solution.")
            return self

        for group, name in ((self.assessment.visible_tests, "Visible test"), (self.assessment.hidden_tests, "Hidden test"), (self.assessment.reference_solution_files, "Reference solution")):
            paths = [file.path for file in group]
            if len(set(paths)) != len(paths):
                raise ValueError(f"{name} file paths must be unique.")

        if not self.assessment.visible_tests:
            raise ValueError("A coding lesson needs at least one visible test file.")
        if not self.assessment.hidden_tests:
            raise ValueError("A coding lesson needs at least one hidden test file.")

        workspace_paths = {file.path for file in self.workspace.files}
        visible_test_paths = {file.path for file in self.assessment.visible_tests}
        hidden_test_paths = {file.path for file in self.assessment.hidden_tests}
        reference_paths = {file.path for file in self.assessment.reference_solution_files}

        if reference_paths != self.workspace.visible_paths:
            raise ValueError("Reference solution must cover exactly the visible (editable) workspace file paths.")
        reference_by_path = {file.path: file.content for file in self.assessment.reference_solution_files}
        for file in self.workspace.files:
            if file.visibility == "visible" and reference_by_path.get(file.path, "").strip() == file.content.strip():
                raise ValueError(
                    f"Visible workspace file '{file.path}' is identical to the reference solution; the starter "
                    "must leave the target behavior unimplemented (a stub or deliberate gap) for the learner."
                )
        if workspace_paths & (visible_test_paths | hidden_test_paths):
            raise ValueError("Test files must not collide with workspace file paths.")
        if visible_test_paths & hidden_test_paths:
            raise ValueError("Visible and hidden test files must not share a path.")
        if not all(_pytest_discoverable(path) for path in visible_test_paths):
            raise ValueError("Every visible test file must be pytest-discoverable (test_*.py) since learners run them individually.")
        if not any(_pytest_discoverable(path) for path in hidden_test_paths):
            raise ValueError("At least one hidden test file must be pytest-discoverable (test_*.py).")

        return self


def bundle_citations(bundle: LessonBundle) -> set[str]:
    """Every chunk ID the bundle cites, across content, examples, and quiz items."""
    citations = set(bundle.lesson_content.citations)
    for example in bundle.lesson_content.worked_examples:
        citations.update(example.citations)
    for item in bundle.assessment.quiz_items:
        citations.update(item.citations)
    return citations


def validate_lesson_bundle(
    bundle: LessonBundle,
    available_citations: Iterable[str],
    *,
    require_workspace: bool = False,
    forbid_workspace: bool = False,
) -> None:
    if require_workspace and bundle.workspace is None:
        raise ValueError("A coding lesson bundle must include a workspace.")
    if forbid_workspace and bundle.workspace is not None:
        raise ValueError("A conceptual lesson bundle must not include a workspace or coding exercise.")
    if not bundle_citations(bundle).issubset(set(available_citations)):
        raise ValueError("Lesson bundle cites a chunk outside the concept's source context.")


def starter_workspace(bundle: LessonBundle) -> list[WorkspaceFile]:
    """What the learner starts from: the workspace exactly as served, plus every test.
    A correct exercise must FAIL this run — if the starter already passes, there is
    nothing left to implement."""
    if bundle.workspace is None:
        return []
    return [
        *[WorkspaceFile(path=file.path, content=file.content) for file in bundle.workspace.files],
        *bundle.assessment.visible_tests,
        *bundle.assessment.hidden_tests,
    ]


def reference_workspace(bundle: LessonBundle) -> list[WorkspaceFile]:
    """What the sandbox validates: the reference solution, read-only context files,
    and every test (visible and hidden) the solution must pass."""
    if bundle.workspace is None:
        return []
    context_files = [
        WorkspaceFile(path=file.path, content=file.content)
        for file in bundle.workspace.files
        if file.visibility == "inspectable"
    ]
    return [
        *bundle.assessment.reference_solution_files,
        *context_files,
        *bundle.assessment.visible_tests,
        *bundle.assessment.hidden_tests,
    ]

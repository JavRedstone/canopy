from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Relative, no leading "/", no ".." traversal, must be a .py file directly under the workspace.
_SAFE_PY_PATH = r"^[A-Za-z0-9_][A-Za-z0-9_./-]*\.py$"


class WorkspaceFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(pattern=_SAFE_PY_PATH)
    content: str = Field(min_length=1, max_length=20_000)


class PublicTestCase(BaseModel):
    """A learner-visible behavior check; private pytest files remain server-side."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=500)


class LessonBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    title: str = Field(min_length=1, max_length=160)
    explanation_markdown: str = Field(min_length=1, max_length=8000)
    citations: list[str] = Field(default_factory=list)
    starter_files: list[WorkspaceFile] = Field(min_length=1, max_length=10)
    test_files: list[WorkspaceFile] = Field(min_length=1, max_length=5)
    reference_solution_files: list[WorkspaceFile] = Field(min_length=1, max_length=10)
    hints: list[str] = Field(default_factory=list, max_length=5)
    public_test_cases: list[PublicTestCase] = Field(default_factory=list, max_length=6)

    @model_validator(mode="after")
    def paths_are_consistent(self) -> "LessonBundle":
        starter_paths = {file.path for file in self.starter_files}
        test_paths = {file.path for file in self.test_files}
        reference_paths = {file.path for file in self.reference_solution_files}

        if len(starter_paths) != len(self.starter_files):
            raise ValueError("Starter file paths must be unique.")
        if len(test_paths) != len(self.test_files):
            raise ValueError("Test file paths must be unique.")
        if len(reference_paths) != len(self.reference_solution_files):
            raise ValueError("Reference solution file paths must be unique.")

        if reference_paths != starter_paths:
            raise ValueError("Reference solution must cover exactly the starter file paths.")
        if starter_paths & test_paths:
            raise ValueError("Test files must not collide with starter file paths.")
        if not any(path.startswith("test_") or path.endswith("_test.py") for path in test_paths):
            raise ValueError("At least one test file must be pytest-discoverable (test_*.py).")

        return self


def validate_lesson_bundle(bundle: LessonBundle, available_citations: Iterable[str]) -> None:
    if not set(bundle.citations).issubset(set(available_citations)):
        raise ValueError("Lesson bundle cites a chunk outside the concept's source context.")


def reference_workspace(bundle: LessonBundle) -> list[WorkspaceFile]:
    """The reference solution plus the tests it must pass — what the sandbox validates."""
    return [*bundle.reference_solution_files, *bundle.test_files]

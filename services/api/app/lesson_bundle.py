"""Version-normalized reads of ``lesson_revisions.bundle_json``.

Bundles exist in two shapes: the flat v1 layout (title/starter_files/test_files at the
top level) and the v2 envelope (lesson_content/workspace/assessment). Everything in the
API reads bundles through :func:`bundle_view` so route/repository code never branches on
schema_version, and grading-only material (hidden tests, reference solution, quiz
answers) is stripped in exactly one place.
"""

from dataclasses import dataclass
from typing import Any

from app.schemas import LessonWorkspaceFile, QuizItemPreview, QuizOptionPreview, WorkedExamplePreview


@dataclass(frozen=True)
class BundleView:
    title: str
    explanation_markdown: str
    starter_files: list[LessonWorkspaceFile]
    context_files: list[LessonWorkspaceFile]
    public_test_files: list[LessonWorkspaceFile]
    hidden_test_files: list[LessonWorkspaceFile]
    hints: list[str]
    worked_examples: list[WorkedExamplePreview]
    quiz_items: list[QuizItemPreview]


def _files(entries: list[dict[str, Any]] | None) -> list[LessonWorkspaceFile]:
    return [LessonWorkspaceFile(path=entry["path"], content=entry["content"]) for entry in entries or []]


def bundle_view(bundle: dict[str, Any]) -> BundleView:
    if int(bundle.get("schema_version") or 1) >= 2:
        content = bundle.get("lesson_content") or {}
        workspace = bundle.get("workspace") or {}
        assessment = bundle.get("assessment") or {}
        manifest = workspace.get("files") or []
        return BundleView(
            title=content.get("title", ""),
            explanation_markdown=content.get("explanation_markdown", ""),
            starter_files=_files([file for file in manifest if file.get("visibility", "visible") == "visible"]),
            context_files=_files([file for file in manifest if file.get("visibility") == "inspectable"]),
            public_test_files=_files(assessment.get("visible_tests")),
            hidden_test_files=_files(assessment.get("hidden_tests")),
            hints=assessment.get("hints") or [],
            worked_examples=[
                WorkedExamplePreview(title=example["title"], body_markdown=example["body_markdown"])
                for example in content.get("worked_examples") or []
            ],
            quiz_items=[
                QuizItemPreview(
                    id=item["id"],
                    kind=item["kind"],
                    prompt_markdown=item["prompt_markdown"],
                    options=[QuizOptionPreview(text=option["text"]) for option in item.get("options") or []],
                )
                for item in assessment.get("quiz_items") or []
            ],
        )
    return BundleView(
        title=bundle.get("title", ""),
        explanation_markdown=bundle.get("explanation_markdown", ""),
        starter_files=_files(bundle.get("starter_files")),
        context_files=[],
        public_test_files=_files(bundle.get("public_test_files")),
        hidden_test_files=_files(bundle.get("test_files")),
        hints=bundle.get("hints") or [],
        worked_examples=[],
        quiz_items=[],
    )

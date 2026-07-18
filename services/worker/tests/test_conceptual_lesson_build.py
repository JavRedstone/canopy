from types import SimpleNamespace

from worker.lesson_build import LessonBuilder
from worker.lesson_schema import LessonContentBundle


def _conceptual_content_dict(**content_overrides: object) -> dict:
    return {
        "lesson_content": {
            "title": "Why tokens expire",
            "explanation_markdown": "Expiry bounds the damage of a leaked token.",
            "citations": [],
            "worked_examples": [],
            **content_overrides,
        },
        "quiz_items": [
            {
                "id": "expiry-check",
                "kind": "fill",
                "prompt_markdown": "A token past its exp claim is ____.",
                "options": [],
                "correct_option_index": None,
                "correct_answers": ["rejected"],
                "explanation_markdown": "Expiry is a hard boundary.",
                "citations": [],
            }
        ],
        "hints": [],
    }


class FakeRequest:
    def __init__(self, data: list[dict[str, object]]) -> None:
        self.data = data

    def execute(self) -> SimpleNamespace:
        return SimpleNamespace(data=self.data)


class FakeClient:
    def __init__(self) -> None:
        self.rpc_calls: list[tuple[str, dict[str, object]]] = []

    def rpc(self, function: str, arguments: dict[str, object]) -> FakeRequest:
        self.rpc_calls.append((function, arguments))
        if function == "claim_lesson_build":
            return FakeRequest(
                [
                    {
                        "lesson_definition_id": arguments["p_lesson_definition_id"],
                        "course_version_id": "version-id",
                        "concept_id": "concept-id",
                        "concept_slug": "token-expiry",
                        "concept_kind": "conceptual",
                        "concept_title": "Why tokens expire",
                        "summary_markdown": "Expiry bounds damage.",
                        "citations_json": [],
                        "next_revision": 1,
                    }
                ]
            )
        return FakeRequest([])


class ExplodingSandbox:
    def run_pytest(self, files: object) -> None:
        raise AssertionError("Conceptual lessons must never reach the sandbox.")


class FakeResponses:
    def __init__(self, outputs: list[object]) -> None:
        self.outputs = list(outputs)
        self.calls: list[dict[str, object]] = []

    def parse(self, **kwargs: object) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(output_parsed=self.outputs.pop(0))


def _builder(responses: FakeResponses) -> LessonBuilder:
    builder = LessonBuilder.__new__(LessonBuilder)
    builder.settings = SimpleNamespace(
        builder_model="lesson_build", conceptual_builder_model="concept_regeneration", queue_visibility_seconds=300
    )
    builder.client = FakeClient()
    builder.openai = SimpleNamespace(responses=responses)
    builder.sandbox = ExplodingSandbox()
    return builder


def test_conceptual_lesson_builds_without_sandbox_and_stores_validated_bundle() -> None:
    responses = FakeResponses([LessonContentBundle.model_validate(_conceptual_content_dict())])
    builder = _builder(responses)

    builder.build_lesson("lesson-id")

    assert [call["model"] for call in responses.calls] == ["concept_regeneration"]
    applied = dict(builder.client.rpc_calls)["apply_lesson_bundle"]
    assert applied["p_validation_status"] == "validated"
    assert applied["p_bundle"]["workspace"] is None
    assert applied["p_bundle"]["assessment"]["quiz_items"][0]["id"] == "expiry-check"


def test_conceptual_content_with_out_of_context_citation_is_regenerated_with_feedback() -> None:
    # A workspace can no longer slip into conceptual content by mistake -- LessonContentBundle
    # has no such field -- so the retry-with-feedback path is exercised via an out-of-context
    # citation instead, the other real failure mode content generation can still hit.
    responses = FakeResponses(
        [
            LessonContentBundle.model_validate(_conceptual_content_dict(citations=["chunk-outside-context"])),
            LessonContentBundle.model_validate(_conceptual_content_dict()),
        ]
    )
    builder = _builder(responses)

    builder.build_lesson("lesson-id")

    assert len(responses.calls) == 2
    feedback_message = responses.calls[1]["input"][-1]
    assert feedback_message["role"] == "user"
    assert "cites a chunk outside" in feedback_message["content"]
    applied = dict(builder.client.rpc_calls)["apply_lesson_bundle"]
    assert applied["p_validation_status"] == "validated"
    assert applied["p_bundle"]["workspace"] is None

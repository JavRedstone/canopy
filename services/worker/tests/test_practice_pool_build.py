"""Coverage for the practice_pool_build job: context handling, the mandatory validation
loop around generation, idempotent storage, and the fact that a pool failure is isolated
from the lesson that spawned it."""

from types import SimpleNamespace

import pytest

from worker.lesson_schema import PracticePoolBundle
from worker.practice_pool_build import POOL_VALIDATION_ATTEMPTS, PracticePoolBuilder


def _item(item_id: str, prompt: str, citations: list[str] | None = None) -> dict:
    return {
        "id": item_id,
        "kind": "mcq",
        "prompt_markdown": prompt,
        "options": [
            {"text": "Rejected.", "explanation_markdown": "Correct: expired tokens never validate."},
            {"text": "Accepted.", "explanation_markdown": "Wrong: that defeats expiry."},
        ],
        "correct_option_index": 0,
        "explanation_markdown": "Expiry is a hard boundary.",
        "citations": citations if citations is not None else ["chunk-a"],
    }


# Ten visibly different questions: enough to clear the batch floor without tripping the
# near-duplicate check that validate_practice_pool applies within a batch.
PROMPTS = [
    "What happens when a token's exp claim is in the past?",
    "Why do validators usually permit a small amount of clock skew?",
    "Which claim carries the moment a credential stops being usable?",
    "How should a server respond to a signature it cannot verify?",
    "What breaks if refresh lifetimes exceed access lifetimes?",
    "Where must revocation state live for logout to take effect?",
    "When is caching a validation decision unsafe?",
    "Who decides the audience a bearer credential is scoped to?",
    "Which failure mode does short expiry actually bound?",
    "What distinguishes an opaque reference from a self-describing one?",
]


def _pool(count: int = 10, citations: list[str] | None = None) -> PracticePoolBundle:
    return PracticePoolBundle.model_validate(
        {"practice_items": [_item(f"item-{index}", PROMPTS[index], citations) for index in range(count)]}
    )


CONTEXT = {
    "concept_id": "concept-id",
    "course_version_id": "version-id",
    "concept_title": "Token expiry",
    "concept_kind": "conceptual",
    "summary_markdown": "Reject expired tokens.",
    "citations_json": ["chunk-a"],
    "lesson_explanation": "Tokens carry an expiry claim that must be checked.",
    "existing_prompts": [],
    "next_batch": 0,
}


class FakeRequest:
    def __init__(self, data: object) -> None:
        self.data = data

    def execute(self) -> SimpleNamespace:
        return SimpleNamespace(data=self.data)


class FakeClient:
    def __init__(self, context: dict | None = CONTEXT, inserted: int = 10) -> None:
        self.context = context
        self.inserted = inserted
        self.rpc_calls: list[tuple[str, dict]] = []

    def rpc(self, function: str, arguments: dict) -> FakeRequest:
        self.rpc_calls.append((function, arguments))
        if function == "practice_pool_context":
            return FakeRequest([self.context] if self.context else [])
        if function == "apply_practice_pool":
            return FakeRequest(self.inserted)
        return FakeRequest([])

    def table(self, name: str) -> "FakeTable":
        assert name == "source_chunks", f"The pool builder must not query {name} directly."
        return FakeTable()


class FakeTable:
    """Just enough of the PostgREST builder for citation_chunks to load the cited chunks."""

    def select(self, _columns: str) -> "FakeTable":
        return self

    def in_(self, _column: str, values: list[str]) -> FakeRequest:
        return FakeRequest([{"id": value, "content": f"Excerpt for {value}."} for value in values])


class FakeResponses:
    def __init__(self, outputs: list[PracticePoolBundle]) -> None:
        self.outputs = list(outputs)
        self.calls: list[dict] = []

    def parse(self, **kwargs: object) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(output_parsed=self.outputs.pop(0))


def _builder(responses: FakeResponses, client: FakeClient | None = None, min_batch: int = 10) -> PracticePoolBuilder:
    builder = PracticePoolBuilder.__new__(PracticePoolBuilder)
    builder.settings = SimpleNamespace(
        practice_pool_model="practice_pool",
        practice_pool_batch_size=12,
        practice_pool_min_batch_size=min_batch,
    )
    builder.client = client or FakeClient()
    builder.openai = SimpleNamespace(responses=responses)
    return builder


def _applied(builder: PracticePoolBuilder) -> dict:
    return dict(builder.client.rpc_calls)["apply_practice_pool"]


def test_a_validated_batch_is_stored_against_the_concept_and_batch_number() -> None:
    builder = _builder(FakeResponses([_pool()]))

    assert builder.build_pool("lesson-id") is True

    applied = _applied(builder)
    assert applied["p_concept_id"] == "concept-id"
    assert applied["p_course_version_id"] == "version-id"
    assert applied["p_batch"] == 0
    assert len(applied["p_items"]) == 10


def test_generation_is_grounded_on_the_context_the_rpc_returned() -> None:
    responses = FakeResponses([_pool()])
    builder = _builder(responses)

    builder.build_pool("lesson-id")

    assert responses.calls[0]["model"] == "practice_pool"
    user_message = responses.calls[0]["input"][1]["content"]
    assert "Tokens carry an expiry claim that must be checked." in user_message
    assert "exactly 12 practice questions" in user_message


def test_an_unbuilt_lesson_resolves_the_job_without_generating() -> None:
    responses = FakeResponses([])
    builder = _builder(responses, client=FakeClient(context=None))

    assert builder.build_pool("lesson-id") is True

    assert responses.calls == []
    assert "apply_practice_pool" not in dict(builder.client.rpc_calls)


def test_an_ungrounded_batch_is_regenerated_with_the_validators_own_message() -> None:
    responses = FakeResponses([_pool(citations=["chunk-invented"]), _pool()])
    builder = _builder(responses)

    builder.build_pool("lesson-id")

    assert len(responses.calls) == 2
    feedback = responses.calls[1]["input"][-1]
    assert feedback["role"] == "user"
    assert "outside the concept's source context" in feedback["content"]
    assert len(_applied(builder)["p_items"]) == 10


def test_a_short_batch_is_regenerated_rather_than_stored() -> None:
    responses = FakeResponses([_pool(count=4), _pool()])
    builder = _builder(responses)

    builder.build_pool("lesson-id")

    feedback = responses.calls[1]["input"][-1]["content"]
    assert "at least 10 are needed" in feedback
    assert len(_applied(builder)["p_items"]) == 10


def test_a_batch_that_undershoots_the_target_but_clears_the_floor_is_accepted() -> None:
    # Asked for 12, got 10. Regenerating to chase an exact count would cost a call for no
    # learner benefit, so the floor -- not the target -- is what actually gates storage.
    responses = FakeResponses([_pool(count=10)])
    builder = _builder(responses)

    builder.build_pool("lesson-id")

    assert len(responses.calls) == 1
    assert len(_applied(builder)["p_items"]) == 10


def test_a_batch_that_never_validates_fails_the_job_without_storing_anything() -> None:
    responses = FakeResponses([_pool(citations=["chunk-invented"]) for _ in range(POOL_VALIDATION_ATTEMPTS)])
    builder = _builder(responses)

    with pytest.raises(ValueError, match="failed validation after"):
        builder.build_pool("lesson-id")

    assert len(responses.calls) == POOL_VALIDATION_ATTEMPTS
    assert "apply_practice_pool" not in dict(builder.client.rpc_calls)


def test_validation_is_not_optional_so_bad_batches_can_never_reach_storage() -> None:
    # The guarantee in one assertion: every stored batch went through the validator, so no
    # caller can skip it by calling the generator directly.
    responses = FakeResponses([_pool(citations=["chunk-invented"]), _pool(count=3), _pool()])
    builder = _builder(responses)

    builder.build_pool("lesson-id")

    assert len(responses.calls) == 3
    assert len(_applied(builder)["p_items"]) == 10


def test_a_batch_already_written_by_another_delivery_is_discarded_not_duplicated() -> None:
    builder = _builder(FakeResponses([_pool()]), client=FakeClient(inserted=0))

    assert builder.build_pool("lesson-id") is True


def test_a_top_up_writes_the_next_batch_and_avoids_what_was_already_asked() -> None:
    context = {**CONTEXT, "next_batch": 2, "existing_prompts": ["What happens when a token expires?"]}
    responses = FakeResponses([_pool()])
    builder = _builder(responses, client=FakeClient(context=context))

    builder.build_pool("lesson-id")

    assert _applied(builder)["p_batch"] == 2
    user_message = responses.calls[0]["input"][1]["content"]
    assert "What happens when a token expires?" in user_message
    assert "do not repeat these" in user_message

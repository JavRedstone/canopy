"""Coverage for the practice-pool generation pass: the batch schema, the grounding and
anti-repetition validation, and the prompt/context the generator actually sends."""

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from worker.lesson_agent import generate_practice_pool
from worker.lesson_schema import (
    PracticePoolBundle,
    practice_pool_citations,
    validate_practice_pool,
)


def _item(item_id: str = "expiry-check", prompt: str = "What happens when a token's exp claim is in the past?", **overrides: object) -> dict:
    base = {
        "id": item_id,
        "kind": "mcq",
        "prompt_markdown": prompt,
        "options": [
            {"text": "It is rejected.", "explanation_markdown": "Correct: expired tokens must never validate."},
            {"text": "It is accepted.", "explanation_markdown": "Wrong: that would defeat expiry entirely."},
        ],
        "correct_option_index": 0,
        "explanation_markdown": "Expiry is a hard boundary, not a hint.",
        "citations": ["chunk-a"],
    }
    base.update(overrides)
    return base


def _pool(*items: dict) -> PracticePoolBundle:
    return PracticePoolBundle.model_validate({"practice_items": list(items or (_item(),))})


class FakeResponses:
    def __init__(self, parsed: PracticePoolBundle | None) -> None:
        self.parsed = parsed
        self.calls: list[dict] = []

    def parse(self, **kwargs: object) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(output_parsed=self.parsed)


def _client(parsed: PracticePoolBundle | None) -> tuple[SimpleNamespace, FakeResponses]:
    responses = FakeResponses(parsed)
    return SimpleNamespace(responses=responses), responses


CHUNKS = [{"id": "chunk-a", "content": "Tokens carry an exp claim."}]


def test_batch_rejects_duplicate_item_ids() -> None:
    with pytest.raises(ValidationError):
        _pool(_item("expiry-check"), _item("expiry-check", prompt="Something else entirely here."))


def test_batch_must_not_be_empty() -> None:
    with pytest.raises(ValidationError):
        PracticePoolBundle.model_validate({"practice_items": []})


def test_batch_reuses_the_quiz_item_shape_rules() -> None:
    # A choice item with a rubric is invalid for a pool question exactly as it is for a
    # lesson quiz item -- the pool inherits QuizItem's validation wholesale.
    with pytest.raises(ValidationError):
        _pool(_item(rubric_markdown="Should mention expiry."))


def test_citations_are_collected_across_every_item() -> None:
    pool = _pool(
        _item("expiry-check", citations=["chunk-a"]),
        _item("clock-skew", prompt="Why allow a small clock skew when validating?", citations=["chunk-b"]),
    )
    assert practice_pool_citations(pool) == {"chunk-a", "chunk-b"}


def test_validation_rejects_a_citation_outside_the_concept_context() -> None:
    pool = _pool(_item(citations=["chunk-invented"]))
    with pytest.raises(ValueError, match="outside the concept's source context"):
        validate_practice_pool(pool, ["chunk-a"])


def test_validation_accepts_an_ungrounded_batch_when_the_concept_has_no_sources() -> None:
    # The existing zero-source policy: no chunks means empty citations, not a failure.
    validate_practice_pool(_pool(_item(citations=[])), [])


def test_validation_rejects_two_questions_that_are_the_same_reworded() -> None:
    pool = _pool(
        _item("expiry-check", prompt="What happens when a token's exp claim is in the past?"),
        _item("expiry-check-2", prompt="What happens when the exp claim of a token is in the past?"),
    )
    with pytest.raises(ValueError, match="nearly the same question"):
        validate_practice_pool(pool, ["chunk-a"])


def test_validation_allows_distinct_questions_sharing_the_concept_vocabulary() -> None:
    pool = _pool(
        _item("expiry-check", prompt="What happens when a token's exp claim is in the past?"),
        _item("skew-window", prompt="Why do validators usually allow a small amount of clock skew?"),
    )
    validate_practice_pool(pool, ["chunk-a"])


def test_validation_rejects_a_question_the_lesson_quiz_already_asks() -> None:
    pool = _pool(_item(prompt="What happens when a token's exp claim is in the past?"))
    with pytest.raises(ValueError, match="already been asked"):
        validate_practice_pool(
            pool,
            ["chunk-a"],
            existing_prompts=["What happens when the exp claim of a token is in the past?"],
        )


def test_validation_passes_when_a_top_up_asks_something_new() -> None:
    pool = _pool(_item("skew-window", prompt="Why do validators usually allow a small amount of clock skew?"))
    validate_practice_pool(
        pool,
        ["chunk-a"],
        existing_prompts=["What happens when a token's exp claim is in the past?"],
    )


def test_generation_returns_the_parsed_batch() -> None:
    expected = _pool()
    client, _ = _client(expected)
    pool = generate_practice_pool(
        client,
        "practice_pool",
        concept_title="Token expiry",
        concept_summary="Reject expired tokens.",
        lesson_explanation="Tokens carry an expiry claim that must be checked.",
        chunks=CHUNKS,
        count=12,
    )
    assert pool is expected


def test_generation_raises_when_the_model_returns_nothing_structured() -> None:
    client, _ = _client(None)
    with pytest.raises(ValueError, match="no structured practice items"):
        generate_practice_pool(
            client,
            "practice_pool",
            concept_title="Token expiry",
            concept_summary="Reject expired tokens.",
            lesson_explanation="Tokens carry an expiry claim.",
            chunks=CHUNKS,
            count=12,
        )


def test_generation_grounds_on_the_explanation_the_chunks_and_the_requested_count() -> None:
    client, responses = _client(_pool())
    generate_practice_pool(
        client,
        "practice_pool",
        concept_title="Token expiry",
        concept_summary="Reject expired tokens.",
        lesson_explanation="Tokens carry an expiry claim that must be checked.",
        chunks=CHUNKS,
        count=12,
    )
    user_message = responses.calls[0]["input"][1]["content"]
    assert "Tokens carry an expiry claim that must be checked." in user_message
    assert "[chunk-a]" in user_message
    assert "exactly 12 practice questions" in user_message


def test_generation_passes_already_asked_questions_so_the_model_writes_around_them() -> None:
    client, responses = _client(_pool())
    generate_practice_pool(
        client,
        "practice_pool",
        concept_title="Token expiry",
        concept_summary="Reject expired tokens.",
        lesson_explanation="Tokens carry an expiry claim.",
        chunks=CHUNKS,
        count=12,
        existing_prompts=["What happens when a token's exp claim is in the past?"],
    )
    user_message = responses.calls[0]["input"][1]["content"]
    assert "do not repeat these" in user_message
    assert "What happens when a token's exp claim is in the past?" in user_message


def test_first_batch_says_so_rather_than_listing_nothing() -> None:
    client, responses = _client(_pool())
    generate_practice_pool(
        client,
        "practice_pool",
        concept_title="Token expiry",
        concept_summary="Reject expired tokens.",
        lesson_explanation="Tokens carry an expiry claim.",
        chunks=CHUNKS,
        count=12,
    )
    assert "None yet" in responses.calls[0]["input"][1]["content"]


def test_pool_questions_are_standalone_not_interleaved() -> None:
    # Pool items are served a few at a time out of context, so the lesson's inline
    # {{quiz:N}} marker instruction must never reach this prompt.
    client, responses = _client(_pool())
    generate_practice_pool(
        client,
        "practice_pool",
        concept_title="Token expiry",
        concept_summary="Reject expired tokens.",
        lesson_explanation="Tokens carry an expiry claim.",
        chunks=CHUNKS,
        count=12,
    )
    system_message = responses.calls[0]["input"][0]["content"]
    assert "{{quiz:" not in system_message
    assert "stand completely on its own" in system_message


def test_rejection_feedback_is_appended_for_a_retry() -> None:
    client, responses = _client(_pool())
    generate_practice_pool(
        client,
        "practice_pool",
        concept_title="Token expiry",
        concept_summary="Reject expired tokens.",
        lesson_explanation="Tokens carry an expiry claim.",
        chunks=CHUNKS,
        count=12,
        feedback="Practice items a and b ask nearly the same question.",
    )
    retry_message = responses.calls[0]["input"][-1]["content"]
    assert "ask nearly the same question" in retry_message


def test_zero_source_concepts_are_told_to_leave_citations_empty() -> None:
    client, responses = _client(_pool())
    generate_practice_pool(
        client,
        "practice_pool",
        concept_title="Token expiry",
        concept_summary="Reject expired tokens.",
        lesson_explanation="Tokens carry an expiry claim.",
        chunks=[],
        count=12,
    )
    assert "empty citations list" in responses.calls[0]["input"][0]["content"]

from datetime import datetime, timedelta

from app.practice import (
    DEFAULT_SESSION_COUNT,
    MIN_UNSEEN_BEFORE_TOP_UP,
    PracticeAttempt,
    PracticeItem,
    PracticeSession,
    concept_accuracy,
    concepts_needing_top_up,
    select_practice_items,
)


EPOCH = datetime(2026, 7, 1, 12, 0, 0)


def item(item_id: str, concept_id: str = "loops", kind: str = "mcq") -> PracticeItem:
    return PracticeItem(id=item_id, concept_id=concept_id, kind=kind)


def attempt(item_id: str, concept_id: str = "loops", *, correct: bool, minutes: int = 0) -> PracticeAttempt:
    return PracticeAttempt(
        item_id=item_id,
        concept_id=concept_id,
        correct=correct,
        created_at=EPOCH + timedelta(minutes=minutes),
    )


def pool(count: int, concept_id: str = "loops") -> list[PracticeItem]:
    return [item(f"{concept_id}-{index}", concept_id) for index in range(count)]


def ids(items: list[PracticeItem]) -> list[str]:
    return [selected.id for selected in items]


def test_serves_up_to_the_requested_count() -> None:
    selected = select_practice_items(pool(10), [], PracticeSession(count=4))
    assert len(selected) == 4


def test_never_serves_more_than_the_pool_holds() -> None:
    selected = select_practice_items(pool(3), [], PracticeSession(count=10))
    assert len(selected) == 3


def test_selection_is_deterministic_for_a_given_seed() -> None:
    session = PracticeSession(count=5, seed=99)
    first = select_practice_items(pool(20), [], session)
    second = select_practice_items(pool(20), [], session)
    assert ids(first) == ids(second)


def test_different_seeds_shuffle_differently() -> None:
    items = pool(20)
    first = select_practice_items(items, [], PracticeSession(count=8, seed=1))
    second = select_practice_items(items, [], PracticeSession(count=8, seed=2))
    assert ids(first) != ids(second)


def test_zero_or_negative_count_serves_nothing() -> None:
    assert select_practice_items(pool(5), [], PracticeSession(count=0)) == []
    assert select_practice_items(pool(5), [], PracticeSession(count=-3)) == []


def test_unseen_filter_excludes_anything_already_answered() -> None:
    items = pool(4)
    attempts = [attempt("loops-0", correct=True), attempt("loops-2", correct=False)]
    selected = select_practice_items(items, attempts, PracticeSession(count=4, filter="unseen"))
    assert sorted(ids(selected)) == ["loops-1", "loops-3"]


def test_unseen_filter_on_an_exhausted_pool_serves_nothing_rather_than_repeating() -> None:
    items = pool(2)
    attempts = [attempt("loops-0", correct=True), attempt("loops-1", correct=True)]
    assert select_practice_items(items, attempts, PracticeSession(count=5, filter="unseen")) == []


def test_all_filter_includes_seen_questions() -> None:
    items = pool(3)
    attempts = [attempt("loops-0", correct=True)]
    selected = select_practice_items(items, attempts, PracticeSession(count=3, filter="all"))
    assert sorted(ids(selected)) == ["loops-0", "loops-1", "loops-2"]


def test_missed_filter_serves_only_the_most_recent_misses() -> None:
    items = pool(4)
    attempts = [
        attempt("loops-0", correct=False),
        attempt("loops-1", correct=True),
        # Missed at first, since corrected -- no longer worth retrying.
        attempt("loops-2", correct=False, minutes=1),
        attempt("loops-2", correct=True, minutes=5),
    ]
    selected = select_practice_items(items, attempts, PracticeSession(count=4, filter="missed"))
    assert ids(selected) == ["loops-0"]


def test_rotation_prefers_unseen_then_least_recently_seen() -> None:
    items = pool(3)
    attempts = [
        attempt("loops-0", correct=True, minutes=50),
        attempt("loops-2", correct=True, minutes=10),
    ]
    selected = select_practice_items(items, attempts, PracticeSession(count=3, filter="all"))
    # Never seen first; then the one seen longest ago; the freshest repeat comes last.
    assert ids(selected) == ["loops-1", "loops-2", "loops-0"]


def test_rotation_prefers_the_least_often_seen_question() -> None:
    items = pool(2)
    attempts = [
        attempt("loops-0", correct=True, minutes=1),
        attempt("loops-0", correct=True, minutes=2),
        attempt("loops-1", correct=True, minutes=3),
    ]
    selected = select_practice_items(items, attempts, PracticeSession(count=2, filter="all"))
    # loops-1 was seen more recently but only once; seen-count outranks recency.
    assert ids(selected) == ["loops-1", "loops-0"]


def test_shuffle_still_respects_the_rotation_tiers() -> None:
    items = pool(6)
    attempts = [attempt(f"loops-{index}", correct=True) for index in range(3)]
    selected = select_practice_items(items, attempts, PracticeSession(count=6, filter="all", seed=7))
    # The three never-seen questions all come before the three repeats, in some order.
    assert sorted(ids(selected)[:3]) == ["loops-3", "loops-4", "loops-5"]


def test_multi_concept_session_interleaves_concepts() -> None:
    items = pool(3, "loops") + pool(3, "recursion")
    selected = select_practice_items(items, [], PracticeSession(count=4, order="course"))
    concepts = [selected_item.concept_id for selected_item in selected]
    assert concepts == ["loops", "recursion", "loops", "recursion"]


def test_course_order_follows_the_order_items_were_supplied() -> None:
    items = pool(2, "recursion") + pool(2, "loops")
    selected = select_practice_items(items, [], PracticeSession(count=4, order="course"))
    assert ids(selected) == ["recursion-0", "loops-0", "recursion-1", "loops-1"]


def test_weakest_first_leads_with_the_lowest_accuracy_concept() -> None:
    items = pool(2, "loops") + pool(2, "recursion") + pool(2, "types")
    attempts = [
        attempt("loops-0", "loops", correct=True),
        attempt("loops-1", "loops", correct=True),
        attempt("recursion-0", "recursion", correct=False),
        attempt("recursion-1", "recursion", correct=False),
    ]
    selected = select_practice_items(
        items, attempts, PracticeSession(count=3, order="weakest", filter="all")
    )
    concepts = [selected_item.concept_id for selected_item in selected]
    # Recursion (all wrong) leads, then untried types, then loops (all right) last.
    assert concepts == ["recursion", "types", "loops"]


def test_untried_concepts_sort_between_weak_and_strong_ones() -> None:
    attempts = [
        attempt("loops-0", "loops", correct=False),
        attempt("types-0", "types", correct=True),
    ]
    assert concept_accuracy(attempts, "loops") < concept_accuracy(attempts, "untried")
    assert concept_accuracy(attempts, "untried") < concept_accuracy(attempts, "types")


def test_concept_accuracy_is_neutral_with_no_evidence() -> None:
    assert concept_accuracy([], "loops") == 0.5


def test_a_single_miss_does_not_zero_out_a_concept() -> None:
    assert concept_accuracy([attempt("loops-0", correct=False)], "loops") > 0.0


def test_round_robin_drains_remaining_concepts_when_one_runs_out() -> None:
    items = pool(1, "loops") + pool(3, "recursion")
    selected = select_practice_items(items, [], PracticeSession(count=4, order="course"))
    assert ids(selected) == ["loops-0", "recursion-0", "recursion-1", "recursion-2"]


def test_no_question_is_served_twice_in_one_session() -> None:
    items = pool(5, "loops") + pool(5, "recursion")
    selected = select_practice_items(items, [], PracticeSession(count=10, seed=3))
    assert len(ids(selected)) == len(set(ids(selected)))


def test_empty_pool_serves_nothing() -> None:
    assert select_practice_items([], [], PracticeSession(count=5)) == []


def test_default_session_is_a_ten_question_unseen_shuffle() -> None:
    session = PracticeSession()
    assert (session.count, session.order, session.filter) == (DEFAULT_SESSION_COUNT, "shuffle", "unseen")


def test_top_up_flags_concepts_low_on_unseen_questions() -> None:
    items = pool(MIN_UNSEEN_BEFORE_TOP_UP, "loops") + pool(MIN_UNSEEN_BEFORE_TOP_UP, "recursion")
    # One loops question answered drops it below the threshold; recursion is still stocked.
    attempts = [attempt("loops-0", "loops", correct=True)]
    assert concepts_needing_top_up(items, attempts) == ["loops"]


def test_top_up_flags_a_fully_exhausted_concept() -> None:
    items = pool(2, "loops")
    attempts = [attempt("loops-0", correct=True), attempt("loops-1", correct=False)]
    assert concepts_needing_top_up(items, attempts) == ["loops"]


def test_top_up_leaves_a_well_stocked_concept_alone() -> None:
    items = pool(MIN_UNSEEN_BEFORE_TOP_UP + 5, "loops")
    assert concepts_needing_top_up(items, []) == []


def test_top_up_flags_a_concept_whose_pool_was_never_generated() -> None:
    # The concept most in need of a top-up has no items to be counted from, so the scope's
    # concept list has to be passed in separately -- counting only what exists would leave
    # a concept whose generation failed permanently empty.
    items = pool(MIN_UNSEEN_BEFORE_TOP_UP + 5, "loops")
    assert concepts_needing_top_up(items, [], concept_ids=["loops", "recursion"]) == ["recursion"]


def test_top_up_scope_order_is_preserved_for_concepts_with_and_without_items() -> None:
    items = pool(1, "loops")
    assert concepts_needing_top_up(items, [], concept_ids=["types", "loops"]) == ["types", "loops"]

"""Selection engine for the low-stakes practice question pool.

Given the practice items in scope, the learner's answer history, and the session
options they chose, this module decides *which questions to serve next*. It answers
three questions at once:

- **Non-repeat** -- prefer questions the learner has never seen, then the ones they
  saw longest ago, so a pool feels like a pool rather than a loop.
- **Spread** -- a session that spans several concepts interleaves them round-robin
  instead of draining one concept before touching the next.
- **Order / filter** -- the learner-chosen session options: shuffle, weakest-first,
  or course order; unseen-only, everything, or "retry the ones I missed".

Like :mod:`app.mastery` this is deliberately pure and side-effect free -- no clock, no
IO, no database -- so it can be unit-tested in isolation. The repository owns reading
``practice_items`` and the ``practice_attempts`` ledger; the router owns grading and
writing. Randomness is drawn from a caller-supplied seed so a given session is
reproducible. See docs/architecture/PRACTICE_QUESTION_POOL.md for the full design.
"""

import random
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Sequence


PracticeOrder = Literal["shuffle", "weakest", "course"]
PracticeFilter = Literal["unseen", "all", "missed"]

# How many questions a session serves when the learner does not ask for a specific
# length. "Endless" mode is the caller paging for another batch of this size.
DEFAULT_SESSION_COUNT = 10

# A concept's pool is topped up once it has fewer than this many never-seen questions
# left for the learner. Kept above zero so the next batch is generated *before* the
# learner hits an empty pool rather than after.
MIN_UNSEEN_BEFORE_TOP_UP = 3


@dataclass(frozen=True)
class PracticeItem:
    """One question in the pool, stripped to what selection needs.

    Items are supplied in **course order**; the engine preserves that ordering when the
    learner asks for it, so no separate concept-ordering argument is needed.
    """

    id: str
    concept_id: str
    kind: str


@dataclass(frozen=True)
class PracticeAttempt:
    """One row of the ``practice_attempts`` ledger: this learner answered this item."""

    item_id: str
    concept_id: str
    correct: bool
    created_at: datetime


@dataclass(frozen=True)
class PracticeSession:
    """The session options the learner picked before starting a drill."""

    count: int = DEFAULT_SESSION_COUNT
    order: PracticeOrder = "shuffle"
    filter: PracticeFilter = "unseen"
    seed: int = 0


@dataclass(frozen=True)
class _ItemHistory:
    """What the ledger says about one item, rolled up."""

    seen_count: int
    last_seen: float
    last_correct: bool


def _item_history(attempts: Sequence[PracticeAttempt]) -> dict[str, _ItemHistory]:
    """Roll the attempt ledger up per item: how often, how recently, and how it went last."""
    latest: dict[str, PracticeAttempt] = {}
    counts: Counter[str] = Counter()
    for attempt in attempts:
        counts[attempt.item_id] += 1
        seen = latest.get(attempt.item_id)
        if seen is None or attempt.created_at > seen.created_at:
            latest[attempt.item_id] = attempt
    return {
        item_id: _ItemHistory(
            seen_count=counts[item_id],
            # A float keeps naive and aware timestamps comparable in the same sort key.
            last_seen=attempt.created_at.timestamp(),
            last_correct=attempt.correct,
        )
        for item_id, attempt in latest.items()
    }


def concept_accuracy(attempts: Sequence[PracticeAttempt], concept_id: str) -> float:
    """Laplace-smoothed practice accuracy for one concept, used to rank weakest-first.

    Smoothing means a concept with no attempts scores a neutral 0.5 -- it interleaves
    among the concepts the learner is coping with rather than being treated as either
    the weakest or the strongest -- and a single miss does not slam a concept to 0.0.
    """
    answered = [attempt for attempt in attempts if attempt.concept_id == concept_id]
    correct = sum(1 for attempt in answered if attempt.correct)
    return (correct + 1) / (len(answered) + 2)


def _passes_filter(item: PracticeItem, history: dict[str, _ItemHistory], filter: PracticeFilter) -> bool:
    if filter == "all":
        return True
    if filter == "unseen":
        return item.id not in history
    # "missed": the questions they got wrong *most recently* -- an item they since got
    # right is no longer a miss worth retrying.
    seen = history.get(item.id)
    return seen is not None and not seen.last_correct


def _concept_visit_order(
    concept_ids: list[str],
    attempts: Sequence[PracticeAttempt],
    session: PracticeSession,
    rng: random.Random,
) -> list[str]:
    """The order concepts take their turn in the round-robin.

    ``concept_ids`` arrives in course order, which is both the answer for
    ``order="course"`` and the deterministic tie-break for the other two.
    """
    if session.order == "course":
        return concept_ids
    if session.order == "weakest":
        position = {concept_id: index for index, concept_id in enumerate(concept_ids)}
        return sorted(concept_ids, key=lambda cid: (concept_accuracy(attempts, cid), position[cid]))
    shuffled = list(concept_ids)
    rng.shuffle(shuffled)
    return shuffled


def select_practice_items(
    items: Sequence[PracticeItem],
    attempts: Sequence[PracticeAttempt],
    session: PracticeSession,
) -> list[PracticeItem]:
    """Return the next batch of practice questions, in the order they should be served.

    ``items`` are every question in the learner's chosen scope, in course order;
    ``attempts`` is their full ledger for that scope. The result holds at most
    ``session.count`` items and is empty when the filter leaves nothing eligible --
    an exhausted pool is reported to the learner, never silently refilled with
    questions they just answered.
    """
    if session.count <= 0:
        return []

    history = _item_history(attempts)
    eligible = [item for item in items if _passes_filter(item, history, session.filter)]
    if not eligible:
        return []

    rng = random.Random(session.seed)
    # Shuffling breaks ties *within* a rotation tier rather than replacing the tier
    # ordering, so "shuffle" still serves unseen questions before repeats.
    tiebreak = {
        item.id: (rng.random() if session.order == "shuffle" else float(index))
        for index, item in enumerate(eligible)
    }

    by_concept: dict[str, list[PracticeItem]] = {}
    for item in eligible:
        by_concept.setdefault(item.concept_id, []).append(item)
    for concept_items in by_concept.values():
        concept_items.sort(key=lambda item: _rotation_key(item, history, tiebreak))

    visit_order = _concept_visit_order(list(by_concept), attempts, session, rng)
    return _round_robin(by_concept, visit_order, session.count)


def _rotation_key(
    item: PracticeItem,
    history: dict[str, _ItemHistory],
    tiebreak: dict[str, float],
) -> tuple[int, float, float]:
    """Never-seen first, then least-often-seen, then longest-ago, then the tie-break."""
    seen = history.get(item.id)
    if seen is None:
        return (0, 0.0, tiebreak[item.id])
    return (seen.seen_count, seen.last_seen, tiebreak[item.id])


def _round_robin(
    by_concept: dict[str, list[PracticeItem]],
    visit_order: list[str],
    count: int,
) -> list[PracticeItem]:
    """Take one question from each concept in turn until the session is full or the
    eligible pool runs dry."""
    queues = {concept_id: list(by_concept[concept_id]) for concept_id in visit_order}
    selected: list[PracticeItem] = []
    while len(selected) < count:
        served_this_pass = False
        for concept_id in visit_order:
            queue = queues[concept_id]
            if not queue:
                continue
            selected.append(queue.pop(0))
            served_this_pass = True
            if len(selected) == count:
                return selected
        if not served_this_pass:
            break
    return selected


def concepts_needing_top_up(
    items: Sequence[PracticeItem],
    attempts: Sequence[PracticeAttempt],
    concept_ids: Sequence[str] = (),
    minimum_unseen: int = MIN_UNSEEN_BEFORE_TOP_UP,
) -> list[str]:
    """Concepts whose pool is running low on never-seen questions, in course order.

    Drives the top-up endpoint: the API enqueues another generation batch for these
    before the learner exhausts them. ``concept_ids`` is every concept in scope, which
    must be passed separately from ``items`` -- a concept whose pool is *empty* has no
    items to be counted from, and it is exactly the one most in need of a top-up.
    """
    history = _item_history(attempts)
    unseen: dict[str, int] = {concept_id: 0 for concept_id in concept_ids}
    for item in items:
        unseen.setdefault(item.concept_id, 0)
        if item.id not in history:
            unseen[item.concept_id] += 1
    return [concept_id for concept_id, remaining in unseen.items() if remaining < minimum_unseen]

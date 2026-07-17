"""Per-concept, dual-track Bayesian Knowledge Tracing (BKT).

Every concept carries two independent mastery estimates: ``understand`` (recall /
explanation, fed by quiz answers) and ``apply`` (implementing the idea in code, fed by
coding submissions and transfer exercises). Each is a single probability ``p(L)`` that
the learner has mastered that facet, updated one assessed observation at a time with the
classic BKT rule (Corbett & Anderson):

    condition on the observation, then apply the learning transition.

The math here is deliberately pure and side-effect free so it can be unit-tested in
isolation; the repository owns reading/writing the ``observations`` ledger and the
``mastery`` cache. See docs/IDEA.md "The Mastery Model" for the full specification.
"""

from dataclasses import dataclass
from typing import Literal


Track = Literal["understand", "apply"]
AssessmentKind = Literal["quiz_mcq", "quiz_fill", "coding_submission", "transfer_exercise"]

# A track is "mastered" once its probability crosses this bar. Conceptual concepts need
# only ``understand``; coding concepts need ``apply`` as well (see ``concept_mastered``).
MASTERY_THRESHOLD = 0.95

# A prerequisite is flagged for review when the learner has *practiced* it (it has
# observations) yet its relevant track sits below this softer bar -- meaning the idea a
# later concept builds on is shaky. Kept well under the mastery bar so it flags genuine
# weakness, not merely "not perfect yet". Unpracticed prerequisites are not nagged about:
# the sequential course already routes the learner through them the first time.
REVIEW_THRESHOLD = 0.6


@dataclass(frozen=True)
class BktParams:
    """The four BKT parameters for one (track, assessment_kind) pair.

    - ``p_l0`` prior probability the concept is already mastered (cold-start seed).
    - ``p_t``  probability of learning it on any single practice opportunity.
    - ``p_g``  guess rate: passing without mastery (higher for 4-option MCQs).
    - ``p_s``  slip rate: failing despite mastery.
    """

    p_l0: float
    p_t: float
    p_g: float
    p_s: float


# Conservative, track-specific priors used until enough real observations accumulate to
# refit per concept (docs/IDEA.md cold-start section). Choice items are easier to guess
# than free-text ones; applied coding is hardest to fake, so its guess rate is lowest.
DEFAULT_PARAMS: dict[AssessmentKind, BktParams] = {
    "quiz_mcq": BktParams(p_l0=0.20, p_t=0.15, p_g=0.30, p_s=0.10),
    "quiz_fill": BktParams(p_l0=0.20, p_t=0.15, p_g=0.10, p_s=0.12),
    "coding_submission": BktParams(p_l0=0.15, p_t=0.12, p_g=0.10, p_s=0.10),
    "transfer_exercise": BktParams(p_l0=0.15, p_t=0.10, p_g=0.05, p_s=0.10),
}

# Which mastery track each assessment kind updates.
TRACK_BY_ASSESSMENT: dict[AssessmentKind, Track] = {
    "quiz_mcq": "understand",
    "quiz_fill": "understand",
    "coding_submission": "apply",
    "transfer_exercise": "apply",
}

# Quiz item kinds (from the lesson bundle) collapse onto the two quiz assessment kinds:
# anything chosen from a fixed option set is guess-prone like an MCQ; anything typed is
# treated like a fill-in for parameter purposes.
_ASSESSMENT_BY_QUIZ_KIND: dict[str, AssessmentKind] = {
    "mcq": "quiz_mcq",
    "multi_select": "quiz_mcq",
    "fill": "quiz_fill",
    "short_answer": "quiz_fill",
}


def assessment_for_quiz_kind(quiz_kind: str) -> AssessmentKind:
    """Map a bundle quiz item ``kind`` to the BKT assessment kind that scores it."""
    return _ASSESSMENT_BY_QUIZ_KIND.get(quiz_kind, "quiz_mcq")


def params_for(assessment_kind: AssessmentKind) -> BktParams:
    return DEFAULT_PARAMS[assessment_kind]


def track_for(assessment_kind: AssessmentKind) -> Track:
    return TRACK_BY_ASSESSMENT[assessment_kind]


def bkt_update(p_l: float, correct: bool, params: BktParams) -> float:
    """Return the posterior ``p(L)`` after one observation, learning transition included.

    First condition the prior on whether the observation was correct, then move it toward
    mastery by the learning rate. The result is clamped to ``[0, 1]``; a correct answer can
    only ever raise it and an incorrect one can only ever lower it (before the transition),
    which keeps the estimate explainable to the learner.
    """
    p_l = min(1.0, max(0.0, p_l))
    if correct:
        numerator = p_l * (1.0 - params.p_s)
        denominator = numerator + (1.0 - p_l) * params.p_g
    else:
        numerator = p_l * params.p_s
        denominator = numerator + (1.0 - p_l) * (1.0 - params.p_g)
    conditioned = numerator / denominator if denominator > 0 else p_l
    learned = conditioned + (1.0 - conditioned) * params.p_t
    return min(1.0, max(0.0, learned))


def relevant_track(kind: str) -> Track:
    """The track that carries a concept's core skill: applied code for coding labs,
    conceptual understanding for everything else."""
    return "apply" if kind == "coding" else "understand"


def prerequisite_needs_review(
    kind: str,
    p_understand: float | None,
    p_apply: float | None,
    understand_opportunities: int,
    apply_opportunities: int,
) -> bool:
    """True when a prerequisite has been assessed but its relevant track is below the review
    bar -- the signal that drives the prerequisite-review recommendation."""
    if relevant_track(kind) == "apply":
        p, opportunities = p_apply, apply_opportunities
    else:
        p, opportunities = p_understand, understand_opportunities
    return opportunities > 0 and p is not None and p < REVIEW_THRESHOLD


def concept_mastered(
    kind: str,
    p_understand: float | None,
    p_apply: float | None,
) -> bool:
    """Decision rule: has this concept been mastered given its two track estimates?

    Coding concepts must clear the bar on ``apply`` (and on ``understand`` too when they
    carry any quiz observations); everything else needs only ``understand``. ``None`` means
    a track has no observations yet, so it cannot count toward mastery.
    """
    understood = p_understand is not None and p_understand >= MASTERY_THRESHOLD
    applied = p_apply is not None and p_apply >= MASTERY_THRESHOLD
    if kind == "coding":
        # Understanding is only required if the lab actually assessed it.
        return applied and (understood or p_understand is None)
    return understood

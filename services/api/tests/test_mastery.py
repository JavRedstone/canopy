from app.mastery import (
    DEFAULT_PARAMS,
    MASTERY_THRESHOLD,
    MIN_STRUGGLE_OPPORTUNITIES,
    PRACTICE_CEILING,
    REVIEW_THRESHOLD,
    STRUGGLE_THRESHOLD,
    BktParams,
    assessment_for_quiz_kind,
    bkt_update,
    concept_mastered,
    concept_struggling,
    params_for,
    practice_update,
    prerequisite_needs_review,
    relevant_track,
    track_for,
)


PARAMS = BktParams(p_l0=0.2, p_t=0.15, p_g=0.2, p_s=0.1)


def test_correct_answer_raises_the_estimate() -> None:
    assert bkt_update(0.2, correct=True, params=PARAMS) > 0.2


def test_incorrect_answer_lowers_the_conditioned_estimate() -> None:
    # The learning transition nudges upward afterwards, but a wrong answer with these
    # params must still leave the learner below where a correct one would land.
    wrong = bkt_update(0.5, correct=False, params=PARAMS)
    right = bkt_update(0.5, correct=True, params=PARAMS)
    assert wrong < right


def test_repeated_correct_answers_converge_toward_mastery() -> None:
    p = 0.2
    for _ in range(15):
        p = bkt_update(p, correct=True, params=PARAMS)
    assert p >= MASTERY_THRESHOLD


def test_estimate_stays_within_unit_interval() -> None:
    for correct in (True, False):
        for start in (0.0, 0.01, 0.5, 0.99, 1.0):
            result = bkt_update(start, correct=correct, params=PARAMS)
            assert 0.0 <= result <= 1.0


def test_out_of_range_prior_is_clamped_before_use() -> None:
    assert 0.0 <= bkt_update(1.5, correct=False, params=PARAMS) <= 1.0
    assert 0.0 <= bkt_update(-0.3, correct=True, params=PARAMS) <= 1.0


def test_learning_transition_lifts_a_correct_answer_above_pure_conditioning() -> None:
    # With p_t > 0 the estimate always ends above the conditioned posterior.
    no_learning = BktParams(p_l0=0.2, p_t=0.0, p_g=0.2, p_s=0.1)
    assert bkt_update(0.4, correct=True, params=PARAMS) > bkt_update(0.4, correct=True, params=no_learning)


def test_quiz_kinds_map_to_the_understand_track_assessment_kinds() -> None:
    assert assessment_for_quiz_kind("mcq") == "quiz_mcq"
    assert assessment_for_quiz_kind("multi_select") == "quiz_mcq"
    assert assessment_for_quiz_kind("fill") == "quiz_fill"
    assert assessment_for_quiz_kind("short_answer") == "quiz_fill"
    # Unknown kinds fall back to the guess-prone MCQ profile rather than crashing.
    assert assessment_for_quiz_kind("something_new") == "quiz_mcq"


def test_tracks_route_quiz_to_understand_and_coding_to_apply() -> None:
    assert track_for("quiz_mcq") == "understand"
    assert track_for("quiz_fill") == "understand"
    assert track_for("coding_submission") == "apply"
    assert track_for("transfer_exercise") == "apply"


def test_every_assessment_kind_has_default_params() -> None:
    for kind in ("quiz_mcq", "quiz_fill", "coding_submission", "transfer_exercise", "practice"):
        assert isinstance(params_for(kind), BktParams)
    assert set(DEFAULT_PARAMS) == {"quiz_mcq", "quiz_fill", "coding_submission", "transfer_exercise", "practice"}


def test_practice_feeds_the_understand_track_with_the_highest_guess_rate() -> None:
    assert track_for("practice") == "understand"
    # Retryable, self-revealing, low-stakes: one correct practice answer is the weakest
    # evidence of mastery any assessment kind produces.
    assert params_for("practice").p_g > max(
        params_for(kind).p_g for kind in ("quiz_mcq", "quiz_fill", "coding_submission", "transfer_exercise")
    )


def test_practice_credit_raises_a_low_estimate() -> None:
    assert practice_update(0.2, params_for("practice")) > 0.2


def test_practice_credit_cannot_cross_the_practice_ceiling() -> None:
    p = 0.2
    for _ in range(50):
        p = practice_update(p, params_for("practice"))
    assert p <= PRACTICE_CEILING
    # Drilling forever must never certify mastery -- that still needs graded evidence.
    assert p < MASTERY_THRESHOLD


def test_practice_credit_never_lowers_an_already_stronger_estimate() -> None:
    # A learner who cleared the ceiling on graded work keeps it; practice does not drag
    # them back down to 0.85.
    earned = 0.97
    assert practice_update(earned, params_for("practice")) >= earned


def test_practice_ceiling_sits_below_the_mastery_bar() -> None:
    assert PRACTICE_CEILING < MASTERY_THRESHOLD


def test_conceptual_concept_masters_on_understanding_alone() -> None:
    assert concept_mastered("conceptual", p_understand=0.96, p_apply=None) is True
    assert concept_mastered("conceptual", p_understand=0.90, p_apply=None) is False


def test_relevant_track_is_apply_for_coding_and_understand_otherwise() -> None:
    assert relevant_track("coding") == "apply"
    assert relevant_track("conceptual") == "understand"
    assert relevant_track("assessment") == "understand"


def test_prerequisite_review_flags_only_practiced_but_shaky_concepts() -> None:
    low = REVIEW_THRESHOLD - 0.1
    high = REVIEW_THRESHOLD + 0.2
    # Practiced and shaky on the relevant track -> review.
    assert prerequisite_needs_review("conceptual", low, None, understand_opportunities=3, apply_opportunities=0) is True
    assert prerequisite_needs_review("coding", None, low, understand_opportunities=0, apply_opportunities=2) is True
    # Practiced and solid -> no review.
    assert prerequisite_needs_review("conceptual", high, None, understand_opportunities=3, apply_opportunities=0) is False
    # Never practiced -> not nagged, even with no data.
    assert prerequisite_needs_review("conceptual", None, None, understand_opportunities=0, apply_opportunities=0) is False
    # For a coding prereq the apply track decides; a weak quiz score alone doesn't flag it.
    assert prerequisite_needs_review("coding", low, high, understand_opportunities=2, apply_opportunities=1) is False


def test_struggling_needs_enough_practice_and_a_low_relevant_track() -> None:
    low = STRUGGLE_THRESHOLD - 0.1
    high = STRUGGLE_THRESHOLD + 0.2
    # Enough tries and still weak on the relevant track -> struggling.
    assert concept_struggling("conceptual", low, None, MIN_STRUGGLE_OPPORTUNITIES, 0) is True
    assert concept_struggling("coding", None, low, 0, MIN_STRUGGLE_OPPORTUNITIES) is True
    # One unlucky slip is not yet struggling -- the minimum-opportunities guard holds it back.
    assert concept_struggling("conceptual", low, None, MIN_STRUGGLE_OPPORTUNITIES - 1, 0) is False
    # Practiced enough but coping -> not struggling.
    assert concept_struggling("conceptual", high, None, MIN_STRUGGLE_OPPORTUNITIES + 1, 0) is False
    # A coding concept is judged on apply; a weak quiz score alone doesn't count as struggling.
    assert concept_struggling("coding", low, high, MIN_STRUGGLE_OPPORTUNITIES, 1) is False
    # No observations on the relevant track -> nothing to call struggling.
    assert concept_struggling("conceptual", None, None, 0, 0) is False


def test_coding_concept_requires_the_apply_track() -> None:
    # Applied bar cleared, no quiz on the lab -> mastered.
    assert concept_mastered("coding", p_understand=None, p_apply=0.97) is True
    # Applied bar not cleared -> not mastered, however strong the understanding.
    assert concept_mastered("coding", p_understand=0.99, p_apply=0.80) is False
    # Lab that also quizzes: both tracks must clear the bar.
    assert concept_mastered("coding", p_understand=0.80, p_apply=0.99) is False
    assert concept_mastered("coding", p_understand=0.99, p_apply=0.99) is True

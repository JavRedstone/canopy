from app.mastery import (
    DEFAULT_PARAMS,
    MASTERY_THRESHOLD,
    REVIEW_THRESHOLD,
    BktParams,
    assessment_for_quiz_kind,
    bkt_update,
    concept_mastered,
    params_for,
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
    for kind in ("quiz_mcq", "quiz_fill", "coding_submission", "transfer_exercise"):
        assert isinstance(params_for(kind), BktParams)
    assert set(DEFAULT_PARAMS) == {"quiz_mcq", "quiz_fill", "coding_submission", "transfer_exercise"}


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


def test_coding_concept_requires_the_apply_track() -> None:
    # Applied bar cleared, no quiz on the lab -> mastered.
    assert concept_mastered("coding", p_understand=None, p_apply=0.97) is True
    # Applied bar not cleared -> not mastered, however strong the understanding.
    assert concept_mastered("coding", p_understand=0.99, p_apply=0.80) is False
    # Lab that also quizzes: both tracks must clear the bar.
    assert concept_mastered("coding", p_understand=0.80, p_apply=0.99) is False
    assert concept_mastered("coding", p_understand=0.99, p_apply=0.99) is True

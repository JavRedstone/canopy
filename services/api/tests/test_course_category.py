from app.course_category import accent_colors_for, category_for


def test_category_matches_keywords_in_title_or_goal() -> None:
    assert category_for("Machine Learning Foundations", "Learn ML from first principles") == "ml"
    assert category_for("API auth", "Learn JWT validation") == "security"
    # "Poetry" and "history" (not "code"/"api"/etc.) -- and deliberately avoids "random"/
    # "seldom"-style words, which the substring-only heuristic this mirrors (course-category.ts)
    # would false-positive-match against the "web" keyword "dom".
    assert category_for("Poetry appreciation", "Understand 19th century verse") == "default"


def test_accent_colors_are_a_consistent_pair_per_category() -> None:
    accent, tint = accent_colors_for("Machine Learning Foundations", "Learn ML")
    assert accent == "#312e81"
    assert tint == "#eef2ff"

    default_accent, default_tint = accent_colors_for("Nothing in particular", "")
    assert default_accent == "#334155"
    assert default_tint == "#f1f5f9"

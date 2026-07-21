"""Regression cover for the coursebook renderer's markdown fidelity and layout safety.

These assert on the reportlab markup/flowables rather than on rasterized pages: every defect
below shipped as *silently wrong output* (literal "####", pipes instead of a table, code
running off the page edge) rather than an exception, so a smoke test that only checks for a
%PDF- header would not have caught any of them.
"""

from datetime import UTC, datetime
from uuid import uuid4

from reportlab.platypus import Preformatted, Table

from app.schemas import (
    ConceptDetailResponse,
    CourseMapConcept,
    CourseMapModule,
    CourseMapResponse,
    CourseSummary,
    LessonPreview,
    WorkedExamplePreview,
)
from app.textbook_pdf import (
    _CONTENT_WIDTH,
    _build_styles,
    _code_cards,
    _inline,
    _markdown_flowables,
    _math_markup,
    _Theme,
    render_textbook_pdf,
)

THEME = _Theme(accent="#312e81", tint="#eef2ff")
STYLES = _build_styles(THEME)


def _flowables(markdown: str, width: float = _CONTENT_WIDTH) -> list:
    return list(_markdown_flowables(markdown, STYLES, THEME, width))


def test_links_render_as_hyperlinks_not_literal_markdown() -> None:
    markup = _inline("See the [official docs](https://example.com/a_b) for more.")

    assert '<link href="https://example.com/a_b"' in markup
    assert "[official docs]" not in markup
    # The URL's underscore must not be eaten by the italic rule.
    assert "<i>" not in markup


def test_emphasis_renders_but_snake_case_survives() -> None:
    assert "<i>italic</i>" in _inline("some *italic* text")
    assert "<i>italic</i>" in _inline("some _italic_ text")
    assert "<i>" not in _inline("call some_snake_case_name here")


def test_inline_code_is_escaped_and_not_reformatted() -> None:
    markup = _inline("generics like `List<int>` and `a ** b`")

    assert "&lt;int&gt;" in markup
    # The asterisks inside the code span must not be read as emphasis.
    assert "a ** b" in markup


def test_headings_beyond_level_three_are_not_literal() -> None:
    flowables = _flowables("#### A fourth-level heading")

    assert len(flowables) == 1
    assert "####" not in flowables[0].text


def test_pipe_table_becomes_a_real_table() -> None:
    table = [item for item in _flowables("| A | B |\n| --- | ---: |\n| 1 | 2 |\n") if isinstance(item, Table)]

    assert len(table) == 1
    # Header plus one body row, two columns -- previously this collapsed into one paragraph.
    assert len(table[0]._cellvalues) == 2
    assert len(table[0]._cellvalues[0]) == 2


def test_long_code_lines_are_wrapped_to_the_card_width() -> None:
    long_line = "def f(" + ", ".join(f"argument_number_{i}" for i in range(20)) + "): pass"
    cards = list(_code_cards(long_line, STYLES, _CONTENT_WIDTH))
    rendered = [
        line
        for card in cards
        for row in card._cellvalues
        for cell in row
        if isinstance(cell, Preformatted)
        for line in cell.lines
    ]

    assert len(rendered) > 1
    # Courier is fixed-pitch, so the character budget is exact.
    assert max(len(line) for line in rendered) <= 100


def test_code_nested_in_a_card_wraps_narrower_than_top_level() -> None:
    """A card nested inside a padded parent must shrink to fit rather than overhang it."""
    code = "x = " + "y" * 400
    widest = lambda width: max(  # noqa: E731
        len(line)
        for card in _code_cards(code, STYLES, width)
        for row in card._cellvalues
        for cell in row
        if isinstance(cell, Preformatted)
        for line in cell.lines
    )

    assert widest(_CONTENT_WIDTH - 28) < widest(_CONTENT_WIDTH)


def test_math_becomes_symbols_and_scripts_not_raw_latex() -> None:
    markup = _math_markup(r"\theta_{t+1} = \theta_t - \eta \nabla J(\theta_t)")

    assert "\\theta" not in markup and "\\nabla" not in markup
    assert "θ" in markup and "∇" in markup
    assert "<sub>t+1</sub>" in markup
    # Greek/math glyphs are absent from the brand font, so they must carry the Symbol font.
    assert 'name="Symbol"' in markup


def test_unsupported_glyphs_fall_back_instead_of_rendering_blank() -> None:
    markup = _inline("ship it 🚀 done ✓")

    assert "🚀" not in markup  # the brand font has no emoji; a blank box reads as a bug
    assert 'name="ZapfDingbats"' in markup  # the check mark still renders


def test_nested_lists_keep_their_depth() -> None:
    paragraphs = [item for item in _flowables("- one\n  - two\n    - three\n") if hasattr(item, "style")]
    indents = [item.style.leftIndent for item in paragraphs]

    assert indents == sorted(indents) and len(set(indents)) == 3


def test_render_survives_hostile_markdown_and_missing_lessons() -> None:
    course = CourseSummary(
        id=uuid4(), title="Edge cases", goal="Survive anything", status="ready",
        active_version=1, updated_at=datetime.now(UTC),
    )
    built = CourseMapConcept(slug="built", title="Built", kind="conceptual", summary_markdown="s", completed=False)
    bare = CourseMapConcept(slug="bare", title="Bare", kind="coding", summary_markdown="s", completed=False)
    course_map = CourseMapResponse(
        course_id=course.id, version=1,
        modules=[CourseMapModule(title="Only module", position=1, concepts=[built, bare])],
    )
    details = {
        "built": ConceptDetailResponse(
            slug="built", title="Built", kind="conceptual", summary_markdown="s", citations=[],
            generation_status="built",
            lesson=LessonPreview(
                status="built", title="Built",
                # Unclosed fence, ragged table, hostile characters, and an oversized example.
                explanation_markdown="```python\nx = 1 < 2 & 3\n\n| a | b |\n| --- | --- |\n| 1 |\n",
                starter_files=[], hints=[],
                worked_examples=[WorkedExamplePreview(title="Big", body_markdown="para\n\n" * 400)],
                quiz_items=[],
            ),
        )
        # "bare" is deliberately absent: a concept whose lesson never built must still render.
    }

    pdf = render_textbook_pdf(course, course_map, details, [])

    assert pdf.startswith(b"%PDF-")

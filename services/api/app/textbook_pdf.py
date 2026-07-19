"""Render a course's learner-visible material as a downloadable PDF textbook."""

from __future__ import annotations

from html import escape
from io import BytesIO
from pathlib import Path
import re
from typing import Iterable

from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, Preformatted, SimpleDocTemplate, Spacer, Table, TableStyle

from app.course_category import accent_colors_for
from app.schemas import CitationExcerptResponse, ConceptDetailResponse, CourseMapResponse, CourseSummary

# The lesson generator emits placement markers like "{{example:1}}"/"{{quiz:2}}" inline in
# explanation prose (apps/web/components/concept-detail.tsx's LESSON_MARKER splits the
# interactive lesson view on these to interleave the actual example/quiz card at that
# position). The PDF still shows every worked example and quiz item -- just gathered into
# their own cards after the prose, rather than re-implementing positional interleaving in a
# static document -- so the markers themselves are just noise here and are stripped.
_LESSON_MARKER = re.compile(r"\{\{\s*(?:example|quiz)\s*:\s*\d+\s*\}\}")

# Same embedded brand font as certificate_pdf.py (see there for provenance) -- registering
# twice under the same name is a no-op in reportlab's global font registry, so it's safe
# for both modules to do this independently rather than one importing internals from the other.
_FONTS_DIR = Path(__file__).parent / "assets" / "fonts"
_REGULAR_FONT = "GoogleSans"
_BOLD_FONT = "GoogleSans-Bold"
pdfmetrics.registerFont(TTFont(_REGULAR_FONT, str(_FONTS_DIR / "GoogleSans-Regular.ttf")))
pdfmetrics.registerFont(TTFont(_BOLD_FONT, str(_FONTS_DIR / "GoogleSans-Bold.ttf")))

def _inline(markdown: str) -> str:
    text = escape(markdown.strip())
    # Not <b>...</b>: reportlab's <b> tag resolves a family's bold variant through
    # pdfmetrics.registerFontFamily/addMapping, which -- empirically, even when registered --
    # doesn't reliably kick in for a non-standard embedded TTF across reportlab versions, and
    # silently renders "bold" text in the regular weight with no error. Naming the actual
    # registered bold font directly sidesteps that resolution path entirely.
    text = re.sub(r"\*\*(.+?)\*\*", rf'<font name="{_BOLD_FONT}">\1</font>', text)
    text = re.sub(r"`(.+?)`", r'<font name="Courier">\1</font>', text)
    # There is no LaTeX renderer in reportlab; show the math expression in italics without its
    # delimiters so exports read cleanly rather than surfacing raw $ / \( markers. Order matters:
    # strip the paired display/inline delimiters before the bare-$ pass.
    text = re.sub(r"\$\$(.+?)\$\$", r"<i>\1</i>", text)
    text = re.sub(r"\\\((.+?)\\\)", r"<i>\1</i>", text)
    text = re.sub(r"\\\[(.+?)\\\]", r"<i>\1</i>", text)
    text = re.sub(r"\$(?![\s\d])([^$]+?)\$(?!\d)", r"<i>\1</i>", text)
    return text


def _math_flowable(tex: str, styles: dict[str, ParagraphStyle]) -> Paragraph:
    return Paragraph(f"<i>{escape(tex.strip())}</i>", styles["body"])


class _RoundedCard(Table):
    """A ReportLab table with the same soft card treatment as the web course view."""

    def __init__(self, *args, background: str, border: str | None = None, radius: int = 14, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._card_background = HexColor(background)
        self._card_border = HexColor(border) if border else None
        self._card_radius = radius

    def draw(self) -> None:  # type: ignore[no-untyped-def]
        self.canv.saveState()
        self.canv.setFillColor(self._card_background)
        if self._card_border:
            self.canv.setStrokeColor(self._card_border)
            self.canv.setLineWidth(0.65)
            self.canv.roundRect(0, 0, self._width, self._height, self._card_radius, fill=1, stroke=1)
        else:
            self.canv.roundRect(0, 0, self._width, self._height, self._card_radius, fill=1, stroke=0)
        self.canv.restoreState()
        super().draw()


def _card(content: list, background: str, padding: int = 12, border: str | None = "#dbe4f0", radius: int = 14) -> Table:
    card = _RoundedCard([[content]], colWidths=[6.45 * inch], background=background, border=border, radius=radius)
    card.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), padding), ("RIGHTPADDING", (0, 0), (-1, -1), padding),
        ("TOPPADDING", (0, 0), (-1, -1), padding), ("BOTTOMPADDING", (0, 0), (-1, -1), padding),
    ]))
    return card


def _markdown_flowables(markdown: str, styles: dict[str, ParagraphStyle], accent: str) -> Iterable:
    lines = markdown.splitlines()
    index = 0
    paragraph: list[str] = []

    def flush_paragraph() -> Iterable[Paragraph | Spacer]:
        if paragraph:
            text = " ".join(part.strip() for part in paragraph)
            paragraph.clear()
            yield Paragraph(_inline(text), styles["body"])

    while index < len(lines):
        raw = lines[index]
        text = raw.strip()
        if text.startswith("```"):
            yield from flush_paragraph()
            index += 1
            code: list[str] = []
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code.append(lines[index])
                index += 1
            yield _card([Preformatted("\n".join(code), styles["code"])], "#0f172a", 12, border=None, radius=12)
        elif text.startswith("$$") or text.startswith("\\["):
            yield from flush_paragraph()
            close = "$$" if text.startswith("$$") else "\\]"
            first = text[2:]
            if close in first:
                yield _math_flowable(first.split(close, 1)[0], styles)
            else:
                math: list[str] = [first]
                index += 1
                while index < len(lines) and close not in lines[index]:
                    math.append(lines[index])
                    index += 1
                if index < len(lines):
                    math.append(lines[index].split(close, 1)[0])
                yield _math_flowable("\n".join(math), styles)
                index += 1
                continue
        elif not text:
            yield from flush_paragraph()
            yield Spacer(1, 6)
        elif text.startswith("> "):
            yield from flush_paragraph()
            quote: list[str] = []
            while index < len(lines) and lines[index].strip().startswith("> "):
                quote.append(lines[index].strip()[2:])
                index += 1
            yield _card([Paragraph(_inline(" ".join(quote)), styles["callout"])], "#ffffff", 13, border=accent, radius=12)
            yield Spacer(1, 7)
            continue
        elif text.startswith("### "):
            yield from flush_paragraph()
            yield Paragraph(_inline(text[4:]), styles["h3"])
        elif text.startswith("## "):
            yield from flush_paragraph()
            yield Paragraph(_inline(text[3:]), styles["h2"])
        elif text.startswith("# "):
            yield from flush_paragraph()
            yield Paragraph(_inline(text[2:]), styles["h1"])
        elif re.match(r"^(?:[-*+] |\d+\. )", text):
            yield from flush_paragraph()
            marker, item = re.match(r"^([-*+]|\d+\.)\s+(.*)$", text).groups()  # type: ignore[union-attr]
            yield Paragraph(f"{marker} {_inline(item)}", styles["list"])
        elif text in {"---", "***", "___"}:
            yield from flush_paragraph()
            yield Spacer(1, 4)
        else:
            paragraph.append(raw)
        index += 1
    yield from flush_paragraph()


def _footer(canvas, document) -> None:  # type: ignore[no-untyped-def]
    canvas.saveState()
    canvas.setFont(_REGULAR_FONT, 8)
    canvas.setFillColor(HexColor("#64748b"))
    canvas.drawString(document.leftMargin, 0.45 * inch, "Canopy coursebook export")
    canvas.drawRightString(LETTER[0] - document.rightMargin, 0.45 * inch, str(document.page))
    canvas.restoreState()


def render_textbook_pdf(
    course: CourseSummary,
    course_map: CourseMapResponse,
    details: dict[str, ConceptDetailResponse],
    references: list[CitationExcerptResponse],
) -> bytes:
    """Produce learner-visible prose only; never include hidden tests or solutions."""
    accent, tint = accent_colors_for(course.title, course.goal)
    output = BytesIO()
    document = SimpleDocTemplate(output, pagesize=LETTER, leftMargin=0.78 * inch, rightMargin=0.78 * inch, topMargin=0.78 * inch, bottomMargin=0.7 * inch, title=course.title, author="Canopy")
    styles = getSampleStyleSheet()
    title = ParagraphStyle("TextbookTitle", parent=styles["Title"], fontName=_BOLD_FONT, fontSize=27, leading=32, alignment=TA_CENTER, textColor=white, spaceAfter=10)
    subtitle = ParagraphStyle("TextbookSubtitle", parent=styles["BodyText"], fontName=_REGULAR_FONT, fontSize=11, leading=16, alignment=TA_CENTER, textColor=HexColor("#dbeafe"))
    module = ParagraphStyle("Module", parent=styles["Heading1"], fontName=_BOLD_FONT, fontSize=19, leading=24, textColor=HexColor(accent), spaceBefore=8, spaceAfter=14)
    section = ParagraphStyle("Section", parent=styles["Heading2"], fontName=_BOLD_FONT, fontSize=15, leading=19, textColor=HexColor("#0f172a"), spaceBefore=13, spaceAfter=9)
    body = ParagraphStyle("TextbookBody", parent=styles["BodyText"], fontName=_REGULAR_FONT, fontSize=10.5, leading=15, textColor=HexColor("#24324a"), spaceAfter=6)
    small = ParagraphStyle("TextbookSmall", parent=body, fontSize=9, leading=12, textColor=HexColor("#64748b"))
    markdown_styles = {"body": body, "list": ParagraphStyle("List", parent=body, leftIndent=13, firstLineIndent=-10), "h1": ParagraphStyle("MarkdownH1", parent=section, fontSize=16), "h2": ParagraphStyle("MarkdownH2", parent=section, fontSize=14), "h3": ParagraphStyle("MarkdownH3", parent=body, fontName=_BOLD_FONT, spaceBefore=8), "callout": ParagraphStyle("Callout", parent=body, textColor=HexColor(accent)), "code": ParagraphStyle("Code", fontName="Courier", fontSize=8.5, leading=11, textColor=HexColor("#e2e8f0"))}
    cover_label = ParagraphStyle("CoverLabel", parent=small, alignment=TA_CENTER, textColor=HexColor("#e0e7ff"))
    cover = _card(
        [Paragraph(_inline(course.title), title), Paragraph(_inline(course.goal), subtitle), Spacer(1, 14), Paragraph("CANOPY COURSEBOOK", cover_label)],
        accent,
        30,
        border=None,
        radius=24,
    )
    story = [Spacer(1, 0.45 * inch), cover, Spacer(1, 28), Paragraph("Contents", module)]
    reference_numbers = {str(reference.id): index for index, reference in enumerate(references, start=1)}
    for item in course_map.modules:
        story.append(Paragraph(f"{item.position}. {_inline(item.title)}", body))
        for concept in item.concepts:
            story.append(Paragraph(f"&nbsp;&nbsp;&nbsp;{_inline(concept.title)}", small))
    for item in course_map.modules:
        module_label = ParagraphStyle("ModuleLabel", parent=small, fontName=_BOLD_FONT, textColor=HexColor(accent), alignment=TA_CENTER, letterSpacing=0.8)
        module_title = ParagraphStyle("ModuleCardTitle", parent=module, alignment=TA_CENTER, spaceAfter=0)
        story.extend([
            PageBreak(),
            _card(
                [Paragraph(f"MODULE {item.position}", module_label), Spacer(1, 6), Paragraph(_inline(item.title), module_title)],
                tint,
                22,
                border=None,
                radius=18,
            ),
            Spacer(1, 12),
        ])
        for concept in item.concepts:
            detail = details[concept.slug]
            lesson_header = [Paragraph(_inline(concept.title), section), Paragraph(_inline(detail.summary_markdown or concept.summary_markdown), small)]
            story.append(KeepTogether([_card(lesson_header, "#ffffff", 14, border="#e2e8f0", radius=14), Spacer(1, 9)]))
            if detail.lesson:
                explanation = _LESSON_MARKER.sub("", detail.lesson.explanation_markdown)
                story.extend(_markdown_flowables(explanation, markdown_styles, accent))
                for example in detail.lesson.worked_examples:
                    story.append(Spacer(1, 6))
                    story.append(_card([Paragraph(_inline(example.title), ParagraphStyle("Example", parent=body, fontName=_BOLD_FONT, textColor=HexColor(accent))), Spacer(1, 5), *list(_markdown_flowables(example.body_markdown, markdown_styles, accent))], tint, 14, border=None, radius=14))
                if detail.lesson.quiz_items:
                    story.append(Spacer(1, 8))
                    quiz_content = [Paragraph("Check your understanding", ParagraphStyle("Check", parent=body, fontName=_BOLD_FONT, textColor=HexColor("#92400e"), spaceAfter=6))]
                    for index, quiz in enumerate(detail.lesson.quiz_items, start=1):
                        quiz_content.append(Paragraph(f"{index}. {_inline(quiz.prompt_markdown)}", body))
                        for option in quiz.options or []:
                            quiz_content.append(Paragraph(f"&nbsp;&nbsp;&nbsp;- {_inline(option.text)}", small))
                    story.append(_card(quiz_content, "#fffbeb", 14, border="#fde68a", radius=14))
            cited_numbers = [reference_numbers[citation] for citation in detail.citations if citation in reference_numbers]
            if cited_numbers:
                links = ", ".join(f'<a href="#ref-{number}" color="#4338ca">[{number}]</a>' for number in cited_numbers)
                story.append(Spacer(1, 5))
                story.append(Paragraph(f"Sources: {links}", small))
            story.append(Spacer(1, 10))
    if references:
        story.extend([PageBreak(), Paragraph("References", module)])
        for index, reference in enumerate(references, start=1):
            location = ", ".join(part for part in [reference.filename, reference.section, f"p. {reference.page_number}" if reference.page_number else None] if part)
            reference_title = Paragraph(f'<a name="ref-{index}"/>[{index}] {_inline(location)}', ParagraphStyle("ReferenceTitle", parent=body, fontName=_BOLD_FONT, spaceBefore=8))
            excerpt = Paragraph(_inline(reference.content), small)
            story.append(_card([reference_title, Spacer(1, 4), excerpt], "#f8fafc", 12, border="#e2e8f0", radius=12))
            story.append(Spacer(1, 7))
    document.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return output.getvalue()

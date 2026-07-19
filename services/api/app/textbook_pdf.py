"""Render a course's learner-visible material as a downloadable PDF textbook."""

from __future__ import annotations

from html import escape
from io import BytesIO
import re
from typing import Iterable

from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, Preformatted, SimpleDocTemplate, Spacer, Table, TableStyle

from app.schemas import CitationExcerptResponse, ConceptDetailResponse, CourseMapResponse, CourseSummary


def _inline(markdown: str) -> str:
    text = escape(markdown.strip())
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
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


def _card(content: list, background: str, padding: int = 12) -> Table:
    card = Table([[content]], colWidths=[6.45 * inch])
    card.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), HexColor(background)),
        ("BOX", (0, 0), (-1, -1), 0.5, HexColor("#dbe4f0")),
        ("LEFTPADDING", (0, 0), (-1, -1), padding), ("RIGHTPADDING", (0, 0), (-1, -1), padding),
        ("TOPPADDING", (0, 0), (-1, -1), padding), ("BOTTOMPADDING", (0, 0), (-1, -1), padding),
    ]))
    return card


def _markdown_flowables(markdown: str, styles: dict[str, ParagraphStyle]) -> Iterable:
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
            yield _card([Preformatted("\n".join(code), styles["code"])], "#0f172a", 11)
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
            yield _card([Paragraph(_inline(" ".join(quote)), styles["callout"])], "#eef2ff")
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
    canvas.setFont("Helvetica", 8)
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
    output = BytesIO()
    document = SimpleDocTemplate(output, pagesize=LETTER, leftMargin=0.78 * inch, rightMargin=0.78 * inch, topMargin=0.78 * inch, bottomMargin=0.7 * inch, title=course.title, author="Canopy")
    styles = getSampleStyleSheet()
    title = ParagraphStyle("TextbookTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=27, leading=32, alignment=TA_CENTER, textColor=white, spaceAfter=10)
    subtitle = ParagraphStyle("TextbookSubtitle", parent=styles["BodyText"], fontSize=11, leading=16, alignment=TA_CENTER, textColor=HexColor("#dbeafe"))
    module = ParagraphStyle("Module", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=19, leading=24, textColor=HexColor("#1e3a8a"), spaceBefore=8, spaceAfter=14)
    section = ParagraphStyle("Section", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=15, leading=19, textColor=HexColor("#0f172a"), spaceBefore=13, spaceAfter=9)
    body = ParagraphStyle("TextbookBody", parent=styles["BodyText"], fontSize=10.5, leading=15, textColor=HexColor("#24324a"), spaceAfter=6)
    small = ParagraphStyle("TextbookSmall", parent=body, fontSize=9, leading=12, textColor=HexColor("#64748b"))
    markdown_styles = {"body": body, "list": ParagraphStyle("List", parent=body, leftIndent=13, firstLineIndent=-10), "h1": ParagraphStyle("MarkdownH1", parent=section, fontSize=16), "h2": ParagraphStyle("MarkdownH2", parent=section, fontSize=14), "h3": ParagraphStyle("MarkdownH3", parent=body, fontName="Helvetica-Bold", spaceBefore=8), "callout": ParagraphStyle("Callout", parent=body, textColor=HexColor("#3730a3")), "code": ParagraphStyle("Code", fontName="Courier", fontSize=8.5, leading=11, textColor=HexColor("#e2e8f0"))}
    cover = Table([[[Paragraph(_inline(course.title), title), Paragraph(_inline(course.goal), subtitle), Spacer(1, 5), Paragraph("Generated coursebook", ParagraphStyle("CoverLabel", parent=small, alignment=TA_CENTER, textColor=HexColor("#c7d2fe")))]]], colWidths=[6.45 * inch])
    cover.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), HexColor("#312e81")), ("LEFTPADDING", (0, 0), (-1, -1), 28), ("RIGHTPADDING", (0, 0), (-1, -1), 28), ("TOPPADDING", (0, 0), (-1, -1), 40), ("BOTTOMPADDING", (0, 0), (-1, -1), 38)]))
    story = [Spacer(1, 0.45 * inch), cover, Spacer(1, 28), Paragraph("Contents", module)]
    reference_numbers = {str(reference.id): index for index, reference in enumerate(references, start=1)}
    for item in course_map.modules:
        story.append(Paragraph(f"{item.position}. {_inline(item.title)}", body))
        for concept in item.concepts:
            story.append(Paragraph(f"&nbsp;&nbsp;&nbsp;{_inline(concept.title)}", small))
    for item in course_map.modules:
        story.extend([PageBreak(), Paragraph(f"{item.position}. {_inline(item.title)}", module)])
        for concept in item.concepts:
            detail = details[concept.slug]
            lesson_header = [Paragraph(_inline(concept.title), section), Paragraph(_inline(detail.summary_markdown or concept.summary_markdown), small)]
            story.append(KeepTogether([_card(lesson_header, "#f8fafc"), Spacer(1, 9)]))
            if detail.lesson:
                story.extend(_markdown_flowables(detail.lesson.explanation_markdown, markdown_styles))
                for example in detail.lesson.worked_examples:
                    story.append(Spacer(1, 6))
                    story.append(_card([Paragraph(_inline(example.title), ParagraphStyle("Example", parent=body, fontName="Helvetica-Bold", textColor=HexColor("#0f766e"))), Spacer(1, 5), *list(_markdown_flowables(example.body_markdown, markdown_styles))], "#f0fdfa"))
                if detail.lesson.quiz_items:
                    story.append(Spacer(1, 8))
                    quiz_content = [Paragraph("Check your understanding", ParagraphStyle("Check", parent=body, fontName="Helvetica-Bold", textColor=HexColor("#92400e"), spaceAfter=6))]
                    for index, quiz in enumerate(detail.lesson.quiz_items, start=1):
                        quiz_content.append(Paragraph(f"{index}. {_inline(quiz.prompt_markdown)}", body))
                        for option in quiz.options or []:
                            quiz_content.append(Paragraph(f"&nbsp;&nbsp;&nbsp;- {_inline(option.text)}", small))
                    story.append(_card(quiz_content, "#fffbeb"))
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
            reference_title = Paragraph(f'<a name="ref-{index}"/>[{index}] {_inline(location)}', ParagraphStyle("ReferenceTitle", parent=body, fontName="Helvetica-Bold", spaceBefore=8))
            excerpt = Paragraph(_inline(reference.content), small)
            story.append(_card([reference_title, Spacer(1, 4), excerpt], "#f8fafc", 10))
            story.append(Spacer(1, 7))
    document.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return output.getvalue()

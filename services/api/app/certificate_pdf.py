"""Render a course completion certificate as a downloadable PDF."""

from __future__ import annotations

from html import escape
from io import BytesIO
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import LETTER, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Flowable, Paragraph, SimpleDocTemplate, Spacer

from app.schemas import CertificateResponse

_PAGE_SIZE = landscape(LETTER)

# The app's own self-hosted brand font (apps/web/app/fonts/GoogleSansFlex.woff2), pre-flattened
# from its variable-font source into static Regular/Bold instances reportlab can embed --
# so the PDF actually looks like the rest of the product instead of generic Helvetica.
_FONTS_DIR = Path(__file__).parent / "assets" / "fonts"
_REGULAR_FONT = "GoogleSans"
_BOLD_FONT = "GoogleSans-Bold"
pdfmetrics.registerFont(TTFont(_REGULAR_FONT, str(_FONTS_DIR / "GoogleSans-Regular.ttf")))
pdfmetrics.registerFont(TTFont(_BOLD_FONT, str(_FONTS_DIR / "GoogleSans-Bold.ttf")))

_INK = "#0f172a"
_MUTED = "#64748b"


def _border(accent: str):  # type: ignore[no-untyped-def]
    def draw(canvas, document) -> None:
        canvas.saveState()
        width, height = _PAGE_SIZE
        canvas.setStrokeColor(HexColor(accent))
        canvas.setLineWidth(3)
        canvas.rect(0.35 * inch, 0.35 * inch, width - 0.7 * inch, height - 0.7 * inch)
        canvas.setStrokeColor(HexColor(accent))
        canvas.setLineWidth(0.5)
        canvas.rect(0.45 * inch, 0.45 * inch, width - 0.9 * inch, height - 0.9 * inch)
        canvas.restoreState()

    return draw


class _SkillChips(Flowable):
    """A centered, wrapping grid of pill-shaped skill tags -- Platypus has no native
    chip/pill flowable, so this draws them directly rather than approximating with a
    Table (which can't do rounded corners or per-row centered auto-width)."""

    def __init__(self, skills: list[str], *, max_width: float, accent: str, tint: str) -> None:
        super().__init__()
        self.skills = skills
        self.max_width = max_width
        self.accent = accent
        self.tint = tint
        self.chip_height = 22
        self.row_gap = 8
        self.font_size = 9.5

    def _rows(self) -> list[list[tuple[str, float]]]:
        gap = 8
        padding_x = 11
        rows: list[list[tuple[str, float]]] = []
        current: list[tuple[str, float]] = []
        current_width = 0.0
        for skill in self.skills:
            width = pdfmetrics.stringWidth(skill, _BOLD_FONT, self.font_size) + 2 * padding_x
            needed = width if not current else current_width + gap + width
            if current and needed > self.max_width:
                rows.append(current)
                current, current_width = [], 0.0
                needed = width
            current.append((skill, width))
            current_width = needed
        if current:
            rows.append(current)
        return rows

    def wrap(self, available_width: float, available_height: float) -> tuple[float, float]:
        rows = self._rows()
        if not rows:
            return self.max_width, 0
        height = len(rows) * self.chip_height + (len(rows) - 1) * self.row_gap
        return self.max_width, height

    def draw(self) -> None:
        rows = self._rows()
        if not rows:
            return
        canvas = self.canv
        canvas.setFont(_BOLD_FONT, self.font_size)
        gap = 8
        total_height = len(rows) * self.chip_height + (len(rows) - 1) * self.row_gap
        y = total_height - self.chip_height
        for row in rows:
            row_width = sum(width for _, width in row) + gap * (len(row) - 1)
            x = max(0, (self.max_width - row_width) / 2)
            for skill, width in row:
                canvas.setFillColor(HexColor(self.tint))
                canvas.roundRect(x, y, width, self.chip_height, self.chip_height / 2, fill=1, stroke=0)
                canvas.setFillColor(HexColor(self.accent))
                canvas.drawCentredString(x + width / 2, y + 6.5, skill)
                x += width + gap
            y -= self.chip_height + self.row_gap


def _format_hours(hours: float) -> str:
    text = f"{hours:g}"
    return f"~{text} hour{'s' if hours != 1 else ''}"


def render_certificate_pdf(certificate: CertificateResponse) -> bytes:
    accent = certificate.accent_color
    tint = certificate.accent_tint
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=_PAGE_SIZE,
        leftMargin=1 * inch,
        rightMargin=1 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.75 * inch,
        title=f"{certificate.course_title} -- Certificate of Completion",
        author="Canopy",
    )
    styles = getSampleStyleSheet()
    content_width = _PAGE_SIZE[0] - document.leftMargin - document.rightMargin

    # Small and de-emphasized -- the issuer's mark, not the headline; the learner's name
    # and course are what a certificate should foreground.
    brand = ParagraphStyle("Brand", parent=styles["Normal"], fontName=_BOLD_FONT, fontSize=12, leading=14, alignment=TA_CENTER, textColor=HexColor(_INK), spaceAfter=16)
    eyebrow = ParagraphStyle("Eyebrow", parent=styles["Normal"], fontName=_REGULAR_FONT, fontSize=11.5, leading=15, alignment=TA_CENTER, textColor=HexColor(accent), spaceAfter=16)
    body = ParagraphStyle("Body", parent=styles["BodyText"], fontName=_REGULAR_FONT, fontSize=12.5, leading=18, alignment=TA_CENTER, textColor=HexColor(_MUTED), spaceAfter=6)
    name = ParagraphStyle("Name", parent=body, fontSize=19, fontName=_BOLD_FONT, textColor=HexColor(_INK), spaceAfter=8)
    course_title_style = ParagraphStyle("CourseTitle", parent=styles["Title"], fontName=_BOLD_FONT, fontSize=22, leading=27, alignment=TA_CENTER, textColor=HexColor(accent), spaceBefore=4, spaceAfter=16)
    skills_label = ParagraphStyle("SkillsLabel", parent=styles["Normal"], fontName=_REGULAR_FONT, fontSize=8.5, leading=12, alignment=TA_CENTER, textColor=HexColor(_MUTED), spaceAfter=8)
    stats = ParagraphStyle("Stats", parent=styles["Normal"], fontName=_BOLD_FONT, fontSize=10.5, leading=14, alignment=TA_CENTER, textColor=HexColor(_INK))
    link_style = ParagraphStyle("Link", parent=styles["Normal"], fontName=_REGULAR_FONT, fontSize=9, leading=13, alignment=TA_CENTER, textColor=HexColor(accent), spaceBefore=12)

    story = [
        Spacer(1, 0.1 * inch),
        Paragraph("CANOPY", brand),
        Paragraph("CERTIFICATE OF COMPLETION", eyebrow),
        Paragraph("This certifies that", body),
        Paragraph(escape(certificate.learner_name), name),
        Paragraph("has successfully completed", body),
        Paragraph(escape(certificate.course_title), course_title_style),
    ]
    if certificate.skills:
        story.append(Paragraph("SKILLS COVERED", skills_label))
        story.append(_SkillChips([skill.upper() for skill in certificate.skills], max_width=content_width, accent=accent, tint=tint))
        story.append(Spacer(1, 16))
    story.append(Paragraph(f"{_format_hours(certificate.estimated_hours)} &nbsp;&middot;&nbsp; Issued {certificate.issued_at.strftime('%B %d, %Y')}", stats))
    # Verification is just the link -- it's both the proof and the id (the certificate
    # row's own url path), so a separate "Certificate ID" line next to it was redundant.
    story.append(Paragraph(f'Verify at <link href="{escape(certificate.verify_url)}">{escape(certificate.verify_url)}</link>', link_style))

    border = _border(accent)
    document.build(story, onFirstPage=border, onLaterPages=border)
    return output.getvalue()

"""Render a course completion certificate as a downloadable PDF."""

from __future__ import annotations

from html import escape
from io import BytesIO

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import LETTER, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from app.schemas import CertificateResponse

_PAGE_SIZE = landscape(LETTER)


def _border(canvas, document) -> None:  # type: ignore[no-untyped-def]
    canvas.saveState()
    width, height = _PAGE_SIZE
    canvas.setStrokeColor(HexColor("#312e81"))
    canvas.setLineWidth(3)
    canvas.rect(0.35 * inch, 0.35 * inch, width - 0.7 * inch, height - 0.7 * inch)
    canvas.setStrokeColor(HexColor("#a5b4fc"))
    canvas.setLineWidth(0.75)
    canvas.rect(0.45 * inch, 0.45 * inch, width - 0.9 * inch, height - 0.9 * inch)
    canvas.restoreState()


def render_certificate_pdf(certificate: CertificateResponse) -> bytes:
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=_PAGE_SIZE,
        leftMargin=1 * inch,
        rightMargin=1 * inch,
        topMargin=0.9 * inch,
        bottomMargin=0.9 * inch,
        title=f"{certificate.course_title} -- Certificate of Completion",
        author="Canopy",
    )
    styles = getSampleStyleSheet()
    eyebrow = ParagraphStyle("Eyebrow", parent=styles["Normal"], fontName="Helvetica", fontSize=12, leading=16, alignment=TA_CENTER, textColor=HexColor("#6366f1"), spaceAfter=6)
    heading = ParagraphStyle("Heading", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=30, leading=36, alignment=TA_CENTER, textColor=HexColor("#0f172a"), spaceAfter=18)
    body = ParagraphStyle("Body", parent=styles["BodyText"], fontSize=13, leading=19, alignment=TA_CENTER, textColor=HexColor("#334155"), spaceAfter=8)
    name = ParagraphStyle("Name", parent=body, fontSize=18, fontName="Helvetica-Bold", textColor=HexColor("#0f172a"), spaceAfter=10)
    course_title_style = ParagraphStyle("CourseTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=22, leading=28, alignment=TA_CENTER, textColor=HexColor("#312e81"), spaceBefore=6, spaceAfter=18)
    meta = ParagraphStyle("Meta", parent=styles["Normal"], fontSize=9.5, leading=13, alignment=TA_CENTER, textColor=HexColor("#94a3b8"))

    story = [
        Spacer(1, 0.3 * inch),
        Paragraph("CERTIFICATE OF COMPLETION", eyebrow),
        Paragraph("Canopy", heading),
        Spacer(1, 6),
        Paragraph("This certifies that", body),
        Paragraph(escape(certificate.learner_email), name),
        Paragraph("has successfully completed", body),
        Paragraph(escape(certificate.course_title), course_title_style),
        Spacer(1, 20),
        Paragraph(f"Issued {certificate.issued_at.strftime('%B %d, %Y')}", meta),
        Paragraph(f"Certificate ID {certificate.certificate_id}", meta),
    ]
    document.build(story, onFirstPage=_border, onLaterPages=_border)
    return output.getvalue()

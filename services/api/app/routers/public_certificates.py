"""Public, no-auth certificate verification -- the durable link a certificate's owner can
share anywhere (a resume, LinkedIn, an email) and have it resolve for anyone, the same
trust model course sharing already uses for its course-id links. Deliberately outside the
/courses prefix and never behind CurrentUser: the certificate row's own id is the only
credential a viewer needs, and it's unguessable (a random uuid), not derived from anything
about the viewer."""

import re
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from app.certificate_pdf import render_certificate_pdf
from app.repository import CourseRepository, get_repository
from app.schemas import CertificateResponse

router = APIRouter(prefix="/certificates", tags=["certificates"])
Repository = Annotated[CourseRepository, Depends(get_repository)]


@router.get("/{certificate_id}", response_model=CertificateResponse)
def get_public_certificate(certificate_id: UUID, repository: Repository) -> CertificateResponse:
    return repository.public_certificate(certificate_id)


@router.get("/{certificate_id}/export", response_class=Response)
def export_public_certificate(certificate_id: UUID, repository: Repository) -> Response:
    certificate = repository.public_certificate(certificate_id)
    filename = re.sub(r"[^a-zA-Z0-9._-]+", "-", certificate.course_title).strip("-.") or "course"
    return Response(
        content=render_certificate_pdf(certificate),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}-certificate.pdf"'},
    )

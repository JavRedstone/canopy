from dataclasses import dataclass
from io import BytesIO
import re

from pypdf import PdfReader


@dataclass(frozen=True)
class ParsedChunk:
    content: str
    page_number: int | None
    section: str | None
    char_start: int
    char_end: int


def parse_source_document(
    raw_content: bytes,
    mime_type: str,
    chunk_characters: int,
    chunk_overlap_characters: int,
) -> list[ParsedChunk]:
    if mime_type == "application/pdf":
        return _parse_pdf(raw_content, chunk_characters, chunk_overlap_characters)
    if mime_type in {"text/markdown", "text/plain"}:
        return _parse_text(raw_content, mime_type, chunk_characters, chunk_overlap_characters)
    raise ValueError(f"Unsupported source MIME type: {mime_type}")


def _parse_pdf(raw_content: bytes, chunk_characters: int, chunk_overlap_characters: int) -> list[ParsedChunk]:
    reader = PdfReader(BytesIO(raw_content))
    chunks: list[ParsedChunk] = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        chunks.extend(
            _chunk_text(
                _normalize(text),
                page_number=page_number,
                section=f"Page {page_number}",
                chunk_characters=chunk_characters,
                chunk_overlap_characters=chunk_overlap_characters,
            )
        )
    if not chunks:
        raise ValueError("No extractable text was found in the PDF.")
    return chunks


def _parse_text(
    raw_content: bytes,
    mime_type: str,
    chunk_characters: int,
    chunk_overlap_characters: int,
) -> list[ParsedChunk]:
    text = _normalize(raw_content.decode("utf-8-sig", errors="replace"))
    if not text.strip():
        raise ValueError("The source document is empty.")
    if mime_type == "text/markdown":
        return _chunk_markdown(text, chunk_characters, chunk_overlap_characters)
    return _chunk_text(
        text,
        page_number=None,
        section="Document",
        chunk_characters=chunk_characters,
        chunk_overlap_characters=chunk_overlap_characters,
    )


def _chunk_markdown(text: str, chunk_characters: int, chunk_overlap_characters: int) -> list[ParsedChunk]:
    headings = list(re.finditer(r"(?m)^#{1,6}\s+(.+?)\s*$", text))
    if not headings:
        return _chunk_text(
            text,
            page_number=None,
            section="Document",
            chunk_characters=chunk_characters,
            chunk_overlap_characters=chunk_overlap_characters,
        )

    chunks: list[ParsedChunk] = []
    if headings[0].start() > 0:
        chunks.extend(
            _chunk_text(
                text[: headings[0].start()],
                page_number=None,
                section="Introduction",
                chunk_characters=chunk_characters,
                chunk_overlap_characters=chunk_overlap_characters,
                offset=0,
            )
        )
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        chunks.extend(
            _chunk_text(
                text[heading.start() : end],
                page_number=None,
                section=heading.group(1).strip(),
                chunk_characters=chunk_characters,
                chunk_overlap_characters=chunk_overlap_characters,
                offset=heading.start(),
            )
        )
    return chunks


def _chunk_text(
    text: str,
    *,
    page_number: int | None,
    section: str,
    chunk_characters: int,
    chunk_overlap_characters: int,
    offset: int = 0,
) -> list[ParsedChunk]:
    if chunk_characters <= 0 or chunk_overlap_characters < 0 or chunk_overlap_characters >= chunk_characters:
        raise ValueError("Chunk size must be positive and larger than its overlap.")
    chunks: list[ParsedChunk] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_characters, len(text))
        if end < len(text):
            break_at = max(text.rfind("\n", start + chunk_characters // 2, end), text.rfind(" ", start + chunk_characters // 2, end))
            if break_at > start:
                end = break_at
        content = text[start:end].strip()
        if content:
            chunks.append(
                ParsedChunk(
                    content=content,
                    page_number=page_number,
                    section=section,
                    char_start=offset + start,
                    char_end=offset + end,
                )
            )
        if end == len(text):
            break
        start = max(end - chunk_overlap_characters, start + 1)
    return chunks


def _normalize(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()

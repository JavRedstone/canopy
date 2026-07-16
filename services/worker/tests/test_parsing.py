from worker.parsing import parse_source_document


def test_markdown_parser_keeps_heading_and_offsets() -> None:
    chunks = parse_source_document(
        b"# Authentication\n\nJWTs carry claims.\n\n# Expiration\n\nReject expired tokens.",
        "text/markdown",
        chunk_characters=80,
        chunk_overlap_characters=10,
    )

    assert [chunk.section for chunk in chunks] == ["Authentication", "Expiration"]
    assert chunks[0].char_start == 0
    assert "JWTs carry claims" in chunks[0].content


def test_plain_text_parser_rejects_empty_content() -> None:
    try:
        parse_source_document(b"\n\n", "text/plain", chunk_characters=80, chunk_overlap_characters=10)
    except ValueError as error:
        assert "empty" in str(error).lower()
    else:
        raise AssertionError("Expected empty source content to be rejected.")

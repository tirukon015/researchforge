"""Builders for real PDF bytes used by the tests.

WHY THIS EXISTS
---------------
The extraction tests need genuine PDF files. Three options were considered:

1. Commit binary sample PDFs - bloats the repo and, for real papers, raises
   licensing questions the project does not need.
2. Add a PDF-authoring dependency (e.g. reportlab) - a production dependency
   pulled in purely for tests.
3. Emit minimal but valid PDF bytes here - no dependency, no binaries.

Option 3 is used. These are **synthetic test fixtures exercising the extraction
machinery**, not research data. Root CLAUDE.md section 5 forbids fabricated
research content and fabricated results; it does not forbid test inputs, and
nothing here is ever presented as a real paper or a real finding. Real
open-licence papers belong in `data/samples/` per `data/samples/SOURCES.md`.
"""


def _escape(text: str) -> str:
    """Escape the three characters that are special inside a PDF string."""
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def build_pdf(pages: list[str]) -> bytes:
    """Build a valid single- or multi-page PDF containing `pages` of text.

    Objects are written sequentially and a real xref table is emitted, so the
    result parses without relying on a reader's error recovery.
    """
    if not pages:
        raise ValueError("a PDF needs at least one page")

    font_obj = 3 + 2 * len(pages)
    objects: list[bytes] = []

    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")

    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(len(pages)))
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode("latin-1"))

    for i, text in enumerate(pages):
        page_obj = 3 + 2 * i
        content_obj = page_obj + 1
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                f"/Contents {content_obj} 0 R "
                f"/Resources << /Font << /F1 {font_obj} 0 R >> >> >>"
            ).encode("latin-1")
        )
        # One Tj per line, moved down the page with TL/T*, so extracted text
        # keeps its line breaks.
        lines = text.split("\n") or [""]
        drawn = "\n".join(f"({_escape(line)}) Tj T*" for line in lines)
        stream = f"BT /F1 12 Tf 14 TL 72 720 Td\n{drawn}\nET".encode("latin-1", "replace")
        objects.append(
            b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"
        )

    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"

    xref_at = len(out)
    count = len(objects) + 1
    out += f"xref\n0 {count}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        out += f"{offset:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {count} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n".encode()
    return bytes(out)


def build_text_pdf(text: str) -> bytes:
    """A one-page PDF containing `text`."""
    return build_pdf([text])


def build_empty_text_pdf() -> bytes:
    """A structurally valid PDF whose pages carry no text.

    This is what a scanned, image-only paper looks like to a text extractor.
    """
    return build_pdf([""])


def build_long_pdf(pages: int, chars_per_page: int) -> bytes:
    """A multi-page PDF long enough to exercise the chunking path."""
    body = []
    for page in range(pages):
        # Sentence-shaped filler so the chunker has real boundaries to find.
        sentence = f"Section {page} discusses the measured outcome in detail. "
        repeats = max(1, chars_per_page // len(sentence))
        body.append("\n".join([sentence * 3] * max(1, repeats // 3)))
    return build_pdf(body)

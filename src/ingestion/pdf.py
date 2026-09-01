"""PDF text extraction and cleaning.

WHY pypdf
---------
PROJECT_PLAN.md section F decision 3 leaves the PDF library formally UNDECIDED,
to be settled by benchmarking on real papers. `pypdf` is chosen as the working
default for three reasons that hold regardless of that benchmark:

* **Pure Python, no system dependencies.** Root CLAUDE.md section 7 requires the
  project to run identically on macOS, Windows, and Linux. `pymupdf` is faster
  and more accurate but ships native binaries and is **AGPL**, which is
  incompatible with this repository's MIT licence and its public-portfolio
  purpose. That rules it out on licensing, not just convenience.
* **Permissive licence** (BSD-3), so it can ship in an MIT repo.
* **Adequate for the job.** We need reading-order text, not layout
  reconstruction or table parsing.

`pdfplumber` remains the upgrade path if benchmarking shows pypdf's extraction
is too lossy on real papers. The rest of this module is library-agnostic: only
`_read_pages` touches pypdf, so swapping is a one-function change.
"""

import io
import logging
import re
from dataclasses import dataclass

from pypdf import PdfReader
from pypdf.errors import PdfReadError

logger = logging.getLogger(__name__)

# Every PDF begins with this signature. Checking the bytes rather than trusting
# the browser-supplied content-type means a renamed .exe cannot get through.
PDF_MAGIC = b"%PDF-"

# Below this, extraction effectively failed: the file is almost certainly a
# scanned image with no text layer, which needs OCR we do not have.
MIN_USABLE_CHARS = 200


class PdfExtractionError(ValueError):
    """Raised when a PDF cannot be read or contains no usable text.

    Subclasses ValueError because every cause is a bad input, not a bug - the
    API layer turns it into a 4xx, never a 500.
    """


@dataclass(frozen=True)
class ExtractedDocument:
    """The result of reading a PDF."""

    text: str
    page_count: int
    pages_with_text: int

    @property
    def character_count(self) -> int:
        return len(self.text)


def looks_like_pdf(data: bytes) -> bool:
    """Whether the bytes actually start with a PDF signature."""
    return data.startswith(PDF_MAGIC)


def clean_text(raw: str) -> str:
    """Tidy extracted text without changing its meaning.

    Extraction artefacts waste context and make the model's job harder. Each
    rule below is deliberately conservative - nothing here removes content,
    because a dropped sentence could be the one finding that mattered.
    """
    text = raw.replace("\x00", "")

    # PDFs encode ligatures as single glyphs; models read the split form fine,
    # but normalising keeps quoted evidence matching the source wording.
    for ligature, plain in (("ﬁ", "fi"), ("ﬂ", "fl"), ("ﬀ", "ff")):
        text = text.replace(ligature, plain)

    # Words split across a line break by hyphenation: "hyphen-\nation".
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)

    # Collapse runs of spaces/tabs, but never across newlines - paragraph
    # structure is a real signal about where sections begin and end.
    text = re.sub(r"[ \t]+", " ", text)

    # Three or more blank lines carry no more meaning than two.
    text = re.sub(r"\n{3,}", "\n\n", text)

    return "\n".join(line.strip() for line in text.split("\n")).strip()


def _read_pages(data: bytes) -> list[str]:
    """Extract raw text per page. The ONLY pypdf-specific function here."""
    try:
        reader = PdfReader(io.BytesIO(data))
    except PdfReadError as exc:
        raise PdfExtractionError(f"This file is not a readable PDF: {exc}") from exc
    except Exception as exc:  # pypdf raises assorted low-level errors
        raise PdfExtractionError(f"Could not open the PDF: {exc}") from exc

    if reader.is_encrypted:
        # An empty-password decrypt covers the common "printing restricted"
        # case; a real password is something we cannot and should not guess.
        try:
            if reader.decrypt("") == 0:
                raise PdfExtractionError(
                    "This PDF is password-protected. Please upload an unprotected copy."
                )
        except PdfExtractionError:
            raise
        except Exception as exc:
            raise PdfExtractionError(
                f"This PDF is encrypted and could not be opened: {exc}"
            ) from exc

    pages: list[str] = []
    for index, page in enumerate(reader.pages):
        try:
            pages.append(page.extract_text() or "")
        except Exception as exc:
            # One malformed page must not lose the other forty.
            logger.warning("page %d extraction failed: %s", index + 1, exc)
            pages.append("")
    return pages


def extract_document(data: bytes, *, filename: str = "upload.pdf") -> ExtractedDocument:
    """Validate, extract, and clean a PDF supplied as bytes.

    Raises `PdfExtractionError` for every bad-input case, with a message
    written for the person who uploaded the file.
    """
    if not data:
        raise PdfExtractionError("The uploaded file is empty.")

    if not looks_like_pdf(data):
        raise PdfExtractionError(
            "This file is not a PDF. The content does not start with a PDF "
            "signature, whatever the file extension says."
        )

    pages = _read_pages(data)
    if not pages:
        raise PdfExtractionError("This PDF contains no pages.")

    cleaned_pages = [clean_text(p) for p in pages]
    pages_with_text = sum(1 for p in cleaned_pages if p)
    text = clean_text("\n\n".join(p for p in cleaned_pages if p))

    if len(text) < MIN_USABLE_CHARS:
        raise PdfExtractionError(
            f"Almost no text could be extracted from '{filename}' "
            f"({len(text)} characters from {len(pages)} page(s)). This usually "
            "means the PDF is a scan or image-only document, which needs OCR "
            "that ResearchForge does not currently perform."
        )

    logger.info(
        "extracted %d chars from %d/%d pages of %s",
        len(text),
        pages_with_text,
        len(pages),
        filename,
    )
    return ExtractedDocument(text=text, page_count=len(pages), pages_with_text=pages_with_text)

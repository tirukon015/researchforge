# ruff: noqa: E501  (diagram labels and alt text are long literal strings by design)
"""Render a fictional demo paper (HTML) into a small, text-only PDF.

    python docs/screenshots/case-study/demo-data/make_demo_pdf.py \
        docs/screenshots/case-study/demo-data/fictional_paper_1_spaced_retrieval.html \
        Voss_Okafor_Spaced_Retrieval_DEMO.pdf

WHAT THIS IS FOR
----------------
The case-study screenshots were captured on the live deployment by uploading
two short papers written for the purpose. Every author, institution, dataset,
result and citation in them is invented, and each paper says so on its first
line. They exist only to demonstrate the interface. They are NOT sample papers:
data/samples/ holds real, openly licensed papers only (CLAUDE.md section 5),
and nothing here feeds results/.

WHY A HAND-WRITTEN PDF WRITER
-----------------------------
The PDF had to be small enough to hand to the browser as a base64 string
(the browser tab could not read local files), so it uses the two standard
base-14 fonts with no font embedding. The output is a valid PDF that
src/ingestion/pdf.py extracts normally (3 pages, about 6 to 7 thousand
characters each). Standard library only, plus nothing else.
"""

from __future__ import annotations

import re
import sys
import textwrap
import zlib
from html.parser import HTMLParser


class _Blocks(HTMLParser):
    """Collect (kind, text) blocks from the demo paper's simple HTML."""

    def __init__(self) -> None:
        super().__init__()
        self.blocks: list[tuple[str, str]] = []
        self.cur: str | None = None
        self.buf = ""
        self.skip = False
        self.row: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag in ("style", "title"):
            self.skip = True
        cls = dict(attrs).get("class", "")
        if tag in ("h1", "h2", "p", "div") and self.row is None:
            self.flush()
            if tag in ("h1", "h2"):
                self.cur = tag
            elif cls == "banner":
                self.cur = "banner"
            elif cls in ("authors", "affil"):
                self.cur = "center"
            else:
                self.cur = "p"
        if tag == "tr":
            self.flush()
            self.row = []
        if tag in ("td", "th"):
            self.buf = ""

    def handle_endtag(self, tag):
        if tag in ("style", "title"):
            self.skip = False
        if tag in ("td", "th") and self.row is not None:
            self.row.append(self.buf.strip())
            self.buf = ""
        elif tag == "tr" and self.row is not None:
            self.blocks.append(("row", "   |   ".join(self.row)))
            self.row = None
        elif tag in ("h1", "h2", "p", "div"):
            self.flush()

    def handle_data(self, data):
        if not self.skip:
            self.buf += data

    def flush(self):
        text = re.sub(r"\s+", " ", self.buf).strip()
        if text and self.cur:
            self.blocks.append((self.cur, text))
        self.buf = ""
        self.cur = "p"


# font resource, size in points, wrap width in characters
FONTS = {
    "h1": ("F2", 15, 70),
    "h2": ("F2", 11.5, 95),
    "p": ("F1", 10.5, 100),
    "banner": ("F2", 9, 118),
    "center": ("F1", 10, 110),
    "row": ("F1", 9.5, 120),
}
PAGE_W, PAGE_H, LEFT, TOP, BOTTOM = 595, 842, 60, 790, 60


def _escape(text: str) -> str:
    text = text.encode("ascii", "replace").decode()
    return text.replace("\\", "\\\\").replace("(", r"\(").replace(")", r"\)")


def build_pdf(blocks: list[tuple[str, str]]) -> bytes:
    pages: list[list[str]] = []
    ops: list[str] = []
    y = TOP
    for kind, text in blocks:
        font, size, width = FONTS[kind]
        lead = size * 1.35
        lines = textwrap.wrap(text, width)
        gap = lead * (1.2 if kind in ("h1", "h2") else 0.5)
        if y - gap - lead * min(len(lines), 3) < BOTTOM:
            pages.append(ops)
            ops, y = [], TOP
        y -= gap
        for line in lines:
            if y < BOTTOM:
                pages.append(ops)
                ops, y = [], TOP
            x = LEFT if kind not in ("h1", "center") else max(LEFT, (PAGE_W - len(line) * size * 0.47) / 2)
            ops.append(f"BT /{font} {size} Tf {x:.1f} {y:.1f} Td ({_escape(line)}) Tj ET")
            y -= lead
    pages.append(ops)

    objs: list[bytes | None] = []

    def add(obj: bytes | None) -> int:
        objs.append(obj)
        return len(objs)

    catalog, page_tree = add(None), add(None)
    f1 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Times-Roman /Encoding /WinAnsiEncoding >>")
    f2 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
    kids = []
    for page_ops in pages:
        data = zlib.compress("\n".join(page_ops).encode())
        content = add(b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(data) + data + b"\nendstream")
        kids.append(add(
            f"<< /Type /Page /Parent {page_tree} 0 R /MediaBox [0 0 {PAGE_W} {PAGE_H}] "
            f"/Resources << /Font << /F1 {f1} 0 R /F2 {f2} 0 R >> >> /Contents {content} 0 R >>".encode()
        ))
    objs[catalog - 1] = f"<< /Type /Catalog /Pages {page_tree} 0 R >>".encode()
    objs[page_tree - 1] = (
        f"<< /Type /Pages /Kids [{' '.join(f'{k} 0 R' for k in kids)}] /Count {len(kids)} >>".encode()
    )

    out = b"%PDF-1.4\n"
    offsets = []
    for i, obj in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += (
        f"trailer\n<< /Size {len(objs) + 1} /Root {catalog} 0 R "
        f"/Info << /Title (Fictional demonstration paper) >> >>\nstartxref\n{xref}\n%%EOF\n"
    ).encode()
    return out


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    parser = _Blocks()
    with open(argv[1], encoding="utf-8") as fh:
        parser.feed(fh.read())
    parser.flush()
    pdf = build_pdf(parser.blocks)
    with open(argv[2], "wb") as fh:
        fh.write(pdf)
    print(f"wrote {argv[2]} ({len(pdf)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

"""Build the PowerPoint deck from SLIDES.md.

    python docs/report/build_deck.py

SLIDES.md is the SOURCE. This renders it as a real .pptx - actual PowerPoint
tables, not screenshots or pasted text - so the deck and the report cannot
drift apart.

LAYOUT APPROACH
---------------
Each slide's blocks are measured before anything is drawn, and the whole slide
is scaled down if the content would overflow. A deck that silently runs text
off the bottom of the slide is worse than one with slightly smaller type, and
the alternative - hand-tuning fourteen slides - breaks the moment a number
changes.

The `> *Visual: ...*` lines in the source become speaker notes rather than
body text: they are instructions to the presenter, not content for the
audience.
"""

from __future__ import annotations

import pathlib
import re

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "submission"

W, H = Inches(13.333), Inches(7.5)
MARGIN = Inches(0.62)
CONTENT_TOP = Inches(1.55)
CONTENT_H = H - CONTENT_TOP - Inches(0.5)
CONTENT_W = W - 2 * MARGIN

INK = RGBColor(0x0F, 0x17, 0x2A)
BLUE = RGBColor(0x25, 0x63, 0xEB)
BLUE_DARK = RGBColor(0x1E, 0x40, 0xAF)
MUTED = RGBColor(0x64, 0x74, 0x8B)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
AMBER = RGBColor(0xB4, 0x53, 0x09)
PAGE = RGBColor(0xF8, 0xFA, 0xFC)
HEADER_FILL = RGBColor(0xE8, 0xEE, 0xF9)

FONT = "Calibri"
MONO = "Consolas"

_INLINE = re.compile(r"(\*\*.+?\*\*|(?<!\*)\*[^*\n]+?\*|`[^`\n]+?`)")


def emphasis(text: str):
    """-> [(text, bold, italic, mono)], resolving nested emphasis."""
    out = []
    for piece in _INLINE.split(text):
        if not piece:
            continue
        b = i = m = False
        if piece.startswith("**") and piece.endswith("**"):
            piece, b = piece[2:-2], True
        elif piece.startswith("*") and piece.endswith("*"):
            piece, i = piece[1:-1], True
        elif piece.startswith("`") and piece.endswith("`"):
            piece, m = piece[1:-1], True
        if b or i:  # emphasis may wrap inline code
            for sub in _INLINE.split(piece):
                if not sub:
                    continue
                if sub.startswith("`") and sub.endswith("`"):
                    out.append((sub[1:-1], b, i, True))
                else:
                    out.append((sub, b, i, False))
        else:
            out.append((piece, b, i, m))
    return out or [(text, False, False, False)]


def write(frame_or_para, text, *, size, colour=INK, bold=False, align=PP_ALIGN.LEFT):
    p = frame_or_para
    p.alignment = align
    for chunk, b, i, m in emphasis(text):
        r = p.add_run()
        r.text = chunk
        r.font.size = Pt(size)
        r.font.bold = bold or b
        r.font.italic = i
        r.font.name = MONO if m else FONT
        r.font.color.rgb = colour
    return p


# ------------------------------------------------------------------ parsing

def parse(md: str):
    """SLIDES.md -> [{'title', 'blocks', 'notes'}]"""
    slides, cur = [], None
    in_fence = False
    buf_kind, buf = None, []

    def flush():
        nonlocal buf_kind, buf
        if cur is not None and buf:
            cur["blocks"].append((buf_kind, buf))
        buf_kind, buf = None, []

    for raw in md.splitlines():
        line = raw.rstrip()

        m = re.match(r"^## Slide \d+\s*[—-]\s*(.*)$", line)
        if m:
            flush()
            cur = {"title": m.group(1).strip(), "blocks": [], "notes": []}
            slides.append(cur)
            continue
        if cur is None:
            continue

        if line.lstrip().startswith("```"):
            if in_fence:
                flush()
                in_fence = False
            else:
                flush()
                buf_kind, buf = "code", []
                in_fence = True
            continue
        if in_fence:
            buf.append(raw)
            continue

        if line.startswith("|") and line.count("|") >= 2:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c or "-") for c in cells if c):
                continue
            if buf_kind != "table":
                flush()
                buf_kind, buf = "table", []
            buf.append(cells)
            continue
        if buf_kind == "table":
            flush()

        if not line.strip() or re.fullmatch(r"-{3,}", line.strip()):
            flush()
            continue

        # presenter instructions -> speaker notes
        if re.match(r"^>\s*\*Visual", line):
            flush()
            cur["notes"].append(re.sub(r"^>\s*|\*", "", line).strip())
            continue

        if line.startswith("#"):
            flush()
            cur["blocks"].append(("head", [re.sub(r"^#+\s*", "", line)]))
            continue
        if line.startswith(">"):
            text = line.lstrip(">").strip()
            if not text:
                flush()
                continue
            if buf_kind == "quote":
                buf.append(text)
            else:
                flush()
                buf_kind, buf = "quote", [text]
            continue
        m = re.match(r"^\s*[-*+]\s+(.*)$", line)
        if m:
            if buf_kind != "bullet":
                flush()
                buf_kind, buf = "bullet", []
            buf.append(m.group(1))
            continue
        m = re.match(r"^\s*\d+\.\s+(.*)$", line)
        if m:
            if buf_kind != "bullet":
                flush()
                buf_kind, buf = "bullet", []
            buf.append(m.group(1))
            continue

        if buf_kind in ("para", "bullet", "quote"):
            buf.append(line.strip())
        else:
            flush()
            buf_kind, buf = "para", [line.strip()]

    flush()
    return slides


# ----------------------------------------------------------------- drawing

def rect(slide, x, y, w, h, fill):
    from pptx.enum.shapes import MSO_SHAPE
    s = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h)
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    s.line.fill.background()
    s.shadow.inherit = False
    return s


def measure(blocks, scale):
    """Rough height in EMU, so a slide can be scaled before it overflows."""
    total = 0
    for kind, items in blocks:
        if kind == "table":
            total += Inches(0.42 * scale) * len(items) + Inches(0.18)
        elif kind == "code":
            total += Inches(0.26 * scale) * len(items) + Inches(0.22)
        elif kind == "head":
            total += Inches(0.46 * scale)
        elif kind == "bullet":
            total += sum(Inches(0.34 * scale) * max(1, len(i) // 78 + 1) for i in items)
            total += Inches(0.1)
        else:
            joined = " ".join(items)
            total += Inches(0.32 * scale) * max(1, len(joined) // 82 + 1) + Inches(0.12)
    return total


def add_table(slide, rows, top, scale):
    cols = max(len(r) for r in rows)
    height = Inches(0.42 * scale) * len(rows)
    shape = slide.shapes.add_table(len(rows), cols, MARGIN, top, CONTENT_W, height)
    table = shape.table
    for i, row in enumerate(rows):
        table.rows[i].height = Inches(0.42 * scale)
        for j in range(cols):
            cell = table.cell(i, j)
            cell.margin_top = cell.margin_bottom = Inches(0.02)
            cell.margin_left = cell.margin_right = Inches(0.08)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.fill.solid()
            cell.fill.fore_color.rgb = HEADER_FILL if i == 0 else WHITE
            tf = cell.text_frame
            tf.word_wrap = True
            para = tf.paragraphs[0]
            text = row[j] if j < len(row) else ""
            colour = BLUE_DARK if i == 0 else INK
            write(para, text, size=15 * scale, colour=colour, bold=(i == 0))
    return top + height + Inches(0.18)


def add_text(slide, text, top, *, size, colour=INK, bold=False, italic=False,
             height=None, fill=None, bar=None):
    h = height or Inches(0.4)
    left, width = MARGIN, CONTENT_W
    if fill is not None:
        rect(slide, left, top, width, h, fill)
    if bar is not None:
        rect(slide, left, top, Inches(0.06), h, bar)
        left, width = left + Inches(0.22), width - Inches(0.22)
    box = slide.shapes.add_textbox(left, top, width, h)
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.06)
    tf.margin_top = tf.margin_bottom = Inches(0.02)
    p = tf.paragraphs[0]
    write(p, text, size=size, colour=colour, bold=bold)
    if italic:
        for r in p.runs:
            r.font.italic = True
    return top + h


def title_slide(prs, slides_md):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    rect(slide, 0, 0, W, H, BLUE_DARK)
    rect(slide, 0, H - Inches(0.28), W, Inches(0.28), BLUE)

    box = slide.shapes.add_textbox(MARGIN, Inches(2.1), CONTENT_W, Inches(1.5))
    p = box.text_frame.paragraphs[0]
    write(p, "ResearchForge", size=60, colour=WHITE, bold=True, align=PP_ALIGN.CENTER)

    box = slide.shapes.add_textbox(MARGIN, Inches(3.35), CONTENT_W, Inches(0.8))
    p = box.text_frame.paragraphs[0]
    write(p, "An AI Research Paper Assistant", size=26,
          colour=RGBColor(0xBF, 0xD3, 0xF2), align=PP_ALIGN.CENTER)

    box = slide.shapes.add_textbox(MARGIN, Inches(4.5), CONTENT_W, Inches(1.6))
    tf = box.text_frame
    for i, line in enumerate((
        "BIT 4543 — Artificial Intelligence  ·  Project #17",
        "[GROUP MEMBER NAMES & STUDENT IDs]",
        "Lecturer: Azuan Nazeer",
        "researchforge.rukon.dev",
    )):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(6)
        write(p, line, size=17 if i else 19,
              colour=WHITE if i in (0, 3) else RGBColor(0xBF, 0xD3, 0xF2),
              bold=(i == 3), align=PP_ALIGN.CENTER)
    return slide


def content_slide(prs, spec, number, total):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    rect(slide, 0, 0, W, H, PAGE)
    rect(slide, 0, 0, W, Inches(1.15), BLUE_DARK)
    rect(slide, 0, Inches(1.15), W, Inches(0.05), BLUE)

    box = slide.shapes.add_textbox(MARGIN, Inches(0.24), CONTENT_W - Inches(1.2), Inches(0.75))
    box.text_frame.word_wrap = True
    write(box.text_frame.paragraphs[0], spec["title"], size=30, colour=WHITE, bold=True)

    box = slide.shapes.add_textbox(W - Inches(1.5), Inches(0.42), Inches(1.0), Inches(0.4))
    write(box.text_frame.paragraphs[0], f"{number}/{total}", size=13,
          colour=RGBColor(0x9D, 0xB8, 0xE8), align=PP_ALIGN.RIGHT)

    blocks = spec["blocks"]
    scale = 1.0
    while measure(blocks, scale) > CONTENT_H and scale > 0.62:
        scale -= 0.04

    top = CONTENT_TOP
    for kind, items in blocks:
        if kind == "table":
            top = add_table(slide, items, top, scale)
        elif kind == "code":
            h = Inches(0.26 * scale) * len(items) + Inches(0.18)
            rect(slide, MARGIN, top, CONTENT_W, h, RGBColor(0xEC, 0xF1, 0xF9))
            box = slide.shapes.add_textbox(MARGIN + Inches(0.12), top + Inches(0.07),
                                           CONTENT_W - Inches(0.24), h)
            tf = box.text_frame
            tf.word_wrap = False
            for i, line in enumerate(items):
                p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
                p.space_after = Pt(0)
                r = p.add_run()
                r.text = line
                r.font.size = Pt(13 * scale)
                r.font.name = MONO
                r.font.color.rgb = INK
            top += h + Inches(0.16)
        elif kind == "head":
            top = add_text(slide, items[0], top, size=19 * scale, colour=BLUE_DARK,
                           bold=True, height=Inches(0.44 * scale))
        elif kind == "quote":
            text = " ".join(items)
            lines = max(1, len(text) // 76 + 1)
            h = Inches(0.36 * scale) * lines + Inches(0.14)
            top = add_text(slide, text, top, size=17 * scale, colour=BLUE_DARK,
                           height=h, fill=RGBColor(0xE8, 0xEE, 0xF9), bar=BLUE)
            top += Inches(0.12)
        elif kind == "bullet":
            for item in items:
                lines = max(1, len(item) // 82 + 1)
                h = Inches(0.32 * scale) * lines
                box = slide.shapes.add_textbox(MARGIN, top, CONTENT_W, h)
                tf = box.text_frame
                tf.word_wrap = True
                tf.margin_top = tf.margin_bottom = 0
                p = tf.paragraphs[0]
                r = p.add_run()
                r.text = "•  "
                r.font.size = Pt(17 * scale)
                r.font.color.rgb = BLUE
                r.font.bold = True
                write(p, item, size=17 * scale)
                top += h
            top += Inches(0.1)
        else:
            text = " ".join(items)
            lines = max(1, len(text) // 86 + 1)
            h = Inches(0.3 * scale) * lines + Inches(0.08)
            top = add_text(slide, text, top, size=16 * scale, height=h)

    if spec["notes"]:
        slide.notes_slide.notes_text_frame.text = "\n".join(spec["notes"])
    return slide


def build():
    md = (HERE / "SLIDES.md").read_text(encoding="utf-8")
    specs = parse(md)
    if not specs:
        raise SystemExit("no slides parsed from SLIDES.md")

    prs = Presentation()
    prs.slide_width, prs.slide_height = W, H

    title_slide(prs, specs[0])
    body = specs[1:]
    for i, spec in enumerate(body, start=2):
        content_slide(prs, spec, i, len(body) + 1)

    OUT.mkdir(exist_ok=True)
    path = OUT / "ResearchForge_Slides.pptx"
    prs.save(path)
    return path, len(body) + 1


if __name__ == "__main__":
    path, n = build()
    print(f"  {path.name:42} {path.stat().st_size:>9,} bytes   {n} slides")

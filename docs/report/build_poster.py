"""Build the A1 conference poster as a printable .pptx.

    python docs/report/build_poster.py

POSTER.md is the design specification; this renders it. One PowerPoint slide
sized to A1 portrait (594 x 841 mm), which prints directly or exports to PDF.

Every figure on the poster comes from `results/evaluation/`.

LAYOUT
------
Six horizontal bands on a 12-column grid. Band 4 - the finding - is the
largest, because it is the part a passer-by should read even if they read
nothing else. Type is sized for reading at about 1.5 m: body 24 pt, hero
statistics 130 pt.
"""

from __future__ import annotations

import pathlib

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

OUT = pathlib.Path(__file__).resolve().parent / "submission"

# A1 portrait
W, H = Inches(23.39), Inches(33.11)
PAD = Inches(0.85)
# EMU coordinates must be INTEGERS. A float reaches the XML as "10922508.0"
# and PowerPoint refuses to open the file, so every computed dimension is
# coerced back to a whole EMU here rather than at each call site.
COL = Emu(int((W - 2 * PAD) / 12))

BLUE = RGBColor(0x25, 0x63, 0xEB)
BLUE_DARK = RGBColor(0x1E, 0x40, 0xAF)
INK = RGBColor(0x0F, 0x17, 0x2A)
MUTED = RGBColor(0x64, 0x74, 0x8B)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
PAGE = RGBColor(0xF8, 0xFA, 0xFC)
SURFACE = RGBColor(0xFF, 0xFF, 0xFF)
AMBER = RGBColor(0xB4, 0x53, 0x09)
AMBER_BG = RGBColor(0xFD, 0xF6, 0xEC)
EMERALD = RGBColor(0x04, 0x78, 0x57)
EMERALD_BG = RGBColor(0xEC, 0xFA, 0xF4)
HEADER_FILL = RGBColor(0xE8, 0xEE, 0xF9)
FONT = "Calibri"
MONO = "Consolas"


def cols(n):
    return Emu(int(COL * n))


def rect(slide, x, y, w, h, fill, line=None):
    s = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h)
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line
        s.line.width = Pt(1.5)
    s.shadow.inherit = False
    return s


def text(slide, x, y, w, h, runs, *, size, colour=INK, bold=False,
         align=PP_ALIGN.LEFT, spacing=1.0, anchor=MSO_ANCHOR.TOP):
    """`runs` is a string or a list of (text, bold, colour, size_override)."""
    box = slide.shapes.add_textbox(x, y, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(0.05)
    tf.margin_top = tf.margin_bottom = Inches(0.02)
    lines = runs if isinstance(runs, list) else [runs]
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = spacing
        pieces = line if isinstance(line, list) else [(line, bold, colour, size)]
        for t, b, c, s in pieces:
            r = p.add_run()
            r.text = t
            r.font.size = Pt(s)
            r.font.bold = b
            r.font.name = FONT
            r.font.color.rgb = c
    return box


def table(slide, x, y, w, rows, *, size, row_h, head_fill=HEADER_FILL,
          emphasis_col=None, emphasis_colour=AMBER):
    n, cn = len(rows), max(len(r) for r in rows)
    shape = slide.shapes.add_table(n, cn, x, y, w, Inches(row_h) * n)
    tb = shape.table
    for i, row in enumerate(rows):
        tb.rows[i].height = Inches(row_h)
        for j in range(cn):
            cell = tb.cell(i, j)
            cell.margin_left = cell.margin_right = Inches(0.09)
            cell.margin_top = cell.margin_bottom = Inches(0.03)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.fill.solid()
            cell.fill.fore_color.rgb = head_fill if i == 0 else SURFACE
            p = cell.text_frame.paragraphs[0]
            r = p.add_run()
            r.text = row[j] if j < len(row) else ""
            r.font.size = Pt(size)
            r.font.name = FONT
            r.font.bold = (i == 0)
            if i > 0 and emphasis_col is not None and j == emphasis_col:
                r.font.color.rgb = emphasis_colour
                r.font.bold = True
            else:
                r.font.color.rgb = BLUE_DARK if i == 0 else INK
    return y + Inches(row_h) * n


def build():
    prs = Presentation()
    prs.slide_width, prs.slide_height = W, H
    s = prs.slides.add_slide(prs.slide_layouts[6])
    rect(s, 0, 0, W, H, PAGE)

    # ---------------------------------------------------- BAND 1: title
    y = 0
    band = Inches(3.05)
    rect(s, 0, 0, W, band, BLUE_DARK)
    rect(s, 0, band - Inches(0.09), W, Inches(0.09), BLUE)
    text(s, PAD, Inches(0.42), W - 2 * PAD, Inches(1.3), "ResearchForge",
         size=96, colour=WHITE, bold=True, align=PP_ALIGN.CENTER)
    text(s, PAD, Inches(1.62), W - 2 * PAD, Inches(0.6),
         "An AI Research Paper Assistant — grounded, isolated, and honestly measured",
         size=32, colour=RGBColor(0xBF, 0xD3, 0xF2), align=PP_ALIGN.CENTER)
    text(s, PAD, Inches(2.22), W - 2 * PAD, Inches(0.6), [
        [("[GROUP MEMBER NAMES & STUDENT IDs]", False, RGBColor(0xBF, 0xD3, 0xF2), 21)],
        [("BIT 4543 Artificial Intelligence · Project #17 · Lecturer: Azuan Nazeer · ",
          False, RGBColor(0xBF, 0xD3, 0xF2), 21),
         ("researchforge.rukon.dev", True, WHITE, 21)],
    ], size=21, align=PP_ALIGN.CENTER)
    y = band + Inches(0.3)

    # ------------------------------------- BAND 2: problem + objectives
    h2 = Inches(4.2)
    rect(s, PAD, y, cols(7) - Inches(0.2), h2, SURFACE, line=RGBColor(0xDD, 0xE4, 0xEE))
    text(s, PAD + Inches(0.3), y + Inches(0.24), cols(7) - Inches(0.8), Inches(0.5),
         "THE PROBLEM", size=26, colour=BLUE, bold=True)
    text(s, PAD + Inches(0.3), y + Inches(0.85), cols(7) - Inches(0.8), Inches(2.0),
         "Researchers read papers to decide which papers to read. For every result "
         "in a literature search: what does it claim, what does it leave open, how "
         "does it relate to the rest?", size=24, spacing=1.15)
    rect(s, PAD + Inches(0.3), y + Inches(2.85), Inches(0.09), Inches(1.35), AMBER)
    text(s, PAD + Inches(0.6), y + Inches(2.85), cols(7) - Inches(1.2), Inches(1.35),
         [[("A general chatbot will answer questions about a paper it never read. ",
            False, INK, 24)],
          [("A fabricated citation costs more time to detect than the summary saved.",
            True, AMBER, 24)]], size=24, spacing=1.15)

    ox = PAD + cols(7) + Inches(0.1)
    rect(s, ox, y, cols(5) - Inches(0.1), h2, SURFACE, line=RGBColor(0xDD, 0xE4, 0xEE))
    text(s, ox + Inches(0.3), y + Inches(0.24), cols(5) - Inches(0.7), Inches(0.5),
         "SIX OBJECTIVES", size=26, colour=BLUE, bold=True)
    objs = [
        "1  Summaries · research gaps · literature reviews",
        "2  Grounding enforced structurally, not by instruction",
        "3  Two providers, owner-selected, automatic fallback",
        "4  Isolation enforced by the database",
        "5  Each paper analysed once, however many upload it",
        "6  Empirical evaluation on real papers",
    ]
    oy = y + Inches(0.9)
    for o in objs:
        text(s, ox + Inches(0.3), oy, cols(5) - Inches(0.7), Inches(0.5), o,
             size=22, spacing=1.0)
        oy += Inches(0.52)
    y += h2 + Inches(0.3)

    # ------------------------------------------------ BAND 3: how it works
    h3 = Inches(5.5)
    rect(s, PAD, y, W - 2 * PAD, h3, SURFACE, line=RGBColor(0xDD, 0xE4, 0xEE))
    text(s, PAD + Inches(0.3), y + Inches(0.24), W - 2 * PAD, Inches(0.5),
         "HOW IT WORKS", size=26, colour=BLUE, bold=True)

    arch = ("Browser  →  Next.js frontend ─┐\n"
            "                              ├─  one Vercel project, shared origin\n"
            "          FastAPI backend  ◄──┘\n"
            "                    │\n"
            "        ┌───────────┼───────────┐\n"
            "        ▼           ▼           ▼\n"
            "     pypdf      provider     Supabase\n"
            "   extraction    router     PostgreSQL + RLS\n"
            "                    │\n"
            "            ┌───────┴───────┐\n"
            "            ▼               ▼\n"
            "     Anthropic Claude    Groq Qwen")
    bx = PAD + Inches(0.35)
    bw = cols(6) - Inches(0.6)
    rect(s, bx, y + Inches(0.85), bw, Inches(3.0), RGBColor(0xEC, 0xF1, 0xF9))
    box = s.shapes.add_textbox(bx + Inches(0.15), y + Inches(0.92), bw, Inches(3.0))
    tf = box.text_frame
    tf.word_wrap = False
    for i, ln in enumerate(arch.split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        r = p.add_run()
        r.text = ln
        r.font.size = Pt(17)
        r.font.name = MONO
        r.font.color.rgb = INK
    text(s, bx, y + Inches(3.95), bw, Inches(1.1),
         "Next.js 16 · FastAPI · Python 3.14 · 6,366 lines across 35 modules · "
         "538 automated tests passing", size=20, colour=MUTED, spacing=1.1)

    gx = PAD + cols(6) + Inches(0.25)
    gw = cols(6) - Inches(0.6)
    pipe = ("PDF → extract → SHA-256 hash → cache?\n"
            "        → 3 grounded passes → store\n\n"
            "        cache hit  3.2 s   |   miss  32.4 s")
    rect(s, gx, y + Inches(0.9), gw, Inches(1.55), RGBColor(0xEC, 0xF1, 0xF9))
    box = s.shapes.add_textbox(gx + Inches(0.15), y + Inches(1.0), gw, Inches(1.5))
    tf = box.text_frame
    for i, ln in enumerate(pipe.split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        r = p.add_run()
        r.text = ln
        r.font.size = Pt(17)
        r.font.name = MONO
        r.font.color.rgb = INK
    table(s, gx, y + Inches(2.4), gw, [
        ["Grounding layer", "Mechanism"],
        ["Prompt", "every claim traceable to the text"],
        ["Schema", "output constrained to a declared model"],
        ["Validation", "non-conforming output discarded, not repaired"],
        ["Escape", "must report insufficient evidence"],
    ], size=19, row_h=0.44)
    rect(s, gx, y + Inches(4.7), Inches(0.09), Inches(0.68), BLUE)
    text(s, gx + Inches(0.3), y + Inches(4.7), gw - Inches(0.3), Inches(0.68),
         [[("Not RAG. ", True, BLUE_DARK, 22),
           ("Whole-document grounded generation. No embeddings, no retrieval.",
            False, INK, 22)]], size=22)
    y += h3 + Inches(0.3)

    # ------------------------------------------------- BAND 4: THE FINDING
    h4 = Inches(9.7)
    rect(s, PAD, y, W - 2 * PAD, h4, AMBER_BG, line=AMBER)
    text(s, PAD, y + Inches(0.3), W - 2 * PAD, Inches(1.0),
         "A redundancy mechanism hides the failure it compensates for.",
         size=54, colour=AMBER, bold=True, align=PP_ALIGN.CENTER)

    ty = y + Inches(1.45)
    lw = cols(6) - Inches(0.7)
    lx = PAD + Inches(0.4)
    text(s, lx, ty, lw, Inches(0.5), "THE RESULT", size=24, colour=BLUE, bold=True)
    table(s, lx, ty + Inches(0.6), lw, [
        ["Pass", "Configuration", "Done", "By the configured provider"],
        ["A", "Claude primary", "5/5", "5/5"],
        ["B", "Groq primary", "5/5", "0/5"],
        ["C", "Groq only", "0/5", "0/5"],
    ], size=20, row_h=0.55, emphasis_col=3)
    text(s, lx, ty + Inches(2.8), lw, Inches(0.6),
         "15 runs · 10 analyses produced · all 10 written by Claude.",
         size=21, colour=MUTED)

    rx = PAD + cols(6) + Inches(0.3)
    rw = cols(6) - Inches(0.7)
    text(s, rx, ty, rw, Inches(0.5), "THE EVIDENCE", size=24, colour=BLUE, bold=True)
    rect(s, rx, ty + Inches(0.55), rw, Inches(1.25), RGBColor(0xF3, 0xE8, 0xD4))
    box = s.shapes.add_textbox(rx + Inches(0.18), ty + Inches(0.63), rw, Inches(1.2))
    tf = box.text_frame
    for i, ln in enumerate(["Request too large for model `qwen/qwen3.6-27b`",
                            "on input tokens per minute (ITPM):",
                            "Limit 7000, Requested 7920"]):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        r = p.add_run()
        r.text = ln
        r.font.size = Pt(19)
        r.font.name = MONO
        r.font.color.rgb = RGBColor(0x7A, 0x39, 0x06)
    table(s, rx, ty + Inches(1.9), rw, [
        ["Paper", "Pages", "Tokens needed", "Over"],
        ["SciBERT", "6", "7,920", "1.1×"],
        ["Attention", "15", "11,745", "1.7×"],
        ["Factual Consistency", "13", "12,661", "1.8×"],
        ["BERT", "16", "18,498", "2.6×"],
        ["RAG", "19", "20,362", "2.9×"],
    ], size=19, row_h=0.42, emphasis_col=3)

    # hero statistics
    hy = y + Inches(6.0)
    stats = [("7,000", "Groq free-tier limit,\ninput tokens per minute"),
             ("7,920", "tokens needed by the\nsmallest paper (6 pages)"),
             ("0/5", "papers Groq\ncould analyse")]
    sw = Emu(int((W - 2 * PAD - Inches(0.8)) / 3))
    for i, (big, cap) in enumerate(stats):
        sx = Emu(int(PAD + Inches(0.4) + sw * i))
        text(s, sx, hy, sw, Inches(1.5), big, size=104, colour=AMBER, bold=True,
             align=PP_ALIGN.CENTER)
        text(s, sx, hy + Inches(1.5), sw, Inches(0.9), cap.split("\n"),
             size=21, colour=INK, align=PP_ALIGN.CENTER, spacing=1.05)

    wy = y + Inches(8.45)
    rect(s, PAD + Inches(0.4), wy, Inches(0.1), Inches(1.1), AMBER)
    text(s, PAD + Inches(0.75), wy, W - 2 * PAD - Inches(1.3), Inches(1.1), [
        [("One provider was completely non-functional. Every analysis succeeded. "
          "The interface showed no error.", False, INK, 23)],
        [("Detectable only because every analysis records which provider ", False, INK, 23),
         ("actually", True, AMBER, 23),
         (" produced it — and because results were grouped by that record, not by "
          "configuration.", False, INK, 23)],
        [("Grouping by configuration would have reported that both providers "
          "performed identically, while measuring Claude twice.", True, AMBER, 23)],
    ], size=23, spacing=1.1)
    y += h4 + Inches(0.3)

    # ------------------------------------ BAND 5: verified + limitations
    h5 = Inches(6.1)
    rect(s, PAD, y, cols(6) - Inches(0.2), h5, EMERALD_BG, line=EMERALD)
    text(s, PAD + Inches(0.35), y + Inches(0.26), cols(6), Inches(0.5),
         "VERIFIED", size=26, colour=EMERALD, bold=True)
    text(s, PAD + Inches(0.35), y + Inches(0.85), cols(6) - Inches(0.9), Inches(1.5),
         [[("26 / 0", True, EMERALD, 66)],
          [("live isolation checks passed / failed", False, INK, 22)]], size=22)
    vy = y + Inches(2.35)
    for b in ("A new user's library is empty",
              "User B cannot read, delete or review User A's paper — 404, so "
              "existence is not disclosed",
              "PostgREST with the browser's own key returns ZERO rows — isolation "
              "is a database guarantee, not application behaviour"):
        text(s, PAD + Inches(0.35), vy, cols(6) - Inches(0.9), Inches(0.85),
             "•  " + b, size=21, spacing=1.1)
        vy += Inches(0.72)
    table(s, PAD + Inches(0.35), y + Inches(4.7), cols(6) - Inches(0.9), [
        ["Cache", "Latency", "Model called"],
        ["First upload", "32.4 s", "yes"],
        ["Repeat, same user", "3.2 s", "no"],
        ["Repeat, different user", "2.7 s", "no"],
    ], size=19, row_h=0.33, head_fill=RGBColor(0xD8, 0xF0, 0xE6))

    lx2 = PAD + cols(6) + Inches(0.1)
    rect(s, lx2, y, cols(6) - Inches(0.1), h5, SURFACE, line=RGBColor(0xDD, 0xE4, 0xEE))
    text(s, lx2 + Inches(0.35), y + Inches(0.26), cols(6), Inches(0.5),
         "HONEST LIMITATIONS", size=26, colour=BLUE, bold=True)
    ly = y + Inches(0.9)
    for head, rest in (
        ("No ground truth.", " We measured how much the system produced, not "
                             "whether it is right. A model inventing nine plausible "
                             "gaps would score identically."),
        ("Effectively single-provider.", " Redundancy is architectural, not actual."),
        ("Insufficient-evidence path never triggered.", " 0/10 runs."),
        ("Narrow corpus.", " 5 papers, one discipline, single runs, evaluated by "
                           "its own authors."),
        ("Practical limits.", " ~100 s per new analysis · no OCR · 5 s sign-out "
                              "window."),
    ):
        text(s, lx2 + Inches(0.35), ly, cols(6) - Inches(0.8), Inches(1.05),
             [[("•  " + head, True, INK, 21), (rest, False, INK, 21)]],
             size=21, spacing=1.1)
        ly += Inches(1.0)
    y += h5 + Inches(0.3)

    # ------------------------------------------------- BAND 6: conclusion
    h6 = Emu(int(H - y - PAD + Inches(0.3)))
    rect(s, 0, y, W, h6, BLUE_DARK)
    text(s, PAD, y + Inches(0.45), cols(8), Inches(2.4), [
        [("A deployed system meeting all five requirements — grounding enforced "
          "structurally, isolation enforced by PostgreSQL, provenance recorded "
          "per analysis.", False, WHITE, 24)],
        [("Next: ", True, WHITE, 24),
         ("ground-truth evaluation with expert-annotated gaps · a second provider "
          "that can accept a full paper · a deliberate test of the "
          "insufficient-evidence path.", False, RGBColor(0xBF, 0xD3, 0xF2), 24)],
    ], size=24, spacing=1.15)
    text(s, PAD, y + h6 - Inches(1.15), cols(8), Inches(0.8),
         "The most valuable results came from checking what the system actually "
         "did, rather than trusting what the code implied it would do.",
         size=22, colour=RGBColor(0xBF, 0xD3, 0xF2))
    # The QR block is sized from the band it sits in rather than fixed, and the
    # caption's width is measured to the right margin - both overflowed the A1
    # sheet when they were hard-coded.
    qx = PAD + cols(8) + Inches(0.4)
    qs = Inches(1.9)
    rect(s, qx, y + Inches(0.3), qs, qs, WHITE)
    text(s, qx, y + Inches(0.9), qs, Inches(0.7), "QR",
         size=36, colour=MUTED, align=PP_ALIGN.CENTER, bold=True)
    cap_x = qx + qs + Inches(0.35)
    text(s, cap_x, y + Inches(0.7), W - PAD - cap_x, Inches(1.5),
         [[("Live system", True, WHITE, 26)],
          [("researchforge.rukon.dev", False, RGBColor(0xBF, 0xD3, 0xF2), 22)]],
         size=22, spacing=1.2)

    OUT.mkdir(exist_ok=True)
    path = OUT / "ResearchForge_Poster_A1.pptx"
    prs.save(path)
    return path


if __name__ == "__main__":
    p = build()
    print(f"  {p.name:42} {p.stat().st_size:>9,} bytes   A1 portrait 594x841mm")

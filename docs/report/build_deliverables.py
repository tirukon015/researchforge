"""Build the submission deliverables: .docx reports and a .pptx deck.

    python docs/report/build_deliverables.py

The Markdown files in this folder are the SOURCE. This script renders them into
the formats the assignment is submitted in, so there is exactly one place to
edit a fact and no chance of the Word file and the Markdown drifting apart.

Re-run it after editing any source document.

WHAT IT HANDLES
---------------
Headings, paragraphs, bulleted and numbered lists, block quotes, fenced code,
horizontal rules, and GitHub-style tables - plus inline bold, italic, inline
code and links inside all of them. Each `# Chapter` starts a new page.

Mermaid blocks in DIAGRAMS.md are rendered as their source text: Word cannot
draw them. The diagram images have to be exported separately and dropped in,
which is noted in the generated file rather than left as a silent gap.
"""

from __future__ import annotations

import pathlib
import re

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "submission"

BODY_FONT = "Calibri"
MONO_FONT = "Consolas"
INK = RGBColor(0x0F, 0x17, 0x2A)
BLUE = RGBColor(0x1E, 0x40, 0xAF)
MUTED = RGBColor(0x64, 0x74, 0x8B)


# --------------------------------------------------------------- inline text

def _unlink(s: str) -> str:
    """`[label](url)` -> readable text.

    The URL is kept visible unless it merely repeats the label: this is a
    printed document, and a hyperlink whose target cannot be seen is a dead
    reference on paper.
    """
    m = re.fullmatch(r"\[([^\]]+?)\]\(([^)]+?)\)", s)
    if not m:
        return s
    label, url = m.group(1), m.group(2)
    return label if label.strip("<>") == url.strip("<>") else f"{label} ({url})"


# Applied in this order, each level recursing into what the previous unwrapped.
# Order matters: emphasis is stripped before code, so `**bold `code`**` keeps
# BOTH - the earlier non-recursive version dropped the inner marker and left
# literal backticks in the Word file.
_LEVELS = [
    (re.compile(r"(\*\*.+?\*\*)", re.S), lambda s: (s[2:-2], "bold")),
    (re.compile(r"((?<!\*)\*[^*\n]+?\*(?!\*))"), lambda s: (s[1:-1], "italic")),
    (re.compile(r"(`[^`\n]+?`)"), lambda s: (s[1:-1], "mono")),
    (re.compile(r"(\[[^\]]+?\]\([^)]+?\))"), lambda s: (_unlink(s), None)),
]


def add_inline(paragraph, text: str, *, size=11, colour=INK, bold_all=False,
               bold=False, italic=False, mono=False, _level=0):
    """Write `text` into `paragraph`, honouring nested inline Markdown."""
    if _level == 0:
        text = text.replace("<br/>", "\n").replace("<br>", "\n")
        bold = bold or bold_all

    if _level < len(_LEVELS):
        pattern, unwrap = _LEVELS[_level]
        nxt = dict(size=size, colour=colour, _level=_level + 1)
        for piece in pattern.split(text):
            if not piece:
                continue
            if pattern.fullmatch(piece):
                inner, flag = unwrap(piece)
                add_inline(paragraph, inner, bold=bold or flag == "bold",
                           italic=italic or flag == "italic",
                           mono=mono or flag == "mono", **nxt)
            else:
                add_inline(paragraph, piece, bold=bold, italic=italic,
                           mono=mono, **nxt)
        return

    run = paragraph.add_run(text)
    run.bold, run.italic = bold, italic
    run.font.name = MONO_FONT if mono else BODY_FONT
    run.font.size = Pt(size - 1 if mono else size)
    run.font.color.rgb = colour


def shade(cell_or_para, hex_colour: str):
    el = OxmlElement("w:shd")
    el.set(qn("w:val"), "clear")
    el.set(qn("w:fill"), hex_colour)
    target = cell_or_para._tc if hasattr(cell_or_para, "_tc") else cell_or_para._p.get_or_add_pPr()
    target.append(el)


# ------------------------------------------------------------------ blocks

def add_code(doc, lines: list[str]):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.25)
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(6)
    shade(p, "F1F5F9")
    run = p.add_run("\n".join(lines))
    run.font.name = MONO_FONT
    run.font.size = Pt(9)
    run.font.color.rgb = INK


def add_table(doc, rows: list[list[str]]):
    if not rows:
        return
    cols = max(len(r) for r in rows)
    table = doc.add_table(rows=0, cols=cols)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = True

    for i, row in enumerate(rows):
        cells = table.add_row().cells
        for j in range(cols):
            text = row[j] if j < len(row) else ""
            cell = cells[j]
            cell.text = ""
            para = cell.paragraphs[0]
            para.paragraph_format.space_before = Pt(2)
            para.paragraph_format.space_after = Pt(2)
            add_inline(para, text, size=9, bold_all=(i == 0))
            if i == 0:
                shade(cell, "E8EEF9")
    doc.add_paragraph().paragraph_format.space_after = Pt(4)


def flush(doc, state):
    """Emit whatever block has been accumulating."""
    kind, buf = state["kind"], state["buf"]
    if kind == "table":
        add_table(doc, buf)
    elif kind == "code":
        add_code(doc, buf)
    state["kind"], state["buf"] = None, []


# ------------------------------------------------------------- the renderer

_BLOCK_START = re.compile(
    r"^\s*(?:#{1,4}\s|[-*+]\s|\d+\.\s|>|\||```|(?:-{3,}|\*{3,}|_{3,})\s*$)"
)


def render(doc, md: str, *, page_break_on_h1=True):
    state = {"kind": None, "buf": []}
    pending: dict | None = None
    in_fence = False
    first_h1 = True

    def emit_pending():
        """Write the accumulated text block as ONE Word paragraph.

        The source Markdown is hard-wrapped at about 79 characters. Treating
        each source line as its own paragraph would put a hard break in the
        middle of every sentence, and would also split inline formatting that
        spans a wrap - `**two words` on one line and `bolded**` on the next
        never matches as bold. Joining first fixes both.
        """
        nonlocal pending
        if not pending:
            return
        text = " ".join(pending["lines"]).strip()
        pending_kind = pending["kind"]
        pending = None
        if not text:
            return
        if pending_kind == "quote":
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Inches(0.3)
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(4)
            shade(p, "F8FAFC")
            add_inline(p, text, size=10.5)
        elif pending_kind == "bullet":
            p = doc.add_paragraph(style="List Bullet")
            p.paragraph_format.space_after = Pt(2)
            add_inline(p, text, size=11)
        elif pending_kind == "number":
            p = doc.add_paragraph(style="List Number")
            p.paragraph_format.space_after = Pt(2)
            add_inline(p, text, size=11)
        else:
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(6)
            p.paragraph_format.line_spacing = 1.15
            add_inline(p, text, size=11)

    def heading(text, level):
        nonlocal first_h1
        if level == 1 and page_break_on_h1 and not first_h1:
            doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
        if level == 1:
            first_h1 = False
        h = doc.add_heading(level=min(level, 4))
        h.paragraph_format.space_before = Pt(14 if level <= 2 else 10)
        h.paragraph_format.space_after = Pt(6)
        for r in h.runs:
            r.text = ""
        add_inline(h, text, size={1: 18, 2: 14, 3: 12, 4: 11}[level],
                   colour=BLUE, bold_all=True)

    for raw in md.splitlines():
        line = raw.rstrip()

        # fenced code
        if line.lstrip().startswith("```"):
            if in_fence:
                flush(doc, state)
                in_fence = False
            else:
                emit_pending()
                flush(doc, state)
                state["kind"], state["buf"] = "code", []
                in_fence = True
            continue
        if in_fence:
            state["buf"].append(raw)
            continue

        # tables
        if line.startswith("|") and line.count("|") >= 2:
            emit_pending()
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c or "-") for c in cells if c):
                continue  # the |---|---| separator
            if state["kind"] != "table":
                flush(doc, state)
                state["kind"], state["buf"] = "table", []
            state["buf"].append(cells)
            continue
        if state["kind"] == "table":
            flush(doc, state)

        if not line.strip():
            emit_pending()
            continue

        # headings
        m = re.match(r"^(#{1,4})\s+(.*)$", line)
        if m:
            emit_pending()
            heading(m.group(2).strip(), len(m.group(1)))
            continue

        # horizontal rule
        if re.fullmatch(r"-{3,}|\*{3,}|_{3,}", line.strip()):
            emit_pending()
            continue

        # block quote - which may itself contain a heading
        if line.lstrip().startswith(">"):
            text = line.lstrip().lstrip(">").strip()
            if not text:
                emit_pending()
                continue
            m = re.match(r"^(#{1,4})\s+(.*)$", text)
            if m:
                emit_pending()
                heading(m.group(2).strip(), len(m.group(1)))
                continue
            if pending and pending["kind"] == "quote":
                pending["lines"].append(text)
            else:
                emit_pending()
                pending = {"kind": "quote", "lines": [text]}
            continue

        # lists
        m = re.match(r"^\s*[-*+]\s+(.*)$", line)
        if m:
            emit_pending()
            pending = {"kind": "bullet", "lines": [m.group(1)]}
            continue
        m = re.match(r"^\s*\d+\.\s+(.*)$", line)
        if m:
            emit_pending()
            pending = {"kind": "number", "lines": [m.group(1)]}
            continue

        # a continuation of whatever is open, or a new paragraph
        if pending and not _BLOCK_START.match(line):
            pending["lines"].append(line.strip())
        else:
            emit_pending()
            pending = {"kind": "para", "lines": [line.strip()]}

    emit_pending()
    flush(doc, state)


# -------------------------------------------------------------- page set-up

def new_document(*, landscape=False) -> Document:
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = BODY_FONT
    style.font.size = Pt(11)
    style.font.color.rgb = INK

    sec = doc.sections[0]
    sec.left_margin = sec.right_margin = Inches(1.0)
    sec.top_margin = sec.bottom_margin = Inches(1.0)
    return doc


def add_page_numbers(doc):
    """Word computes the number at open time; we insert the field code."""
    for section in doc.sections:
        p = section.footer.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run()
        for instr in ("begin", "PAGE", "end"):
            el = OxmlElement("w:fldChar" if instr != "PAGE" else "w:instrText")
            if instr == "PAGE":
                el.set(qn("xml:space"), "preserve")
                el.text = " PAGE "
            else:
                el.set(qn("w:fldCharType"), instr)
            run._r.append(el)
        run.font.size = Pt(9)
        run.font.color.rgb = MUTED


def title_page(doc, title, subtitle, rows):
    for _ in range(4):
        doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(title)
    r.bold, r.font.size, r.font.color.rgb = True, Pt(30), BLUE
    r.font.name = BODY_FONT

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(subtitle)
    r.font.size, r.font.color.rgb, r.italic = Pt(14), MUTED, True
    r.font.name = BODY_FONT

    doc.add_paragraph()
    doc.add_paragraph()
    add_table(doc, rows)
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


def toc_placeholder(doc):
    # Deliberately NOT a Heading style: a real heading here would make the
    # contents page list itself as its own first entry.
    h = doc.add_paragraph()
    h.paragraph_format.space_after = Pt(8)
    add_inline(h, "Table of Contents", size=18, colour=BLUE, bold_all=True)
    p = doc.add_paragraph()
    add_inline(
        p,
        "*In Word: References → Table of Contents → Automatic Table 1. "
        "The headings in this document are real Word heading styles, so it will "
        "populate itself.*",
        size=10, colour=MUTED,
    )
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


# ------------------------------------------------------------------- build

def strip_front_matter(md: str) -> str:
    """Drop the Markdown title block; the .docx gets a real title page."""
    lines = md.splitlines()
    out, skipping = [], True
    for i, line in enumerate(lines):
        if skipping:
            if line.startswith("## Declaration") or line.startswith("## Executive Summary"):
                skipping = False
                out.append(line)
            continue
        out.append(line)
    md = "\n".join(out) if out else md
    # Declaration and Executive Summary are front matter, not subsections of
    # anything. In Markdown they sit at `##` because the document title is the
    # only `#`; in Word the title lives on its own page, so they are promoted
    # to Heading 1 and sit alongside the chapters in the contents.
    for name in ("## Declaration", "## Executive Summary"):
        md = md.replace(name, name[1:], 1)
    return md


def build_report():
    md = (HERE / "PROJECT_REPORT.md").read_text(encoding="utf-8")
    doc = new_document()
    title_page(
        doc,
        "ResearchForge",
        "An AI Research Paper Assistant",
        [
            ["Field", "Detail"],
            ["Project title", "ResearchForge: An AI-Powered Research Paper Assistant"],
            ["Course", "BIT 4543 — Artificial Intelligence"],
            ["Project number", "17"],
            ["Group members", "[GROUP MEMBER 1 — FULL NAME & STUDENT ID]\n"
                              "[GROUP MEMBER 2 — FULL NAME & STUDENT ID]\n"
                              "[GROUP MEMBER 3 — FULL NAME & STUDENT ID]"],
            ["Lecturer", "Azuan Nazeer"],
            ["Submission date", "[SUBMISSION DATE]"],
            ["Live system", "https://researchforge.rukon.dev"],
            ["Repository", "https://github.com/tirukon015/researchforge"],
        ],
    )
    toc_placeholder(doc)
    render(doc, strip_front_matter(md))
    add_page_numbers(doc)
    path = OUT / "ResearchForge_Report.docx"
    doc.save(path)
    return path


def build_plain(source: str, out_name: str, title: str, subtitle: str):
    md = (HERE / source).read_text(encoding="utf-8")
    doc = new_document()
    h = doc.add_heading(level=1)
    for r in h.runs:
        r.text = ""
    add_inline(h, title, size=22, colour=BLUE, bold_all=True)
    p = doc.add_paragraph()
    add_inline(p, subtitle, size=11, colour=MUTED)
    doc.add_paragraph()
    render(doc, md, page_break_on_h1=False)
    add_page_numbers(doc)
    path = OUT / out_name
    doc.save(path)
    return path


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    made = [
        build_report(),
        build_plain("SPEAKING_SCRIPT.md", "ResearchForge_Speaking_Script.docx",
                    "Speaking Script", "BIT 4543 · Project #17 · 20-minute presentation"),
        build_plain("EVIDENCE_PACK.md", "ResearchForge_Evidence_Pack.docx",
                    "Evidence Pack", "BIT 4543 · Project #17"),
        build_plain("POSTER.md", "ResearchForge_Poster_Spec.docx",
                    "Poster Specification", "BIT 4543 · Project #17 · A1 portrait"),
        build_plain("DIAGRAMS.md", "ResearchForge_Diagrams.docx", "Diagrams",
                    "BIT 4543 · Project #17 — Mermaid source. Word cannot draw "
                    "these; render each block at mermaid.live and paste the "
                    "image above its source, or keep the source as an appendix."),
    ]
    for p in made:
        print(f"  {p.name:42} {p.stat().st_size:>9,} bytes")

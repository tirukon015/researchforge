"""Build ResearchForge_Final_Speaking_Script.docx.

    python docs/report/build_speaking_script.py

A slide-by-slide script for the fifteen-slide deck, timed to about twenty
minutes. Every figure spoken aloud matches the deck and the final report.

FORMATTED TO BE READ, NOT SUBMITTED
-----------------------------------
The report uses Times New Roman 11 pt, justified. A script read at a lectern
under pressure needs the opposite: a sans-serif face, a larger size, ragged
right so the eye can track lines, and each slide kept whole on one page so a
page turn never lands mid-sentence.
"""

from __future__ import annotations

import pathlib

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "submission"

FONT = "Calibri"
INK = RGBColor(0x11, 0x11, 0x11)
BLUE = RGBColor(0x1E, 0x40, 0xAF)
ACCENT = RGBColor(0x25, 0x63, 0xEB)
GREY = RGBColor(0x60, 0x6A, 0x78)

# (number, title, minutes:seconds, running total, on-screen cue, speech, transition)
SLIDES = [
(1, "Title", "0:30", "0:30",
 "Title slide - ResearchForge, BIT4543, live URL.",
 ["Good morning. We are presenting ResearchForge, an AI Research Paper Assistant, "
  "for BIT4543 Artificial Intelligence. Our project area is document intelligence.",
  "The system is deployed and publicly reachable at researchforge dot rukon dot dev, "
  "so everything you see today runs on the live system rather than a demo build.",
  "I will start with why we built it."],
 "So - why does this problem need solving?"),

(2, "Background and motivation", "1:00", "1:30",
 "Six motivation points on the left, THE FIRST PASS card on the right.",
 ["Researchers work with large volumes of academic literature, and reading those "
  "papers manually is slow. A search on a narrow topic can return dozens of "
  "candidates.",
  "For every one of them, a researcher has to decide three things: what does this "
  "paper claim, what does it leave open, and how does it relate to everything else "
  "they have read. That is the card on the right, and we call it the first pass.",
  "It has to be repeated for every document. Key findings are hard to extract "
  "quickly, research gaps are difficult to identify, and preparing a literature "
  "review means comparing across sources.",
  "This is exactly the kind of work AI can assist with. ResearchForge assists this "
  "first pass, so effort is spent on the papers that actually matter."],
 "Let me state those problems more precisely."),

(3, "Problem statement", "1:05", "2:35",
 "Six problem cards, plus the chatbot warning underneath.",
 ["These are the six problems we set out to address. Analysis is slow. Key findings "
  "are buried in long, dense documents. Gaps are hidden and need close reading to "
  "find. Review effort requires comparison across sources. Re-analysing the same "
  "paper repeats API calls and costs money. And researchers lack a structured "
  "workflow.",
  "I want to draw your attention to the line at the bottom, because it shaped our "
  "whole design. A general chatbot will answer questions about a paper it has not "
  "read. It will produce a summary that sounds right and a citation that does not "
  "exist.",
  "For a researcher, an unreliable summary is worse than no summary, because a "
  "fabricated claim costs more time to detect than the summary ever saved. So "
  "groundedness had to be a design requirement, not something we hoped the model "
  "would do."],
 "That gave us ten objectives."),

(4, "Project objectives", "0:45", "3:20",
 "Ten numbered objectives in two columns.",
 ["We set ten objectives. The first seven are the visible product: upload papers, "
  "extract text from PDFs, generate summaries and key findings, identify research "
  "gaps, generate literature review content, support cross-paper review, and "
  "provide a usable interface.",
  "Objectives eight to ten are the engineering that makes the analysis trustworthy, "
  "private and affordable: secure accounts with private ownership, reducing "
  "duplicate AI processing through caching, and controlled AI routing with "
  "fallback.",
  "Those last three took most of our effort, and most of this presentation is "
  "about them."],
 "Here is what we built."),

(5, "Proposed solution: ResearchForge", "1:15", "4:35",
 "Pipeline across the top, four outputs beneath, dashboard screenshot on the right.",
 ["This is ResearchForge. A user uploads an academic paper as a PDF. We extract the "
  "text, the AI analysis runs, and the user receives structured insights: a summary "
  "with key findings, identified research gaps, literature review content, and all "
  "of it saved into their own research library.",
  "Cross-paper review sits on top of that. Several papers the user has already "
  "analysed can be reviewed together. The feature requires more than one paper, "
  "because a review across a single paper is simply that paper's own review "
  "content.",
  "The line I would emphasise is at the bottom left. Every generated section is "
  "constrained to the uploaded document. Where the paper does not support a "
  "section, the system reports insufficient evidence rather than generating text to "
  "fill the gap.",
  "That is a design decision, not a property we hope the model has, and I will show "
  "you how it is enforced in a few slides."],
 "First, how we went about building it."),

(6, "Methodology", "1:10", "5:45",
 "Seven-stage development flow, then five points on the approach.",
 ["Our methodology was incremental and milestone-based: requirements, system "
  "design, implementation, AI integration, database and authentication, testing, "
  "and production verification. Thirteen milestones, each ending with a test and a "
  "review before the next one began.",
  "The point I would make is that our design decisions were driven by measurement "
  "rather than assumption, and two of them changed the project.",
  "We did not build vector retrieval. When we measured real papers, they fitted "
  "inside the model's context window, so retrieval would have added a failure mode "
  "without solving a problem we actually had.",
  "And we moved data isolation into the database after a defect showed that "
  "filtering in the application had failed silently. I will come back to that "
  "defect, because it is the most instructive thing that happened to us.",
  "All six database migrations are additive only - no DROP, TRUNCATE or DELETE - so "
  "running a migration cannot destroy existing data."],
 "This is what we ended up with."),

(7, "System architecture", "1:35", "7:20",
 "Two-row architecture diagram; scaffolding note in the box at the bottom.",
 ["This is the architecture. A signed-in user uploads through the web interface, "
  "built in Next.js. The request carries their token to the FastAPI backend, which "
  "verifies it, extracts the PDF text, normalises it, and computes a SHA-256 hash "
  "of the content.",
  "That hash goes to the analysis cache. If we have already analysed this exact "
  "document, we return the stored result and make no model call at all.",
  "On a miss, the request goes to the AI provider router, which calls the primary "
  "provider - Groq, running Qwen 3.6 27B. If that fails in a way we allow to be "
  "retried, one fallback attempt is made on Anthropic's Claude Opus 5. The response "
  "is validated against a declared schema before anything is stored in Supabase "
  "PostgreSQL, and results come back filtered by the signed-in user.",
  "One thing I want to be explicit about, because it would be easy to overclaim. "
  "The box at the bottom: our repository does contain Jina embeddings, pgvector and "
  "a chunks table. They are prepared scaffolding and they are not called during "
  "analysis.",
  "The production pipeline is full-document grounded generation - we put the whole "
  "paper into the context. It is not RAG, and we do not describe it as RAG."],
 "Let me go one level deeper into the AI itself."),

(8, "AI model implementation", "1:40", "9:00",
 "Seven implementation points on the left; routing card and owner settings on the right.",
 ["The AI component is inference against hosted foundation models. We do not train "
  "a model, we do not fine-tune one, and we have no labelled training dataset.",
  "Groq running Qwen 3.6 27B is the configured primary. Anthropic Claude Opus 5 is "
  "the fallback. An analysis makes three separate structured passes - summary, gaps "
  "and literature review - because when we asked for all three in one prompt, the "
  "gap analysis came out noticeably weaker.",
  "The whole uploaded document is supplied as grounding context. The output is "
  "validated against a declared schema, and this is the important part: output that "
  "fails validation is discarded, never repaired. A partially valid analysis that "
  "we patched up would be an invented one, and that is exactly what we claim not to "
  "do.",
  "Every analysis records its provenance - which provider actually produced it, "
  "which model, whether the fallback was used, and whether it came from cache. That "
  "one field turns out to matter a great deal, as you will see.",
  "On the right is the routing control. The owner selects one global primary "
  "provider and the other enabled provider automatically becomes the fallback. "
  "Normal users cannot switch providers; there is no auto option. And only one "
  "fallback attempt is made, for allowed retryable failures. We do not retry "
  "indefinitely."],
 "Now let me show you the system in use."),

(9, "Key system features", "1:10", "10:10",
 "Live analysis screen on the left, seven features on the right.",
 ["This is the analysis screen from the live system. One upload produces the "
  "summary and key findings you can see here, plus the research gaps and the "
  "literature review content.",
  "On the right are the features as a set: PDF upload and text extraction; scanned "
  "documents rejected rather than analysed; structured summary and key findings; "
  "research gaps and the limitations the authors state; literature review content; "
  "cross-paper review across saved papers; and a private per-user library.",
  "Let me explain the second one, because it looks like a limitation and is "
  "actually a decision. If a PDF has no extractable text, we refuse it with an "
  "error rather than sending it to a model. A language model given an empty input "
  "will still produce fluent, confident output - it would just be about nothing. "
  "Refusing is the correct behaviour, even though it means we cannot process "
  "scanned papers."],
 "These two outputs are the heart of the project."),

(10, "Research gaps and literature review", "1:15", "11:25",
 "Two live screenshots: gaps on the left, cross-paper review on the right.",
 ["These two screens are the research intelligence the system produces, and they "
  "are live output, not mock-ups.",
  "On the left, research gaps and limitations. The gaps are drawn from what the "
  "paper itself supports - the limitations the authors state and the future work "
  "they propose - rather than speculation about the field in general.",
  "On the right, the cross-paper literature review. You can see it is a review of "
  "two papers. The content covers the major themes, comparisons with prior work, "
  "and future directions. Cross-paper review requires more than one paper by "
  "design.",
  "And again, where the paper does not support a section, the system reports "
  "insufficient evidence. I will be honest about one limitation of our evaluation "
  "here: across our ten analyses, that path was never triggered, because the papers "
  "we tested were complete, well-structured papers that genuinely contained "
  "findings and limitations. So that safeguard is verified by our unit tests, not "
  "by the evaluation."],
 "Everything you have seen is private to one account. Here is how."),

(11, "Authentication and data ownership", "1:40", "13:05",
 "Six auth points and the isolation card on the left; library and settings screenshots right.",
 ["Users sign in with email and password, or with Google. There is password reset "
  "and account settings, and every user has a private research library. No password "
  "is stored by our project - Supabase Auth holds them.",
  "But the guarantee is not the sign-in check. It is Row Level Security in "
  "PostgreSQL. Our backend talks to the database as the signed-in user, so the "
  "database resolves who is asking and applies the ownership policies itself.",
  "What that buys us is the property in bold: a forgotten filter in our code now "
  "returns nothing, rather than everything.",
  "Owner rights are resolved on the server from the authenticated identity, not in "
  "the browser.",
  "We verified this live, with two real accounts against the production database: "
  "twenty-six checks, zero failures. The check I would point to is the last one. We "
  "queried the database directly, using the key that ships inside the browser, "
  "bypassing our API completely. It returns zero rows.",
  "So isolation does not depend on our application code being correct - which "
  "matters, because our application code was previously wrong. An earlier version "
  "used a privileged key that bypasses those policies. Every feature worked, every "
  "test passed, and every policy was inert. We found it by signing in as a second "
  "account and looking."],
 "The last technical feature is the one that saves us money."),

(12, "Same-paper analysis cache", "1:30", "14:35",
 "Hash pipeline, cache lookup, then HIT and MISS branches with observed timings.",
 ["This is the same-paper analysis cache, and it is the feature I would most want "
  "to explain properly.",
  "After extraction we normalise the text and compute a SHA-256 hash of the "
  "content. That hash, together with an analysis version, is the key. Because it is "
  "derived from content, the same paper is recognised whatever the file is called.",
  "On a hit, we reuse the stored analysis, create this user's own private record, "
  "and display the result with zero AI calls. We observed 3.2 seconds for the same "
  "user, and 2.7 seconds for a different user.",
  "On a miss, we run the analysis, validate the response, then store both the "
  "analysis and the cache entry. Only successful, validated analyses are cached - "
  "failed, rate-limited or malformed results never are. That took 32.4 seconds with "
  "three AI calls.",
  "The important qualification is at the bottom. This cache is global internal "
  "infrastructure. It is not a shared library. If another user uploads the same "
  "paper, they still get their own private paper and analysis records, the original "
  "uploader is never revealed, and Row Level Security still applies. What the cache "
  "saves is a duplicate AI call - not a user's privacy."],
 "So how thoroughly did we test all of this?"),

(13, "Testing and evaluation", "1:25", "16:00",
 "Four headline numbers, then eight testing categories and two honest notes.",
 ["We have 522 backend tests and 16 frontend tests passing, 26 live isolation "
  "checks passed, and zero failing tests. These were re-verified against the "
  "current repository for this presentation, not carried over from an earlier "
  "draft.",
  "Our unit tests run against fakes, so the whole suite runs offline, costs "
  "nothing, and gives the same answer every time.",
  "On top of that: integration and API testing against the deployed system, "
  "authentication and session testing, user ownership and Row Level Security "
  "testing, AI provider and fallback testing, cache testing with four independent "
  "signals, and responsive testing on a real handset. Ruff, TypeScript and the "
  "production build are all clean, across fifteen routes.",
  "Two honest notes at the bottom. Five further tests call live providers and are "
  "skipped by design, because they cost tokens - they are opt-in.",
  "And we claim no model accuracy value. Accuracy, precision and recall need "
  "labelled ground truth, and there is no labelled benchmark for the correct "
  "research gaps in a given paper. Reporting a percentage there would be "
  "fabrication dressed up as rigour, so we report what we could actually measure "
  "instead."],
 "Which brings me to our results - including one we did not expect."),

(14, "Results and achievements", "2:00", "18:00",
 "Cache timings on the left; PROVIDER FINDING card on the right.",
 ["These are our results, and I want to be careful with the wording: these are what "
  "we observed in the tested scenarios. They are not guarantees.",
  "A cache miss took 32.4 seconds and three AI calls. The same paper again, same "
  "user, returned in 3.2 seconds with no AI calls - and 2.7 seconds for a "
  "different user. A repeat costs about a tenth of the time and no tokens, while "
  "each user still keeps a separate private record.",
  "Now the finding on the right, which is the most interesting result we got - and "
  "it is a negative one.",
  "Under the owner's configuration, all five evaluation papers completed "
  "successfully. But every single one was produced by the fallback provider. Not "
  "one was produced by the primary.",
  "The reason is that at its free service tier, the primary provider allows 7,000 "
  "input tokens per minute, while our papers required between 7,920 and 20,362 "
  "tokens in a single request. Even the shortest paper is over the limit - and "
  "because that limit applies to a single request, waiting does not help.",
  "So the fallback worked exactly as designed. And in working perfectly, it "
  "completely concealed that the primary provider was unusable. Every analysis "
  "succeeded, the interface showed no error, and a user would have noticed nothing.",
  "We only found it because every analysis records which provider actually produced "
  "it, and because we grouped our results by that record rather than by what we had "
  "configured. Had we done the obvious thing, we would have reported that both "
  "providers performed identically - while measuring the same one twice."],
 "Let me close."),

(15, "Conclusion and future work", "1:35", "19:35",
 "DELIVERED and FUTURE WORK columns, live URL at the foot.",
 ["To conclude. ResearchForge provides an AI-assisted workflow for analysing "
  "academic research papers and extracting structured research insights.",
  "What we delivered: upload, extraction and AI analysis; research gaps and "
  "literature review; cross-paper review; authentication with per-user ownership; "
  "provider routing with one fallback; and the same-paper analysis cache. All of it "
  "deployed and tested.",
  "For future work - and these are not implemented - production vector retrieval, "
  "which is where RAG would properly belong; stronger retrieval and ranking; "
  "citation-aware evidence linking, so each statement points to the passage that "
  "supports it; a larger benchmark with human evaluation; document versioning and "
  "multilingual support; and richer research comparison.",
  "The benchmark is the one that matters most. It is the only way to turn 'the "
  "system produced nine gaps' into 'the system found the gaps that mattered'.",
  "If I can leave you with one thing, it is this. The most valuable results in this "
  "project came from checking what the system actually did, rather than trusting "
  "what the code implied it would do. A security policy that was correct but "
  "inert. A fallback that hid a dead provider. Neither was visible until we went "
  "looking.",
  "The system is live at researchforge dot rukon dot dev. Thank you - we are happy "
  "to take questions."],
 None),
]

QA = [
 ("Is this just a wrapper around an AI model?",
  "The generation is inference against a hosted model, and we say so plainly. What "
  "makes it a system rather than a wrapper is everything around that call: "
  "schema-constrained output that is discarded when it does not conform, "
  "database-enforced isolation, content-addressed caching, and per-analysis "
  "provenance. That last one is what let us discover a dead provider that every "
  "other signal said was fine."),
 ("Why is there no RAG? You have the embedding code in your repository.",
  "Because measurement said it was unnecessary. Every paper we tested fitted in a "
  "single context window with no truncation. Retrieval would have added a failure "
  "mode - a wrong retrieval silently degrades the answer - to solve a problem we "
  "did not have. The scaffolding is unused, and we label it as unused so it cannot "
  "be mistaken for a feature. Production retrieval is our first item of future "
  "work."),
 ("Why not just retry Groq, or send it smaller chunks?",
  "Retrying does not help, because it is a single request that exceeds the "
  "per-minute budget, not a rate we are exceeding. Chunking to fit under 7,000 "
  "tokens would work mechanically, but then the two providers would be doing "
  "different tasks - one reading the whole paper, one reading fragments - so the "
  "comparison would be meaningless. We chose to report the honest negative."),
 ("How do you know the summaries are any good?",
  "We do not, and that is the largest limitation of our evaluation. We measured "
  "quantity, latency and structural validity. Quality needs expert-annotated ground "
  "truth, and that is our top recommendation for future work."),
 ("Is a five-second window after sign-out a security hole?",
  "It is a real cost and we document it rather than hide it. We cache token "
  "verifications for five seconds to avoid contacting the auth service on every "
  "request; we measured the actual window at about six seconds. If it is judged "
  "unacceptable, the fix is a short-lived revocation list. The previous value was "
  "thirty seconds - we reduced it after a live test showed sign-out appeared not to "
  "work."),
 ("Does the cache let one user see another user's data?",
  "No. The cache stores the analysis of a document, keyed by a hash of its content. "
  "It holds no user identity at all, and the table has Row Level Security enabled "
  "with no policy, so no user request can reach it - only our backend can. Each "
  "user still gets their own private paper and analysis records, and we verified in "
  "the live test that nothing identifying the first uploader appears in the second "
  "user's response."),
 ("What would you do differently?",
  "Record provenance first. Everything we learned from the evaluation came from "
  "that one field. If we had added it later, we would have shipped a report saying "
  "both providers worked."),
 ("Isn't this helping students avoid reading?",
  "It can be misused, and no design prevents that. What the design does is tie every "
  "claim to the source document and refuse to invent when evidence is missing, which "
  "makes the output checkable against the paper. Our position is that it is an "
  "assistant for reading, not a replacement for it."),
]


def shade(par, hex_colour):
    el = OxmlElement("w:shd")
    el.set(qn("w:val"), "clear")
    el.set(qn("w:fill"), hex_colour)
    par._p.get_or_add_pPr().append(el)


def field(par, instr, placeholder=""):
    r = par.add_run()._r
    b = OxmlElement("w:fldChar"); b.set(qn("w:fldCharType"), "begin"); r.append(b)
    r2 = par.add_run()._r
    it = OxmlElement("w:instrText"); it.set(qn("xml:space"), "preserve")
    it.text = instr; r2.append(it)
    r3 = par.add_run()._r
    sep = OxmlElement("w:fldChar"); sep.set(qn("w:fldCharType"), "separate"); r3.append(sep)
    if placeholder:
        par.add_run(placeholder)
    r4 = par.add_run()._r
    e = OxmlElement("w:fldChar"); e.set(qn("w:fldCharType"), "end"); r4.append(e)


def para(doc, text, *, size=12, colour=INK, bold=False, italic=False,
         before=0, after=6, spacing=1.15, indent=0.0, keep=False,
         align=WD_ALIGN_PARAGRAPH.LEFT):
    p = doc.add_paragraph()
    p.alignment = align
    pf = p.paragraph_format
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    pf.line_spacing = spacing
    pf.keep_with_next = keep
    if indent:
        pf.left_indent = Cm(indent)
    r = p.add_run(text)
    r.font.name, r.font.size, r.bold, r.italic = FONT, Pt(size), bold, italic
    r.font.color.rgb = colour
    return p


def build():
    doc = Document()
    st = doc.styles["Normal"]
    st.font.name, st.font.size, st.font.color.rgb = FONT, Pt(12), INK
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
    sec.left_margin = sec.right_margin = Cm(2.2)
    sec.top_margin = sec.bottom_margin = Cm(2.0)

    f = sec.footer.paragraphs[0]
    f.alignment = WD_ALIGN_PARAGRAPH.CENTER
    field(f, " PAGE ", "1")
    for r in f.runs:
        r.font.name, r.font.size = FONT, Pt(9)
        r.font.color.rgb = GREY

    # ---- cover -------------------------------------------------------------
    para(doc, "ResearchForge - Presentation Speaking Script", size=20, colour=BLUE,
         bold=True, after=2)
    para(doc, "AI Research Paper Assistant  |  BIT4543 Artificial Intelligence",
         size=12, colour=GREY, after=14)
    para(doc, "Fifteen slides, timed to approximately 20 minutes. Every figure spoken "
              "aloud matches the slide deck and the final report.", size=11,
         colour=INK, after=14)

    para(doc, "TIMING", size=12, colour=BLUE, bold=True, after=4, keep=True)
    t = doc.add_table(rows=0, cols=4)
    t.style = "Table Grid"
    for row in ([("Slides", "Section", "Time", "Running")] +
                [("1", "Title", "0:30", "0:30"),
                 ("2 - 4", "Motivation, problem, objectives", "2:50", "3:20"),
                 ("5 - 8", "Solution, methodology, architecture, AI", "5:40", "9:00"),
                 ("9 - 12", "Features, gaps, security, cache", "5:35", "14:35"),
                 ("13 - 14", "Testing and results", "3:25", "18:00"),
                 ("15", "Conclusion", "1:35", "19:35")]):
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            pp = cells[i].paragraphs[0]
            pp.paragraph_format.space_before = Pt(2)
            pp.paragraph_format.space_after = Pt(2)
            rr = pp.add_run(v)
            rr.font.name, rr.font.size = FONT, Pt(10.5)
            rr.bold = (row[0] == "Slides")
            rr.font.color.rgb = INK
    para(doc, "", size=6, after=2)
    para(doc, "Timings are computed from this script at 135 words per minute, leaving about 25 seconds of buffer inside 20 minutes.",
         size=10.5, colour=GREY, after=14)

    para(doc, "SUGGESTED SPEAKER SPLIT (three presenters)", size=12, colour=BLUE,
         bold=True, after=4, keep=True)
    for who, what, mins in (("Presenter 1", "Slides 1 - 6  (title through methodology)", "5:45"),
                            ("Presenter 2", "Slides 7 - 11  (architecture through security)", "7:20"),
                            ("Presenter 3", "Slides 12 - 15  (cache through conclusion)", "6:30")):
        para(doc, f"{who}  -  {what}  -  {mins}", size=11, after=3, indent=0.5)
    para(doc, "Hand over between slides, not mid-slide. Whoever speaks last should "
              "take the first question.", size=10.5, colour=GREY, after=14)

    para(doc, "BEFORE YOU START", size=12, colour=BLUE, bold=True, after=4, keep=True)
    for item in ("Install the Audiowide and Karla fonts, or present from a machine "
                 "that has them, so the deck renders as designed.",
                 "Open the live site in a second tab, signed in, with at least two "
                 "papers already analysed.",
                 "Do not run a fresh analysis live - it takes about a minute and a "
                 "half. Re-uploading an already-analysed paper returns in about "
                 "three seconds and demonstrates the cache well.",
                 "Do not switch AI providers live. The primary provider cannot "
                 "process a full paper at the free tier, which is fine to describe "
                 "but a bad thing to stake a demo on."):
        para(doc, "•  " + item, size=11, after=3, indent=0.5)

    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    # ---- the script --------------------------------------------------------
    for n, title, mins, running, cue, speech, transition in SLIDES:
        head = doc.add_paragraph()
        head.paragraph_format.space_before = Pt(4)
        head.paragraph_format.space_after = Pt(4)
        head.paragraph_format.keep_with_next = True
        shade(head, "E8EEF9")
        r = head.add_run(f"  SLIDE {n}  -  {title}")
        r.font.name, r.font.size, r.bold = FONT, Pt(13), True
        r.font.color.rgb = BLUE
        r2 = head.add_run(f"      {mins}   (running {running})  ")
        r2.font.name, r2.font.size = FONT, Pt(10.5)
        r2.font.color.rgb = GREY

        para(doc, "ON SCREEN:  " + cue, size=10, colour=GREY, italic=True,
             after=6, keep=True)
        for i, block in enumerate(speech):
            para(doc, block, size=12.5, after=8, spacing=1.25,
                 keep=(i < len(speech) - 1))
        if transition:
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(16)
            p.paragraph_format.left_indent = Cm(0.4)
            rr = p.add_run("→  " + transition)
            rr.font.name, rr.font.size, rr.italic = FONT, Pt(11), True
            rr.font.color.rgb = ACCENT
        else:
            para(doc, "", size=8, after=10)

    # ---- Q&A ---------------------------------------------------------------
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
    para(doc, "Anticipated questions", size=18, colour=BLUE, bold=True, after=4)
    para(doc, "Answer briefly and concede real limits. The strongest position here is "
              "accuracy, not defensiveness.", size=11, colour=GREY, after=12)
    for q, a in QA:
        para(doc, "Q.  " + q, size=12, colour=BLUE, bold=True, after=3, keep=True)
        para(doc, "A.  " + a, size=11.5, after=11, spacing=1.2, indent=0.5)

    para(doc, "If you are running over time", size=14, colour=BLUE, bold=True,
         before=8, after=4)
    for item in ("Compress slide 6 to one sentence: incremental milestones, decisions "
                 "driven by measurement.",
                 "Cut the second half of slide 9 - the scanned-document explanation.",
                 "Never cut slides 12 and 14. The cache and the provider finding are "
                 "the strongest technical content in the presentation."):
        para(doc, "•  " + item, size=11, after=3, indent=0.5)

    OUT.mkdir(exist_ok=True)
    path = OUT / "ResearchForge_Final_Speaking_Script.docx"
    doc.save(path)
    words = sum(len(b.split()) for *_, speech, _ in
                [(a, b, c, d, e, f, g) for a, b, c, d, e, f, g in SLIDES] for b in speech)
    return path, words


if __name__ == "__main__":
    p, w = build()
    print(f"  {p.name}")
    print(f"  {p.stat().st_size:,} bytes")
    print(f"  spoken words: {w:,}  (~{w/135:.1f} min at 135 wpm)")

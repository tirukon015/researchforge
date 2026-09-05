# Submission files — what to do before handing in

These files are **generated**. The Markdown in `docs/report/` is the source of
truth, so edit a fact there and rebuild — a change made only in the .docx is
lost on the next build.

```bash
python docs/report/build_deliverables.py   # the five .docx files
python docs/report/build_deck.py           # the 14-slide .pptx
python docs/report/build_poster.py         # the A1 poster .pptx
```

## The five required submission components

| # | Required | File | Status |
|---|---|---|---|
| 1 | Project Report, Ch 1–7, 8,000–12,000 words | `ResearchForge_Report.docx` | 10,535 words |
| 2 | System / App with interface + database | Live at researchforge.rukon.dev | Deployed |
| 3 | Slides, minimum 10 | `ResearchForge_Slides.pptx` | 14 slides |
| 4 | Presentation, 20 minutes | `ResearchForge_Speaking_Script.docx` | Timed to 20:00 |
| 5 | Poster / Infographic | `ResearchForge_Poster_A1.pptx` | A1 portrait, print-ready |

Supporting documents: `ResearchForge_Evidence_Pack.docx` (requirements
traceability, dataset, 22 test cases, assessment-component audit) and
`ResearchForge_Diagrams.docx` (Mermaid source for the figures).

The report follows the lecturer's structure exactly — all 34 required sections,
including Appendix A (Project Schedule), B (Source Code), C (Dataset Samples)
and D (User Manual).

## Four things still to do by hand

1. **Fill in the placeholders.** Group member names and student IDs, and the
   submission date — on the report's title page and on the poster and slide 1.
   They are the only placeholders left.

2. **Generate the Table of Contents.** Open the report, click under "Table of
   Contents", then **References → Table of Contents → Automatic Table 1**. The
   headings are real Word heading styles, so it populates and paginates itself.

3. **Add screenshots.** Twelve are listed in the Evidence Pack §8, with what
   each must show. Section 4.5 and Appendix D of the report are where they go.

4. **Render the diagrams.** Word cannot draw Mermaid. Paste each block from
   `ResearchForge_Diagrams.docx` (or the fenced blocks in the report's §4.2,
   §4.3, §4.4 and Appendix A) into <https://mermaid.live>, export the PNG, and
   place it above its source. Figures 4.1–4.3 and A.1 are referenced by number
   in the text.

## Two things worth knowing before you present

**The central finding is a negative one.** The planned Claude-versus-Groq
comparison could not be completed: Groq's free tier permits 7,000 input tokens
per minute, and every paper tested needed 7,920–20,362 in a single request.
Groq produced nothing, yet every paper was analysed, because the fallback
quietly handed all of them to Claude. This is the strongest part of the
submission, not a weakness in it — slides 10 and 11 carry it, and the speaking
script has prepared answers for the obvious challenges.

**One outstanding repository action.** The report, evaluation artefacts and
these deliverables have not yet been committed and pushed to
`github.com/tirukon015/researchforge`. Repository quality is worth 10 marks, so
do this before submitting.

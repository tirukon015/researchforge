# ResearchForge — Poster Specification

**AI Research Paper Assistant · BIT4543 Artificial Intelligence**
Format: **A1 portrait**, 594 × 841 mm. Readable from about 1.5 metres.

Every figure below is verified project evidence. Nothing is illustrative, and
nothing here should be changed without changing the source it came from.

Build this in PowerPoint (set Design → Slide Size → Custom → 59.4 × 84.1 cm),
Canva, or Illustrator. Copy is given verbatim — paste it rather than rewriting,
so the poster and the report cannot disagree.

---

## Design system

Reuse the application's own colours so the poster and the product look like one
thing.

| Role | Hex | Use |
|---|---|---|
| Primary | `#2563EB` | Section headings, rules, key figures |
| Primary dark | `#1E40AF` | Title band and conclusion band background |
| Ink | `#0F172A` | Body text |
| Muted | `#64748B` | Captions and labels |
| Surface | `#FFFFFF` | Panel backgrounds |
| Page | `#F8FAFC` | Poster background |
| Accent — finding | `#B45309` | Band 4 only |
| Accent — verified | `#047857` | Band 5 left panel only |

**Type.** One humanist sans throughout — Inter, Source Sans 3 or Calibri.

| Element | Size |
|---|---|
| Poster title | 96 pt |
| Section headings | 44 pt |
| Sub-headings | 30 pt |
| Body | 24 pt |
| Captions | 18 pt |
| Hero statistics | 130 pt |

**One rule that matters.** The two accent colours appear **only** where
specified. A poster where everything is highlighted highlights nothing.

---

## Layout — six horizontal bands

```
┌──────────────────────────────────────────────────────────┐
│ BAND 1 · TITLE                                     (10%) │
├───────────────────────────────┬──────────────────────────┤
│ BAND 2 · PROBLEM      (7 col) │ OBJECTIVES      (5 col)  │
│                                                    (14%) │
├──────────────────────────────────────────────────────────┤
│ BAND 3 · HOW IT WORKS                              (20%) │
├──────────────────────────────────────────────────────────┤
│ BAND 4 · THE FINDING   ← visual centre             (26%) │
├───────────────────────────────┬──────────────────────────┤
│ BAND 5 · VERIFIED             │ LIMITATIONS        (20%) │
├──────────────────────────────────────────────────────────┤
│ BAND 6 · CONCLUSION + QR                           (10%) │
└──────────────────────────────────────────────────────────┘
```

Band 4 is the largest deliberately. It is the part a passer-by should read even
if they read nothing else.

---

## BAND 1 — Title

*Full width. Background `#1E40AF`, white text, centred.*

> # ResearchForge
> ### An AI Research Paper Assistant — grounded, isolated, and honestly measured
>
> `[GROUP MEMBER NAMES & STUDENT IDs]`
> BIT4543 Artificial Intelligence · Lecturer: Encik Azuan Nazeer
> **researchforge.rukon.dev**

---

## BAND 2 — Problem (left, 7 col) and Objectives (right, 5 col)

### Left panel — THE PROBLEM

> Researchers read papers in order to decide which papers to read. For every
> result in a literature search: what does it claim, what does it leave open,
> how does it relate to the rest?

*Amber left rule on this line only:*

> A general chatbot will answer questions about a paper it has never read.
> **An unreliable summary is worse than none: a fabricated claim costs more time
> to detect than the summary ever saved.**

### Right panel — TEN OBJECTIVES

1. Upload research papers
2. Extract text from PDF papers
3. Generate summaries and key findings
4. Identify research gaps
5. Generate literature review content
6. Support cross-paper literature review
7. Provide a usable assistant interface
8. Secure accounts and private ownership
9. Reduce duplicate AI processing
10. Controlled AI routing and fallback

*Caption under the list:*
> Objectives 8 to 10 are the engineering that makes the analysis trustworthy,
> private and affordable.

---

## BAND 3 — How it works

*Two panels side by side on a white surface.*

### Left panel — Architecture

```
User → Web interface (Next.js)
          ↓
     FastAPI backend  →  extract, normalise, SHA-256 hash
          ↓
     Analysis cache  ──hit──────────────┐
          ↓ miss                        │
     AI provider router                 │
          ↓                             ↓
   Primary: Groq qwen3.6-27b      Supabase PostgreSQL
   Fallback: Anthropic opus-5      Row Level Security
          ↓                             ↑
     Schema validation ────────────────┘
```

*Caption:*
> Next.js 16 · FastAPI · Python 3.14 · Supabase PostgreSQL · 15 routes ·
> 538 automated tests passing

### Right panel — Grounding

| Layer | Mechanism |
|---|---|
| Prompt | Every claim traceable to the supplied text |
| Schema | Output constrained to a declared model |
| Validation | Non-conforming output **discarded, not repaired** |
| Escape | Must report *insufficient evidence* |

*Blue left rule on this line:*
> **Not RAG.** The production pipeline is full-document grounded generation.
> Jina embeddings, pgvector and the chunks table exist in the repository as
> prepared scaffolding and are **not called during analysis**.

---

## BAND 4 — The finding

*Background `#FDF6EC`, 2 pt border `#B45309`. This band is the centre of the
poster.*

### Headline — 60 pt, centred, `#B45309`

> ## A redundancy mechanism hides the failure it compensates for.

### Left — the result

| Pass | Configuration | Completed | By the configured provider |
|---|---|---|---|
| A | Anthropic primary | 5/5 | 5/5 |
| B | **Groq primary** | 5/5 | **0/5** |
| C | Groq only | **0/5** | 0/5 |

*Caption:* 15 runs · 10 analyses produced · all 10 by the fallback provider.

### Centre — three hero statistics

*130 pt figures in `#B45309`, 21 pt captions beneath.*

| **7,000** | **7,920** | **0/5** |
|---|---|---|
| provider free-tier limit, input tokens per minute | tokens needed by the **smallest** paper, 6 pages | papers the primary provider could analyse |

### Right — the evidence

*Monospace, on a `#F3E8D4` panel:*

```
Request too large for model `qwen/qwen3.6-27b`
on input tokens per minute (ITPM):
Limit 7000, Requested 7920
```

| Paper | Pages | Tokens needed | Over |
|---|---|---|---|
| SciBERT | 6 | 7,920 | 1.1× |
| Attention | 15 | 11,745 | 1.7× |
| Factual Consistency | 13 | 12,661 | 1.8× |
| BERT | 16 | 18,498 | 2.6× |
| RAG | 19 | 20,362 | 2.9× |

### Bottom strip of Band 4 — why it matters

*Amber left rule, 23 pt:*

> One provider was completely non-functional. **Every analysis succeeded.** The
> interface showed no error, and a user would have noticed nothing.
>
> It was detectable only because every analysis records which provider
> **actually** produced it — and because results were grouped by that record
> rather than by configuration.
>
> **Grouping by configuration would have reported that both providers performed
> identically, while measuring the same one twice.**

---

## BAND 5 — Verified (left) and Limitations (right)

### Left panel — VERIFIED

*Background `#ECFAF4`, border `#047857`.*

> ### 26 / 0
> live isolation checks passed / failed

- A new user's library is empty
- User B cannot read, delete or review User A's paper — **404**, so existence is
  not disclosed
- **Querying the database directly with the browser's own key returns ZERO
  rows** — isolation is a database guarantee, not application behaviour

| Cache | Latency | Model called |
|---|---|---|
| First upload | 32.4 s | yes, 3 AI calls |
| Repeat, same user | 3.2 s | **no** |
| Repeat, different user | 2.7 s | **no** |

*Caption:*
> The reported processing time stays the original run's figure on a hit — the
> signal a merely fast response could not fake.

### Right panel — HONEST LIMITATIONS

- **No ground truth.** We measured how much the system produced, not whether it
  is right. A system inventing nine plausible gaps would score identically.
- **Effectively single-provider.** Redundancy is architectural, not actual.
- **Insufficient-evidence path never triggered** — 0 of 10 runs.
- **No accuracy value is claimed.** There is no labelled benchmark for "the
  correct research gaps in this paper".
- 5 papers, one discipline, single runs, evaluated by its own authors.
- ~100 s per new analysis · no OCR · 5 s sign-out window.

---

## BAND 6 — Conclusion

*Full width. Background `#1E40AF`, white text. QR code on the right.*

> A deployed system meeting all five requirements — grounding enforced
> structurally, isolation enforced by PostgreSQL, provenance recorded per
> analysis, and duplicate inference avoided.
>
> **Next:** ground-truth evaluation with expert-annotated gaps · a second
> provider that can accept a full paper · a deliberate test of the
> insufficient-evidence path.
>
> *The most valuable results came from checking what the system actually did,
> rather than trusting what the code implied it would do.*

*Right, beside a QR code to the live site:*
> **Live system**
> researchforge.rukon.dev

---

## Production checklist

- [ ] Group member names and student IDs filled in (Band 1)
- [ ] QR code generated for `https://researchforge.rukon.dev` and tested from a
      phone at poster distance
- [ ] Body text no smaller than 24 pt; hero figures 130 pt
- [ ] Amber `#B45309` used **only** in Band 4; emerald `#047857` **only** in
      Band 5 left panel
- [ ] Architecture diagram redrawn as shapes, not pasted as a screenshot
- [ ] Every number cross-checked against `results/evaluation/summary.txt`
- [ ] No API key, token or credential anywhere on the poster
- [ ] A4 proof printed and read at arm's length before printing A1

---

## Where each number comes from

| Figure on the poster | Source |
|---|---|
| 538 automated tests, 15 routes | `pytest`, `vitest`, `next build` on the current repository |
| 26 / 0 isolation checks | `results/evaluation/isolation_test.txt` |
| 32.4 s / 3.2 s / 2.7 s | `results/evaluation/cache_test.txt` |
| 7,000 limit; 7,920–20,362 needed | `results/evaluation/groq_capacity.json` |
| Pass A / B / C completion | `results/evaluation/runs.json` |
| Corpus of five papers | `data/dataset_manifest.csv` |

If you change a number on the poster, change it in the report and the deck too —
they are checked against each other.

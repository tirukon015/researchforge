# ResearchForge — Presentation Slides

**BIT 4543 Artificial Intelligence · Project #17**
14 slides · designed for a 20-minute presentation
Speaking script: `SPEAKING_SCRIPT.md`

Every figure on these slides comes from `results/evaluation/`. Nothing is
illustrative.

---

## Slide 1 — Title

# ResearchForge
### An AI Research Paper Assistant

**BIT 4543 — Artificial Intelligence · Project #17**

Group members: `[NAMES & STUDENT IDs]`
Lecturer: Azuan Nazeer
`[SUBMISSION DATE]`

**Live:** researchforge.rukon.dev

> *Visual: the live dashboard screenshot, full-bleed behind a translucent panel.*

---

## Slide 2 — The Problem

### Researchers read to decide what to read

- A literature search returns **dozens** of candidates
- For each one: What does it claim? What does it leave open? How does it relate
  to the rest?
- This first pass is slow, manual, and repeated for **every** document

### And the obvious fix is dangerous

A general chatbot will answer questions about a paper it has not read.
A fabricated citation is **worse than no answer** — it costs more time to
detect than it saved.

> *Visual: left — a stack of 30 paper icons; right — a single quotation
> with a red "unverifiable" stamp.*

---

## Slide 3 — Objectives

| # | Objective |
|---|---|
| 1 | Summaries, research gaps, and literature reviews from uploaded papers |
| 2 | Grounding enforced **structurally**, not by instruction |
| 3 | Two AI providers, owner-selected, automatic fallback |
| 4 | Per-user isolation enforced by the **database** |
| 5 | The same paper analysed once, however many people upload it |
| 6 | Empirical evaluation on real open-access papers |

**Five university requirements:** upload · summarise · identify gaps ·
literature review · deliver a working application.

---

## Slide 4 — System Architecture

```
Browser ──► Next.js frontend  ─┐
                               ├── one Vercel project, shared origin
            FastAPI backend ◄──┘
                  │
      ┌───────────┼────────────┐
      ▼           ▼            ▼
   pypdf      Provider      Supabase
 extraction    router       PostgreSQL
                  │          + RLS
            ┌─────┴─────┐
            ▼           ▼
        Anthropic     Groq
         Claude    Qwen 3.6 27B
```

- **Next.js 16 / React 19 / TypeScript** — 12 routed pages
- **Python 3.14 / FastAPI / Pydantic** — 6,366 lines, 35 modules
- **Supabase PostgreSQL** — chosen specifically for Row Level Security

> *Visual: use the rendered architecture diagram from `DIAGRAMS.md` §2.*

---

## Slide 5 — The Analysis Pipeline

```
PDF ─► extract ─► hash (SHA-256) ─► cache? ─► 3 grounded passes ─► store
                       │               │
                  identity by      hit ⇒ 3.2s
                   CONTENT         miss ⇒ 32.4s
```

**Three separate passes, not one prompt:** summary · research gaps · literature
review. Asking for all three at once produced noticeably weaker gap analysis.

**A PDF with no extractable text is rejected (HTTP 422)** — never sent to a
model. A model given no text produces fluent output about nothing.

> *Visual: the pipeline diagram from `DIAGRAMS.md` §3.*

---

## Slide 6 — How Grounding Is Enforced

### Not by asking politely

| Layer | Mechanism |
|---|---|
| Prompt | Every claim must be traceable to the supplied text |
| Schema | Output constrained to a declared Pydantic model |
| Validation | Output that fails the schema is **discarded, not repaired** |
| Escape hatch | The model must say *insufficient evidence* rather than fill a gap |

> **A partially-valid analysis that we patched up would be an invented one.**
> That is exactly what the grounding claim forbids — so it is thrown away.

**Honest limit:** grounding reduces fabrication. It does not verify truth.

---

## Slide 7 — Data Isolation: the Bug That Taught the Most

### The first version was wrong, and every test passed

```python
# BEFORE — service-role key: designed to BYPASS Row Level Security
# The policies were present, correct, and completely inert.

# AFTER
"apikey":        anon_key,          # identifies the PROJECT
"Authorization": f"Bearer {token}"  # identifies the PERSON
```

Postgres now resolves `auth.uid()`, so **every** policy filters.

> **A forgotten filter now returns nothing instead of everything.**

**Found by:** signing in as a second real account and looking.
Not by any unit test — at the unit level, nothing was wrong.

---

## Slide 8 — Evaluation Design

**Corpus:** 5 real arXiv papers — Attention, BERT, RAG, SciBERT, Factual
Consistency. 6–19 pages, 23,767–69,097 characters. Unmodified.

### Three decisions that make the numbers mean something

1. **Group by the provider that ACTUALLY answered**, not the one configured
2. **Clear the cache between passes** — it is keyed by content, not provider
3. **Bypass Cloudflare** — it replaces error bodies with `error code: 502`

Each corresponds to a mistake actually made, and corrected.

| Pass | Configuration |
|---|---|
| A | Claude primary, both enabled |
| B | Groq primary, both enabled |
| C | Groq only, Claude switched **off** |

---

## Slide 9 — Results

| Pass | Configuration | Completed | **By the configured provider** |
|---|---|---|---|
| A | Claude primary | 5/5 | 5/5 |
| B | Groq primary | 5/5 | **0/5** |
| C | Groq only | **0/5** | 0/5 |

### Output produced (10 analyses, all by Claude)

| Measure | Median | Range |
|---|---|---|
| Processing time | 98.8 s | 72.6 – 115.2 s |
| Key findings | 8 | 6 – 11 |
| Research gaps | 9 | 7 – 10 |
| Review themes | 8 | 5 – 9 |

**The system completed every paper. It never once used the provider the owner
selected.**

---

## Slide 10 — Why Groq Produced Nothing

```
Request too large for model `qwen/qwen3.6-27b`
on input tokens per minute (ITPM): Limit 7000, Requested 7920
```

| Paper | Pages | Tokens needed | Limit | Over by |
|---|---|---|---|---|
| SciBERT | 6 | 7,920 | 7,000 | 1.1× |
| Attention | 15 | 11,745 | 7,000 | 1.7× |
| Factual Consistency | 13 | 12,661 | 7,000 | 1.8× |
| BERT | 16 | 18,498 | 7,000 | 2.6× |
| RAG | 19 | 20,362 | 7,000 | 2.9× |

**This is not a pacing problem.** A single 7,920-token request can never fit a
7,000-tokens-per-minute budget, no matter how long you wait.

**Even the 6-page paper is too big. At this tier, Groq cannot read a paper.**

---

## Slide 11 — The Finding That Matters

# A redundancy mechanism hides the failure it compensates for.

- One provider was **completely non-functional**
- Every analysis **succeeded**
- The interface showed **no error**
- A user would have noticed **nothing**

### It was detectable only because

1. Every analysis records which provider **actually** produced it
2. The evaluation grouped by that record — **not** by configuration

> Grouping by configuration — the obvious choice — would have reported
> *"both providers perform identically."*
> It would have been measuring Claude twice.

---

## Slide 12 — Verified: Isolation and Caching

### Live two-account isolation test — **26 passed, 0 failed**

- A new user's library is empty
- User B cannot read, delete, or review User A's paper (404 — existence is not
  disclosed)
- **PostgREST with the browser's own key returns ZERO rows**

That last check bypasses the API entirely. Isolation is a **database**
guarantee, not an application behaviour.

### Cache — verified by four independent signals

| Request | Latency | Model called |
|---|---|---|
| First upload | 32.4 s | yes |
| Same paper, same user | 3.2 s | **no** |
| Same paper, **different user** | 2.7 s | **no** |

`processing_time_ms` stays the *original* figure — the signal a fast response
cannot fake.

---

## Slide 13 — Honest Limitations

| Limitation | Why it matters |
|---|---|
| **No ground truth** | We count what the system produced, not whether it is *right* |
| **Effectively single-provider** | Redundancy is architectural, not actual |
| **Insufficient-evidence path never triggered** | 0/10 runs — the key safeguard is untested by this corpus |
| **5 papers, one discipline** | Nothing established outside arXiv cs.CL |
| **~100 s per new analysis** | A real usability barrier |
| **No OCR** | Scanned papers are rejected |
| **5-second sign-out window** | A revoked token works for ≤5 s (measured: 6.1 s) |

> Two of six objectives are only partially achieved — and in both cases
> because the evaluation **revealed** something, not because work was skipped.

---

## Slide 14 — Conclusion and Future Work

### Delivered

A deployed system meeting all five requirements, with grounding enforced
structurally, isolation enforced by PostgreSQL, and provenance recorded per
analysis.

### Next, in order of value

1. **Ground-truth evaluation** — expert-annotated gaps; the only way to turn
   "produced 9 gaps" into "found the right gaps"
2. **Restore real redundancy** — a second provider that can accept a full paper
3. **Deliberately trigger insufficient evidence** — test the safeguard
   Objective 2 rests on
4. Stream partial results · OCR · evaluate outside cs.CL

### The lesson

> The most valuable results came from checking what the system **actually did**,
> rather than trusting what the code implied it would do.

**researchforge.rukon.dev** · Questions?

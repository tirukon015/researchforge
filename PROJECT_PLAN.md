# PROJECT_PLAN.md
### ResearchForge — AI Research Paper Assistant (Gen AI)
**BIT4543 Artificial Intelligence — Project #17**

| | |
|---|---|
| **Status** | Milestone 1 — Environment & Foundations ✅ complete |
| **Last updated** | 2026-08-11 |
| **Nothing installed / no API connected / no RAG built yet** | ✅ intentional |

> **How to read this document.** Sections A–D define *what* we are building.
> Sections E–K define *how*. Sections L–P define *how we prove it works and
> ship it*. Sections Q–S define *the order of work and what can go wrong*.
> Items marked **[DECISION NEEDED]** require the project owner's approval
> before any code is written for them.

---

## A. Project Overview

### The problem
A researcher doing a literature review must read dozens of papers, extract the
key contributions of each, notice what *nobody* has studied yet, and synthesise
it all into a coherent written review. This takes weeks and is easy to do badly.

### The solution
A web application where a user uploads research papers and receives:
- a structured **summary** of each paper,
- an analysis of the **research gaps** across the collection,
- a draft **literature review** synthesising the papers,
- an interactive **question-answering** assistant grounded in the uploaded text.

### The key technical idea: RAG
The system uses **RAG — Retrieval-Augmented Generation**.

*In plain language:* a large language model (LLM) on its own will confidently
invent facts, which is fatal for academic work. RAG fixes this. Before the AI
answers anything, we **search the user's actual uploaded papers** for the most
relevant passages, and then we hand those passages to the AI with an
instruction like *"answer using only this text, and cite it."*

So the AI is never asked "what do you know about X?" It is asked "here are five
real paragraphs from the user's papers — summarise them and cite the source."
That is the difference between a plausible-sounding essay and a defensible
academic tool.

### What makes this portfolio-quality (not just a homework submission)
- Real retrieval with citations, not a thin wrapper around a chat API.
- An honest evaluation of AI output quality with real, reproducible numbers.
- Production concerns handled: security, cost control, deployment, tests.
- Clean documentation that a stranger can follow.

---

## B. University Requirements

The graded requirements, mapped to how the plan satisfies them.

| # | Requirement | How it is satisfied | Where |
|---|---|---|---|
| 1 | Allow users to upload research papers | PDF upload → text extraction → chunking → embedding → stored in Postgres | Milestone 3–4 |
| 2 | Generate summaries of research papers | Structured summary generation (problem, method, findings, limitations) with citations | Milestone 6 |
| 3 | Identify research gaps | Cross-paper analysis of stated limitations + "future work" sections, clustered into themes | Milestone 7 |
| 4 | Produce literature reviews | Multi-paper synthesis into a themed, cited review draft | Milestone 8 |
| 5 | Research Assistant Application | Deployed Next.js web app with upload, library, chat Q&A, and all above features | Milestone 9–11 |

**Traceability rule:** every requirement above must have at least one automated
test and one screenshot/demo in the final report.

---

## C. Core Features (must build)

| ID | Feature | Description |
|---|---|---|
| **F1** | Paper upload | Upload one or many PDFs. Validate type and size. Show progress and errors. |
| **F2** | Text extraction & chunking | Extract text from PDF, split into overlapping chunks, keep page/section metadata for citations. |
| **F3** | Embedding & indexing | Convert chunks to vectors, store in Postgres with pgvector for similarity search. |
| **F4** | Paper library | List uploaded papers with title, authors, year, status, and delete option. |
| **F5** | Paper summarisation | Structured per-paper summary: objective, method, dataset, findings, limitations, contribution. |
| **F6** | Research gap identification | Analyse across papers to surface under-explored areas, contradictions, and unmet needs. |
| **F7** | Literature review generation | Themed, synthesised, cited review draft across the selected papers. |
| **F8** | Grounded Q&A chat | Ask questions across the library; answers cite paper + page. Refuses when evidence is absent. |
| **F9** | Citations & provenance | Every AI claim links back to its source chunk. Non-negotiable. |
| **F10** | Export | Download summaries / review as Markdown or PDF. |

---

## D. Optional Enhancement Features (nice to have)

Build only after every core feature is complete and tested.

| ID | Feature | Value |
|---|---|---|
| E1 | Paper comparison table | Side-by-side matrix of methods, datasets, metrics. Very impressive in a demo. |
| E2 | arXiv / Semantic Scholar search & import | Find and import papers without manual download. |
| E3 | Citation graph visualisation | Show how papers relate to each other. |
| E4 | BibTeX export | Ready-to-use references for the user's own paper. |
| E5 | Multi-user accounts | Supabase Auth; each user sees only their own library. |
| E6 | Streaming responses | Token-by-token output; feels far more responsive. |
| E7 | Hybrid search | Combine vector similarity with keyword search for better recall. |
| E8 | Re-ranking | A second model re-orders retrieved chunks for higher precision. |
| E9 | Cost & token dashboard | Show usage per request. Strong engineering signal. |
| E10 | Multi-language papers | Handle non-English sources. |

---

## E. Proposed Architecture

### High-level shape: three tiers

```
┌──────────────────────────────────────────────────────────────┐
│  BROWSER                                                     │
│  Next.js + React + TypeScript + Tailwind   (hosted: Vercel)  │
│  Upload UI · Library · Summaries · Gaps · Review · Chat      │
└───────────────────────────┬──────────────────────────────────┘
                            │  HTTPS / JSON (REST)
                            ▼
┌──────────────────────────────────────────────────────────────┐
│  BACKEND API                                                 │
│  Python + FastAPI              (hosted: cloud container)     │
│                                                              │
│   ingestion → extraction → chunking → embedding              │
│   retrieval → prompt building → LLM call → citation mapping  │
└──────┬──────────────────────────────┬────────────────────────┘
       │                              │
       ▼                              ▼
┌────────────────────┐      ┌─────────────────────────────────┐
│ Supabase Postgres  │      │ External AI APIs                │
│  + pgvector        │      │  LLM  ·  Embedding model        │
│  + Storage (PDFs)  │      │  [PROVIDER NOT YET CHOSEN]      │
└────────────────────┘      └─────────────────────────────────┘
```

### Why a separate Python backend instead of doing it all in Next.js?
**[EXPLAINED FOR BEGINNER]**
Next.js *could* call an AI API directly. We are not doing that because:
1. The AI/document ecosystem (PDF parsing, chunking, evaluation) is
   overwhelmingly **Python**. Fighting that costs weeks.
2. Vercel's serverless functions have short time limits. Ingesting a 40-page
   PDF can exceed them. A normal server does not have that problem.
3. Keeping AI keys on a separate backend means they **never** touch the browser.
4. The assignment is an *AI* project — a clean, inspectable Python AI layer is
   exactly what an examiner wants to see.

**Trade-off accepted:** two deployments instead of one, and slightly more setup.
Worth it.

### Folder responsibilities (APPROVED — decision D3)

The lecturer-required folder structure is kept intact. Each folder's agreed
responsibility:

| Folder | Responsibility | Language | In Git? |
|---|---|---|---|
| **`src/`** | **Python / AI backend** — FastAPI, RAG pipeline, ingestion, retrieval, prompts, evaluation | Python | ✅ Yes |
| **`app/`** | **Next.js frontend** — pages, components, Tailwind, typed API client | TypeScript | ✅ Yes |
| **`data/`** | Papers and derived text (`raw/`, `processed/`, `samples/`) | — | ⚠️ Samples only |
| **`notebooks/`** | Jupyter prototyping, before code moves into `src/` | Python | ✅ Yes |
| **`models/`** | Model configuration and prompt versions; weights git-ignored | — | ⚠️ Config only |
| **`docs/`** | Architecture, schema, decision log, deployment, demo script | Markdown | ✅ Yes |
| **`results/`** | Real measured evaluation outputs only | — | ✅ Yes |
| **`tests/`** | pytest (backend) + Vitest (frontend) | Python / TS | ✅ Yes |

**Rationale:** `src/` carries the graded AI core, so it sits in the conventional
source folder an examiner opens first. `app/` carries the deliverable named in
university requirement #5. Next.js's own internal `src/app/` App Router folder
lives *inside* `app/` and is a separate scope — no conflict.

Full detail, including the planned internal layout of `src/`, is in
[`CLAUDE.md`](CLAUDE.md) §10.

### Request flow: uploading a paper
```
User picks PDF → frontend POSTs to /api/papers/upload
  → backend validates (type, size)
  → stores original file in Supabase Storage
  → creates `papers` row with status = "processing"
  → background job: extract text → chunk → embed → insert into `chunks`
  → status = "ready"
  → frontend polls status and updates the UI
```

### Request flow: asking a question
```
User asks a question
  → backend embeds the question into a vector
  → pgvector finds the top-K most similar chunks (optionally filtered to
    selected papers)
  → backend builds a prompt: system rules + retrieved chunks + question
  → LLM generates an answer that must cite chunk IDs
  → backend maps chunk IDs back to paper + page for display
  → frontend renders the answer with clickable citations
```

---

## F. Technology Stack

### Agreed (from project brief)

| Layer | Choice | Why |
|---|---|---|
| Frontend framework | **Next.js (App Router)** | Industry standard React framework; first-class Vercel deploy. |
| Language (frontend) | **TypeScript** | Catches errors before runtime — a real safety net for a beginner. |
| Styling | **Tailwind CSS** | Fast, consistent UI without writing separate CSS files. |
| Backend | **Python + FastAPI** | Fast, modern, automatic interactive API docs, great for AI work. |
| Database | **Supabase PostgreSQL** | Managed Postgres + file storage + auth in one free tier. |
| Vector search | **pgvector** | Vectors live in the *same* database as the rest of the data — one system to run, back up, and reason about. |
| Frontend hosting | **Vercel** | Free, git-push deploys. |
| Backend hosting | Cloud container host — **[DECISION NEEDED]** | See §O. |

### Still to decide

#### **[RESOLVED 2026-09-02] 1 — LLM provider → Google Gemini (`gemini-3.7-flash`), Anthropic retained**

Both are implemented behind `src/rag/llm/base.py::LLMProvider`; `LLM_PROVIDER`
selects one at runtime, and only the selected provider's key is required.

The recommendation below was followed exactly — design provider-agnostically
first, then choose — which is why adding the second vendor cost one new file
(`src/rag/llm/gemini_provider.py`) plus a branch in `get_llm_provider`, with no
change to the analysis pipeline, the API layer, or the frontend.

D5 is therefore **settled in practice but not locked**: a third provider remains
one file plus one environment variable. The original comparison is kept below as
the record of why.

| Option | Strengths | Watch out for |
|---|---|---|
| **Anthropic (Claude)** | Excellent long-document reasoning and instruction-following; large context window suits whole-paper work; strong at refusing to invent facts | Paid from the start |
| **OpenAI (GPT)** | Largest ecosystem, most tutorials, cheap small models | Paid; quality varies a lot by model tier |
| **Google (Gemini)** | Generous free tier; very large context | Free-tier rate limits; API has changed frequently |
| **Local (Ollama)** | Free, private, no API key | Needs a strong machine; weaker output; **cannot deploy online easily** — conflicts with the deployment requirement |

**Recommendation:** design provider-agnostically (one `LLMClient` interface with
swappable implementations), then start on whichever paid API you are willing to
fund, with Gemini's free tier as the fallback for development. The abstraction
means the choice is reversible and costs one afternoon to switch.

#### 🔒 **[FINAL — LOCKED 2026-08-11] 2 — Embedding model → Jina `jina-embeddings-v3` @ 1024 dims**

| Setting | Value |
|---|---|
| Provider | Jina AI |
| Model | `jina-embeddings-v3` |
| **Dimensions** | **1024** (the model's default; Matryoshka allows 32–1024) |
| Max input | 8,192 tokens per request |
| Languages | 89 |
| Cost | **Free — 10M tokens, no credit card required** |
| Postgres column | `vector(1024)` |
| Index | HNSW, `vector_cosine_ops` |

**Decision history.** D6 was evaluated three times. Gemini `gemini-embedding-2`
(free) and OpenAI `text-embedding-3-small` (paid) were each provisionally
selected before this final re-evaluation, which ranked options against the
owner's stated priorities — **cost first**, then reliability, marks, portfolio
value, and beginner maintainability.

### Why Jina won

1. **Genuinely free, no payment method.** 10M free tokens with no credit card.
   A realistic 25-paper demo consumes ~265,000 tokens, so the allocation covers
   roughly **37 full re-ingests** — ample headroom for iterating on chunking.
2. **Asymmetric retrieval — the strongest academic argument.** The model ships
   task-specific LoRA adapters: documents are embedded with
   `retrieval.passage`, questions with `retrieval.query`. Questions and
   passages are linguistically different objects, and encoding each with an
   adapter trained for its role measurably improves retrieval. Most student RAG
   projects embed both identically; this is demonstrable retrieval engineering.
3. **Citable in the report.** Published and peer-reviewable —
   [arXiv:2409.10173](https://arxiv.org/abs/2409.10173).
4. **1024 dims indexes natively in pgvector** (limit is 2,000 for HNSW/IVFFlat).
5. **8,192-token input** — roughly 32× the planned chunk size, so no silent
   truncation is possible.
6. **89 languages**, covering the multilingual-papers limitation (E10).
7. **Simple REST API** — no SDK lock-in, no normalisation footguns.

### Why the alternatives were rejected

| Option | Reason rejected |
|---|---|
| **Gemini `gemini-embedding-2`** | Free, but Google **cut free-tier quotas by 50–80% on 2025-12-07** and per-model embedding limits are **not published** — only visible inside an AI Studio dashboard. A semester cannot be planned around an invisible, already-slashed quota. Also defaults to 3,072 dims, which pgvector **cannot index**. |
| **OpenAI `text-embedding-3-small`** | Technically excellent and best-documented, but **has no free tier** — requires a ~$5 minimum prepayment. Conflicts directly with priority #1. Retained as the documented paid upgrade path. |
| **OpenAI `text-embedding-3-large`** | 3,072 dims — above pgvector's 2,000-dimension index ceiling. Table would be unindexable. |
| **Cohere `embed-v4.0`** | Free tier is real but capped at 1,000 calls/month, sources **conflict** on the embed rate limit, and the trial key is **explicitly not licensed for production or commercial use** — weakens portfolio framing. |
| **Local (`bge-small`, sentence-transformers)** | Free forever and zero API risk, but PyTorch does not fit free-tier container RAM, conflicting with university requirement #5 (deployable application). A **512-token input cap** would also *silently truncate* chunks with no error. Retained as a Milestone 12 evaluation benchmark. |

### Storage impact (corrected)

An earlier estimate of 15,000 chunks for 100 papers was wrong. A ~10,000-token
paper at 1,000-character chunks yields ~40 chunks, so **100 papers ≈ 4,000
chunks**:

| Dimensions | Vectors + index + text | vs Supabase 500 MB free tier |
|---|---|---|
| 1024 (chosen) | **~36 MB** | ~7% — not a constraint |

Storage does not constrain this decision at any candidate dimension.

### 💰 Cost control (mandatory)

The free allocation is finite, so the same discipline applies as for a paid API:

- **Cache aggressively.** A chunk is embedded **once**, ever. Re-ingesting the
  same paper must not re-embed unchanged content.
- **Batch requests.** Many chunks per API call, never one call per chunk.
- **Never call the API in a test.** All unit tests use a fake provider — tests
  must be free, fast, offline, and deterministic.
- **Log token usage** per operation so consumption is measured, not guessed.

### 🔑 Key handling (mandatory)

- `JINA_API_KEY` lives **only** in `.env` (git-ignored) and in the deployment
  host's server-side environment variables.
- **Never** in source code, never committed, never logged, and never behind a
  `NEXT_PUBLIC_` prefix — the browser must never see it.
- All embedding calls are made **server-side from the FastAPI backend only**.

### Reversibility (design, not luck)

- `chunks.embedding_model` and `chunks.embedding_dimensions` record what
  produced every vector, so a partial migration can never silently mix vectors
  from two models.
- `src/rag/embeddings/base.py` defines a **provider-independent**
  `EmbeddingProvider` interface. Switching providers is a configuration change
  plus a re-index — not a rewrite.
- Any future migration **adds** a column and backfills; it never overwrites.
#### **[DECISION NEEDED] 3 — PDF text extraction library**
Candidates: `pypdf` (pure Python, simple), `pdfplumber` (better layout and
tables), `PyMuPDF` (fastest, best quality, but AGPL licence — matters for a
public repo). To be benchmarked on real papers in Milestone 3.

#### ✅ **[DECIDED] 4 — Python version → Python 3.12**
The machine shipped with only **Python 3.9.6** (Apple's built-in), which is too
old for modern AI libraries. **Approved 2026-08-11:** install Python 3.12 from
python.org and work inside a virtual environment. Resolves §R risk **R1**.

---

## G. Document / Data Strategy

### What data exists
| Data | Source | Committed to Git? |
|---|---|---|
| Uploaded PDFs | The user | ❌ No — copyright + size |
| Extracted text & chunks | Generated | ❌ No — regenerable |
| Embeddings | Generated | ❌ No — lives in the database |
| Sample test papers | Real open-access arXiv papers | ✅ Yes — 3–5 small ones only |
| Evaluation outputs | Real script runs | ✅ Yes — real numbers only |

### Directory contract
```
data/raw/        original uploaded PDFs        (git-ignored)
data/processed/  extracted text / chunk JSON   (git-ignored)
data/samples/    small open-licence papers     (COMMITTED, with SOURCES.md)
```

### Chunking strategy (initial proposal, to be tuned)
- Split on structure first (section headings), then by size.
- Target ~1000 characters per chunk with ~150 characters overlap.
- Overlap exists so a sentence split across a boundary is not lost.
- Every chunk keeps: `paper_id`, `page_number`, `section_title`, `chunk_index`.
  **This metadata is what makes citation possible.** Without it there is no
  provenance, and without provenance the tool is academically worthless.

### Integrity rules
- Only real, legally obtainable papers.
- `data/samples/SOURCES.md` records the title, authors, arXiv ID, and licence
  of every committed sample.
- **No synthetic or fabricated papers, ever.**

---

## H. RAG Pipeline

### Stage 1 — Ingestion (happens once per uploaded paper)
```
PDF file
  ↓ validate      type = PDF, size ≤ limit, not corrupt
  ↓ store         original saved to Supabase Storage
  ↓ extract       PDF → raw text + page numbers
  ↓ clean         strip headers/footers, fix hyphenation and line breaks
  ↓ segment       detect Abstract / Intro / Method / Results / Discussion /
                  Limitations / Future Work / References
  ↓ chunk         overlapping chunks + metadata
  ↓ embed         each chunk → vector (batched to control cost)
  ↓ store         chunks + vectors → Postgres/pgvector
```

### Stage 2 — Retrieval (happens on every question)
```
question
  ↓ embed         question → vector
  ↓ search        pgvector cosine similarity, top-K chunks
  ↓ filter        drop chunks below the minimum similarity score
  ↓ (optional)    re-rank for precision  [enhancement E8]
  ↓ assemble      ordered, de-duplicated context with source labels
```

### Stage 3 — Generation
```
context + question
  ↓ prompt        system rules + numbered context blocks + user question
  ↓ generate      LLM produces answer containing [1][2] style markers
  ↓ map           markers → chunk → paper + page
  ↓ verify        every claim carries a citation; else flag it
  ↓ return        answer + sources + token usage
```

### Feature-specific pipelines
- **Summary (F5):** retrieve that paper's abstract, method, results and
  conclusion chunks → generate against a fixed structured schema.
- **Research gaps (F6):** specifically retrieve *limitations* and *future work*
  chunks across all selected papers → cluster into themes → report gaps that
  multiple papers independently point to. Gaps must be **evidence-backed**,
  never invented.
- **Literature review (F7):** map-reduce. First summarise each paper
  individually ("map"), then synthesise those summaries into themed sections
  ("reduce"). This avoids blowing the context window on 20 papers.

### The anti-hallucination contract
1. The system prompt forbids using outside knowledge.
2. If retrieval returns nothing above the score threshold → respond
   *"insufficient evidence in the uploaded papers"*.
3. Uncited claims are flagged in the UI.
4. Temperature kept low (≈0.2) for factual tasks.

---

## I. Database Design Proposal

Postgres via Supabase, with the `vector` extension enabled.

### `papers`
| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `user_id` | uuid | FK → auth.users (null until auth is added) |
| `title` | text | extracted or user-supplied |
| `authors` | text[] | |
| `year` | int | nullable |
| `filename` | text | original name |
| `storage_path` | text | Supabase Storage path |
| `file_size_bytes` | bigint | |
| `page_count` | int | |
| `status` | text | `processing` \| `ready` \| `failed` |
| `error_message` | text | populated on failure |
| `created_at` | timestamptz | |

### `chunks`
| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `paper_id` | uuid | FK → papers, `ON DELETE CASCADE` |
| `chunk_index` | int | order within the paper |
| `content` | text | the actual text |
| `page_number` | int | **needed for citations** |
| `section_title` | text | nullable |
| `token_count` | int | |
| `embedding` | `vector(N)` | **N fixed by the embedding model — §F decision 2** |
| `created_at` | timestamptz | |

Index: `ivfflat` (or `hnsw`) on `embedding` using cosine distance.
**[EXPLAINED]** Without this index, every search scans every row. With it,
search stays fast as the library grows.

### `generations`
Stores AI outputs so they are not regenerated (and re-paid for) on every view.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `paper_id` | uuid | nullable — reviews span many papers |
| `kind` | text | `summary` \| `gap_analysis` \| `literature_review` \| `chat` |
| `input_params` | jsonb | which papers, which question |
| `content` | text | the generated output |
| `citations` | jsonb | chunk ids → page mapping |
| `model` | text | which model produced it (**reproducibility**) |
| `prompt_version` | text | which prompt version (**reproducibility**) |
| `input_tokens` / `output_tokens` | int | cost tracking |
| `created_at` | timestamptz | |

### `chat_messages`
`id`, `session_id`, `role` (`user`/`assistant`), `content`, `citations` jsonb,
`created_at`.

### Security
Row Level Security **enabled on every table** before any multi-user feature
ships, so one user can never read another's papers.

---

## J. API Design Proposal

FastAPI, REST, JSON. All routes under `/api`. FastAPI auto-generates
interactive docs at `/docs` — useful for the university demo.

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness check (used by the host) |
| `POST` | `/api/papers/upload` | Upload a PDF; returns `paper_id` + status |
| `GET` | `/api/papers` | List papers |
| `GET` | `/api/papers/{id}` | Paper detail + processing status |
| `DELETE` | `/api/papers/{id}` | Delete paper, chunks, and stored file |
| `POST` | `/api/papers/{id}/summarize` | **Requirement 2** |
| `POST` | `/api/analysis/gaps` | **Requirement 3** — body: `paper_ids[]` |
| `POST` | `/api/analysis/literature-review` | **Requirement 4** — body: `paper_ids[]`, options |
| `POST` | `/api/chat` | Grounded Q&A — body: question, `paper_ids[]` |
| `POST` | `/api/search` | Raw retrieval (debugging + demo of the RAG internals) |
| `GET` | `/api/export/{generation_id}` | Markdown / PDF export |

### Conventions
- Request and response bodies validated by **Pydantic** models.
- Consistent error envelope: `{ "error": { "code", "message", "details" } }`.
- Long jobs return immediately with a status; the client polls. No timeouts.
- Every AI response includes `sources[]` and `usage{}`.

---

## K. Frontend Structure Proposal

```
app/
├── src/
│   ├── app/                      # Next.js App Router
│   │   ├── layout.tsx
│   │   ├── page.tsx              # Landing / dashboard
│   │   ├── upload/page.tsx       # Requirement 1
│   │   ├── library/page.tsx      # Paper list
│   │   ├── papers/[id]/page.tsx  # Summary view — Requirement 2
│   │   ├── gaps/page.tsx         # Requirement 3
│   │   ├── review/page.tsx       # Requirement 4
│   │   └── chat/page.tsx         # Grounded Q&A
│   ├── components/
│   │   ├── ui/                   # Button, Card, Dialog, Spinner…
│   │   ├── PaperUploader.tsx
│   │   ├── PaperCard.tsx
│   │   ├── SummaryPanel.tsx
│   │   ├── GapList.tsx
│   │   ├── ReviewEditor.tsx
│   │   ├── ChatWindow.tsx
│   │   └── CitationBadge.tsx     # the trust-building component
│   ├── lib/
│   │   ├── api.ts                # typed backend client
│   │   ├── types.ts              # shared TypeScript types
│   │   └── utils.ts
│   └── styles/
├── public/
├── package.json
└── tsconfig.json
```

### Principles
- Server Components for data fetching; Client Components only where
  interactivity is needed.
- Every long-running action shows a **loading state**; every failure shows a
  **readable error**. Beginners' projects usually skip this — examiners notice.
- Citations are visually prominent. Trust is the product.
- Responsive and accessible (keyboard navigation, sensible contrast).

---

## L. Testing Strategy

| Layer | Tool | What it covers |
|---|---|---|
| Backend unit | `pytest` | chunking, text cleaning, citation mapping, prompt building |
| Backend integration | `pytest` + FastAPI `TestClient` | full upload → retrieve → generate path |
| Database | test schema / transaction rollback | migrations, cascade deletes, vector queries |
| Frontend unit | Vitest + React Testing Library | components render and handle states |
| End-to-end | Playwright (optional) | upload a real sample paper and see a real summary |
| Manual | checklist in `docs/` | the university demo script |

### Rules
- AI API calls are **mocked** in unit tests — tests must be free, fast, and
  deterministic.
- A small number of clearly-marked **live** tests may hit the real API,
  run manually, never in CI by default.
- Every bug that is found gets a regression test.
- Test fixtures use the real sample papers in `data/samples/`.
- Target: meaningful coverage of `src/`, not a vanity percentage.

---

## M. AI Evaluation Strategy

This section is what separates a top-grade project from an average one. **Every
number reported here must come from a real run. Fabricated metrics are
academic misconduct — see CLAUDE.md §5.**

### 1. Retrieval quality
Build a small, honest test set: ~20–30 questions written by hand against the
sample papers, each labelled with the chunk(s) that genuinely answer it.

| Metric | Meaning in plain language |
|---|---|
| Recall@K | Of the questions, how often was a correct chunk in the top K results? |
| Precision@K | How much of what we retrieved was actually relevant? |
| MRR | How high up the list did the correct chunk appear? |

### 2. Generation quality
| Metric | Method |
|---|---|
| **Groundedness / faithfulness** | Is every claim supported by the retrieved text? Manual rubric + optional LLM-as-judge. |
| **Citation accuracy** | Do the cited pages actually contain the claim? Sampled and checked by hand. |
| **Hallucination rate** | % of claims with no support. Target: near zero. |
| **Refusal correctness** | Ask questions the papers cannot answer. Does it correctly say "insufficient evidence"? |
| **Completeness** | Does the summary cover objective/method/results/limitations? |

### 3. System metrics
Latency per stage, tokens and cost per operation, ingestion time per page,
failure rate on messy PDFs.

### Reporting
- Scripts live in `src/evaluation/`; outputs in `results/`.
- Every result file records: date, model, prompt version, dataset, parameters.
- **Negative results are reported too.** Honest limitations earn marks.
- If an evaluation has not been run, the file says **"not yet run"**.

---

## N. Security Considerations

| Risk | Mitigation |
|---|---|
| **Leaked API keys** | Env vars only; `.env` git-ignored; `.env.example` has placeholders; keys never sent to the browser |
| **Service-role key exposure** | Backend-only; never under `NEXT_PUBLIC_`; never logged |
| **Malicious file upload** | Validate MIME type and magic bytes, cap size, never execute uploaded content |
| **Prompt injection** — a PDF containing *"ignore your instructions"* | Treat retrieved text as **untrusted data**, never as instructions; clear delimiters; the system prompt states that context is data only |
| **Cross-user data leakage** | Postgres Row Level Security on every table |
| **SQL injection** | Parameterised queries / ORM only; never string-concatenated SQL |
| **Cost abuse / runaway spend** | Rate limiting, per-request token caps, provider spending limits, usage logging |
| **Overly open CORS** | Explicit allow-list of origins; no `*` in production |
| **Sensitive data in logs** | Never log file contents, keys, or full prompts in production |
| **Dependency vulnerabilities** | Pin versions; enable Dependabot on GitHub |

---

## O. Deployment Strategy

### Frontend — **Vercel**
Connect the GitHub repo; Vercel builds on push. Set `NEXT_PUBLIC_*` env vars in
the Vercel dashboard. Free tier is sufficient.

### Backend — **[DECISION NEEDED]**
FastAPI needs a host that runs a long-lived container.

| Option | Free tier | Notes |
|---|---|---|
| **Render** | Yes (sleeps when idle) | Simplest for a beginner; free instance cold-starts (~30 s) — mention it in the demo |
| **Railway** | Trial credit | Very smooth developer experience |
| **Fly.io** | Small free allowance | More powerful, more concepts to learn |
| **Google Cloud Run** | Generous | Scales to zero; steeper learning curve |

**Recommendation:** **Render** for the university deadline (lowest risk,
Dockerfile-based, one-click from GitHub), with the option to move later. The
app must be containerised with a `Dockerfile` so the host is swappable.

### Database — **Supabase** managed free tier.

### Environments
`local` (developer machine) → `production` (deployed). A `preview` environment
comes free with Vercel pull requests.

### Pre-deployment checklist
- [ ] `DEBUG=false`, real CORS allow-list
- [ ] All env vars set on the host
- [ ] `/health` returns 200
- [ ] Real upload → summary works on the deployed URL
- [ ] Cost limits set at the AI provider
- [ ] README has the live URL

---

## P. GitHub Strategy

- **GitHub is the source of truth.** Work is pushed, not left on one laptop.
- Repository name: **`researchforge`** ✅ **[DECIDED 2026-08-11]**
  — lowercase and hyphenated. The local folder was renamed to match, so the
  local path, the repo name, and the deployment name are all identical and
  portable across Mac / Windows / Linux. Resolves §R risk R2.
- Public repository (it is a portfolio piece), MIT licence.

### Branches
| Branch | Purpose |
|---|---|
| `main` | Always working, always deployable |
| `feature/<name>` | One feature at a time; merged via pull request |

### Commits
`type: short description` — `feat:`, `fix:`, `docs:`, `test:`, `chore:`,
`refactor:`. Small and frequent beats one giant commit.

### Repository presentation (this is what recruiters and examiners see)
- README with a screenshot/GIF, live demo link, and clear setup steps
- Architecture diagram in `docs/`
- Real evaluation results in `results/`
- Meaningful commit history showing incremental progress
- GitHub Actions CI running tests on every push (Milestone 12)

---

## Q. Development Roadmap

Each milestone ends with a **test**, a **commit**, and a **stop for approval**.

| # | Milestone | Deliverable | Requirement |
|---|---|---|---|
| **0** | **Setup & planning** ✅ | Repo structure, CLAUDE.md, PROJECT_PLAN.md, README, .gitignore, .env.example, git init | — |
| **1** | Environment & foundations | Python 3.12 + venv, `requirements.txt`, "hello world" FastAPI with `/health`, tests running | — |
| **2** | Database foundation | Supabase project, pgvector enabled, migrations for `papers`/`chunks`, connection verified | — |
| **3** | PDF ingestion | Upload endpoint, storage, real text extraction benchmarked on real papers | **R1** |
| **4** | Chunking & embedding | Chunking with metadata, embeddings stored, similarity search returns sensible chunks | — |
| **5** | Retrieval + Q&A | `/api/chat` returns grounded, cited answers; refuses when evidence is missing | — |
| **6** | Summarisation | `/api/papers/{id}/summarize` produces structured cited summaries | **R2** |
| **7** | Research gaps | `/api/analysis/gaps` produces evidence-backed gaps | **R3** |
| **8** | Literature review | `/api/analysis/literature-review` produces a cited synthesis | **R4** |
| **9** | Frontend foundation | Next.js + Tailwind, layout, API client, upload + library pages working end-to-end | **R1, R5** |
| **10** | Frontend features | Summary, gaps, review, and chat pages with citations and loading/error states | **R2–R5** |
| **11** | Deployment | Backend containerised and deployed, frontend on Vercel, live URL working | **R5** |
| **12** | Evaluation & polish | Real evaluation run, results committed, CI, docs, demo script, final report material | — |

**Rule:** do not start milestone *N+1* until milestone *N* is tested and approved.

---

## R. Risk Analysis

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| **R1** | ~~Python 3.9.6 is too old for modern AI libraries~~ | — | — | ✅ **RESOLVED 2026-08-11** — Python 3.12.10 (arm64) installed and verified; the project venv runs on 3.12.10, not the system 3.9.6. |
| **R2** | ~~Project folder name contains spaces and parentheses~~ | — | — | ✅ **RESOLVED 2026-08-11** — renamed to `researchforge` before any venv or tooling was created, so no absolute paths had to be repaired. |
| **R3** | AI API costs spiral | Medium | Medium | Cheap models in development, cache generations in the DB, cap tokens, set provider spending limits, batch embeddings |
| **R4** | LLM hallucinates in academic output | Medium | **Critical** | RAG grounding, mandatory citations, refusal path, evaluation in §M |
| **R5** | Messy PDFs extract badly (two-column layouts, scans, formulas) | High | Medium | Benchmark extraction libraries on real papers; detect near-empty extraction and fail loudly; document scanned-PDF/OCR as a known limitation |
| **R6** | Scope creep — too many enhancement features | High | High | Core features first; §D is explicitly "only after core is done" |
| **R7** | Free-tier host cold starts / limits during the demo | Medium | Medium | Warm the service before demoing; keep a recorded backup demo video |
| **R8** | Embedding model changed after data is indexed | Low | High | Decide before Milestone 2; store model name per chunk; treat re-embedding as a migration |
| **R9** | Beginner overwhelmed by simultaneous complexity | Medium | Medium | Strict milestone order; explanations before code; backend proven before frontend starts |
| **R10** | Secret accidentally committed | Low | **Critical** | `.gitignore` in place from commit #1; rotate first, then clean history |
| **R11** | Deadline pressure | Medium | High | Requirements 1–5 are built before every optional feature; Milestone 11 (deploy) is not left to the last week |
| **R12** | Large context window costs on 20+ papers | Medium | Medium | Map-reduce summarisation (§H), retrieval instead of stuffing whole papers |

---

## S. Definition of Done — per milestone

### Global gate (applies to *every* milestone)
1. Runs without errors from a clean checkout.
2. **Actually tested**, with the output shown to the owner.
3. No secrets committed.
4. No hard-coded absolute paths.
5. No fake data or fabricated results.
6. Docs updated.
7. Committed with a clear message.
8. Owner told plainly what works and what does not.

---

**M0 — Setup & Planning** ✅
- [x] Directory structure created
- [x] `CLAUDE.md`, `PROJECT_PLAN.md`, `README.md`, `.gitignore`, `.env.example`, `LICENSE` created
- [x] Environment versions verified and reported
- [x] Git repository initialised
- [x] No fake data, no secrets, no premature installs

**M1 — Environment & Foundations** ✅ **COMPLETE 2026-08-11**
- [x] Python 3.11+ installed and version printed — **3.12.10, arm64**
- [x] Virtual environment created and documented for Mac **and** Windows
- [x] `requirements.txt` with pinned versions, installs cleanly
- [x] FastAPI runs; `GET /health` returns 200 — verified, 0.8 ms response
- [x] `/docs` interactive API page loads — HTTP 200
- [x] `pytest` runs at least one passing test — **9/9 passing**
- [x] `ruff check` and `ruff format --check` clean
- [x] No hard-coded absolute paths; no secrets in source

*Not carried out:* a from-scratch reinstall of `requirements.txt` into a
throwaway venv (blocked by a local tool permission). The pins were taken from
a real verified install, but reproducibility on a second machine is unproven
until someone clones the repo and installs. Worth confirming at Milestone 2.

**M2 — Database Foundation**
- [ ] Supabase project created; keys in local `.env` only
- [ ] `vector` extension enabled
- [ ] `papers` and `chunks` tables created via a committed migration file
- [ ] Backend connects successfully; a test row is inserted and read back
- [ ] Embedding dimension decision recorded in this document

**M3 — PDF Ingestion**
- [ ] Upload endpoint accepts a real PDF and rejects non-PDFs and oversized files
- [ ] File stored in Supabase Storage; `papers` row created
- [ ] Real text extracted from ≥3 real sample papers, verified by eye
- [ ] Extraction library choice justified by a real benchmark in `results/`
- [ ] Failures set `status='failed'` with a readable message

**M4 — Chunking & Embedding**
- [ ] Chunks carry `page_number` and `chunk_index`
- [ ] Embeddings generated and stored; dimension matches the column
- [ ] Vector index created
- [ ] A manual similarity search returns *obviously* relevant chunks
- [ ] Token/cost per paper measured and recorded

**M5 — Retrieval & Q&A**
- [ ] `/api/chat` answers questions about the sample papers
- [ ] Every answer includes real, correct citations (paper + page)
- [ ] Out-of-scope questions produce "insufficient evidence", not invention
- [ ] Retrieval parameters configurable via env vars

**M6 — Summarisation (Requirement 2)**
- [ ] Structured summary: objective, method, data, findings, limitations, contribution
- [ ] Verified against ≥3 real papers by reading them
- [ ] Result cached in `generations`
- [ ] Citations present and spot-checked as accurate

**M7 — Research Gaps (Requirement 3)**
- [ ] Gaps derived from real "limitations"/"future work" text
- [ ] Each gap cites the paper(s) it came from
- [ ] Manually verified as genuine, not invented
- [ ] Handles the single-paper case sensibly

**M8 — Literature Review (Requirement 4)**
- [ ] Themed, multi-paper synthesis produced
- [ ] Every claim cited
- [ ] Works with at least 5 papers without exceeding context limits
- [ ] Exportable as Markdown

**M9 — Frontend Foundation (Requirement 1 & 5)**
- [ ] Next.js + TypeScript + Tailwind running locally
- [ ] Typed API client; no secrets in frontend code
- [ ] Upload page uploads a real PDF and shows real processing status
- [ ] Library page lists real papers
- [ ] Loading and error states implemented

**M10 — Frontend Features (Requirements 2–5)**
- [ ] Summary, gaps, review, and chat pages functional
- [ ] Citations visible and clickable
- [ ] Responsive and keyboard-accessible
- [ ] Errors never show a blank screen

**M11 — Deployment (Requirement 5)**
- [ ] Backend containerised (`Dockerfile`) and deployed
- [ ] Frontend deployed on Vercel
- [ ] Env vars configured on both hosts; no secrets in the repo
- [ ] Full flow verified **on the live URL**
- [ ] Live URL in `README.md`

**M12 — Evaluation & Polish**
- [ ] Real evaluation run; real numbers in `results/`
- [ ] Limitations honestly documented
- [ ] CI runs tests on push
- [ ] README has screenshots and setup instructions verified on a clean machine
- [ ] Demo script written for the university presentation

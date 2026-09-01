# 🔨 ResearchForge

### AI Research Paper Assistant (Gen AI)

> An AI-powered research assistant that reads your research papers, summarises
> them, finds the gaps nobody has studied yet, and drafts a cited literature
> review — with every claim traceable back to the source page.

**BIT4543 Artificial Intelligence — Project #17**

![Status](https://img.shields.io/badge/status-in%20development-yellow)
![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![Next.js](https://img.shields.io/badge/next.js-frontend-black)

> ⚠️ **Project status: working MVP — upload a PDF and get a summary, research gaps, and a literature review.**
> Runs locally only. **No database and no deployment yet** — analysis is stateless and nothing is saved between requests.
> The backend foundation runs (FastAPI + `/health`, 9/9 tests passing), but the
> AI features are not built yet. Follow [`PROJECT_PLAN.md`](PROJECT_PLAN.md)
> for the development roadmap.

---

## The problem

Writing a literature review means reading dozens of papers, extracting each
one's contribution, spotting what has *not* been studied, and synthesising it
all into coherent prose. It takes weeks, and it is easy to miss things.

## The solution

Upload your papers. The assistant gives you:

| Feature | What it does |
|---|---|
| 📄 **Upload** | Drop in PDFs — they are parsed, chunked, and indexed for search |
| 📝 **Summarise** | Structured summaries: objective, method, data, findings, limitations |
| 🔍 **Find research gaps** | Cross-paper analysis of stated limitations and future work |
| 📖 **Literature review** | A themed, cited synthesis across your whole collection |
| 💬 **Ask questions** | Chat with your library — grounded answers with page-level citations |

### Why it can be trusted

The system is built on **RAG (Retrieval-Augmented Generation)**. Before the AI
writes anything, the system searches *your actual uploaded papers* for the
relevant passages and instructs the model to answer **only** from that text,
with citations.

If the papers don't contain the answer, the assistant says
**"insufficient evidence"** instead of inventing one. That refusal is a feature,
not a limitation — it is what makes the output usable for academic work.

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  FRONTEND — Next.js · TypeScript · React · Tailwind          │
│  Upload · Library · Summaries · Gaps · Review · Chat         │
│  Hosted on Vercel                                            │
└───────────────────────────┬──────────────────────────────────┘
                            │  HTTPS / JSON
                            ▼
┌──────────────────────────────────────────────────────────────┐
│  BACKEND — Python · FastAPI                                  │
│  ingest → extract → chunk → embed                            │
│  retrieve → prompt → generate → map citations                │
└──────┬──────────────────────────────┬────────────────────────┘
       ▼                              ▼
┌────────────────────┐      ┌─────────────────────────────────┐
│ Supabase Postgres  │      │ LLM + Embedding APIs            │
│ + pgvector         │      │ (provider not yet selected)     │
│ + File Storage     │      │                                 │
└────────────────────┘      └─────────────────────────────────┘
```

Full reasoning behind every choice is in [`PROJECT_PLAN.md`](PROJECT_PLAN.md) §E.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | Next.js (App Router), TypeScript, React, Tailwind CSS |
| **Backend** | Python 3.11+, FastAPI |
| **Database** | Supabase PostgreSQL |
| **Vector search** | pgvector |
| **AI** | API-based LLM + embedding model *(selection pending)* |
| **Testing** | pytest, Vitest |
| **Hosting** | Vercel (frontend) + containerised cloud host (backend) |

---

## 📁 Repository Structure

```
.
├── data/              # Papers and derived text (contents git-ignored)
│   ├── raw/               # Original uploaded PDFs
│   ├── processed/         # Extracted and chunked text
│   └── samples/           # Small, openly-licensed test papers (committed)
├── notebooks/         # Jupyter experiments and prototyping
├── src/               # Python backend: FastAPI API + RAG pipeline
├── app/               # Next.js frontend application
├── models/            # Model configuration (weights git-ignored)
├── docs/              # Architecture notes, diagrams, report material
├── results/           # Real evaluation outputs only
├── tests/             # Automated tests
├── CLAUDE.md          # Permanent project rules
├── PROJECT_PLAN.md    # Full plan and roadmap
├── requirements.txt   # Python dependencies
├── .env.example       # Environment variable template (no real secrets)
└── LICENSE
```

---

## 🚀 Getting Started

> These steps become fully functional at **Milestone 1**. They are documented
> now so setup is reproducible on any operating system.

### Prerequisites

| Tool | Minimum version | Check with |
|---|---|---|
| Git | 2.30+ | `git --version` |
| Python | **3.11+** | `python3 --version` |
| Node.js | 18+ | `node --version` |
| npm | 9+ | `npm --version` |

### 1. Clone

```bash
git clone https://github.com/tirukon015/researchforge.git
cd researchforge
```

### 2. Configure environment variables

```bash
cp .env.example .env      # macOS / Linux
copy .env.example .env    # Windows (Command Prompt)
```

Then open `.env` and fill in your own values.
**`.env` is git-ignored and must never be committed.**

### 3. Backend setup

**macOS / Linux**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn src.main:app --reload --port 8000
```

**Windows (PowerShell)**
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn src.main:app --reload --port 8000
```

API docs will be available at <http://localhost:8000/docs>.

### 4. Frontend setup

```bash
cd app
npm install
npm run dev
```

App will be available at <http://localhost:3000>.

The frontend reads `NEXT_PUBLIC_API_BASE_URL` (see `app/.env.example`).
It defaults to `http://localhost:8000`, so no configuration is needed
for local development.

---

## 🔬 Using ResearchForge

1. Start the backend (step 3) and the frontend (step 4).
2. Open <http://localhost:3000>. The header shows whether the backend is reachable.
3. Select a PDF and press **Analyse paper**.
4. Read the results under the **Summary**, **Research Gaps**, and
   **Literature Review** tabs.

Analysis typically takes one to three minutes: the backend makes three separate
reasoning calls, one per task.

### AI configuration

An **Anthropic API key is required** for analysis. Everything else — the server,
`/health`, PDF extraction, and the whole test suite — works without one.

```bash
# in .env  (git-ignored; never commit it)
ANTHROPIC_API_KEY=your-key-here
```

Without a key, `POST /api/analyze` returns **503** with a message naming the
missing variable. Set `LLM_EFFORT=low` for cheaper, faster runs while testing.

| Setting | Default | Purpose |
|---|---|---|
| `LLM_PROVIDER` | `anthropic` | Selects the provider implementation |
| `LLM_MODEL` | `claude-opus-5` | 1M-token context window |
| `LLM_EFFORT` | `high` | `low` … `max` — how hard the model thinks |
| `LONG_PAPER_CHAR_THRESHOLD` | `400000` | Above this, chunking activates |

### API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness check used by hosting platforms |
| `GET` | `/` | API description |
| `POST` | `/api/analyze` | Upload a PDF; returns summary, gaps, and review |

`POST /api/analyze` takes `multipart/form-data` with one `file` field.

```bash
curl -X POST http://localhost:8000/api/analyze   -F "file=@paper.pdf;type=application/pdf"
```

| Status | Meaning |
|---|---|
| `200` | Analysis succeeded |
| `413` | File exceeds the upload size limit |
| `422` | Not a readable PDF (wrong type, empty, or a scan with no text layer) |
| `502` | The AI service failed or returned unusable output |
| `503` | No AI credentials configured on the server |

Interactive docs: <http://localhost:8000/docs>.

### How it works

```
PDF → validate + extract (pypdf) → clean → fits in context?
        ├── yes → analyse whole            (the normal path)
        └── no  → chunk → digest each → combine
   → 3 independent structured LLM calls → JSON → UI
```

Scanned PDFs are **rejected**, not silently returned empty — ResearchForge does
no OCR. Where a paper does not support a section, the output says so rather than
inventing content.

---

## 🧪 Testing

```bash
pytest        # backend tests — fully offline, no API key, zero tokens
```

The suite replaces the LLM with a fake provider and builds real PDF bytes in
`tests/pdf_fixtures.py`, so PDF extraction is genuinely exercised.

Frontend checks:

```bash
cd app
npx tsc --noEmit   # type check
npm run build      # production build
```

There is no frontend unit-test runner yet.

---

## 📊 Evaluation

AI systems must be measured, not assumed to work. This project evaluates:

- **Retrieval quality** — Recall@K, Precision@K, MRR
- **Groundedness** — is every claim supported by the retrieved text?
- **Citation accuracy** — do the cited pages actually contain the claim?
- **Hallucination rate** — claims with no supporting evidence
- **Refusal correctness** — does it decline when the papers can't answer?

> **Integrity commitment:** every number published in `results/` comes from a
> real script run on real papers. Nothing in this repository is fabricated.
> Evaluations that have not been run are labelled *"not yet run"*.

Methodology: [`PROJECT_PLAN.md`](PROJECT_PLAN.md) §M.

---

## 🔐 Security

- All credentials come from environment variables — never from source code
- `.env` is git-ignored; `.env.example` contains placeholders only
- The Supabase service-role key is backend-only and never exposed to the browser
- Uploaded files are validated by type and size
- Retrieved paper text is treated as untrusted **data**, never as instructions
  (defence against prompt injection hidden inside a PDF)
- Row Level Security on all database tables

Details: [`PROJECT_PLAN.md`](PROJECT_PLAN.md) §N.

---

## 🗺️ Roadmap

| # | Milestone | Status |
|---|---|---|
| 0 | Setup & planning | ✅ Complete |
| 1 | Environment & foundations | ✅ Complete |
| 3 | PDF ingestion & text extraction | ✅ Complete |
| 6 | Paper summarisation | ✅ Complete |
| 7 | Research gap identification | ✅ Complete |
| 8 | Literature review generation | ✅ Complete (single-paper scope) |
| 9 | Frontend foundation | ✅ Complete |
| 10 | Frontend features | ✅ Upload + results UI |
| 2 | Database foundation (Supabase + pgvector) | ⬜ Next |
| 4 | Chunking & embeddings (semantic search) | ⬜ Not needed by the MVP |
| 5 | Retrieval & grounded Q&A | ⬜ |
| 11 | Deployment | ⬜ |
| 12 | Evaluation & polish | ⬜ |

---

## 🎓 University Requirements Coverage

| # | Requirement | Milestone |
|---|---|---|
| 1 | Allow users to upload research papers | ✅ Implemented |
| 2 | Generate summaries of research papers | ✅ Implemented |
| 3 | Identify research gaps | ✅ Implemented |
| 4 | Produce literature reviews | ✅ Implemented — scoped to the related work discussed *within* the uploaded paper. A cross-corpus review needs the multi-paper library (M2). |
| 5 | Provide a Research Assistant Application | M9–M11 |

---

## ⚠️ Known Limitations

To be documented honestly as development proceeds. Expected areas:
scanned/image-only PDFs without OCR, complex two-column layouts, mathematical
notation, and non-English papers.

---

## 📄 License

[MIT](LICENSE)

---

## 🙏 Acknowledgements

Built as coursework for **BIT4543 Artificial Intelligence**.
Sample papers used for testing are open-access and credited in
`data/samples/SOURCES.md`.

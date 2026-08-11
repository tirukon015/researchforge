# CLAUDE.md — Permanent Project Rules

> This file is read automatically at the start of every Claude Code session.
> It is the **permanent constitution** of this project. These rules override
> convenience, speed, and default behaviour. When a rule here conflicts with a
> suggestion, **this file wins**.

---

## 1. Project Identity

| Field | Value |
|---|---|
| **Project** | **ResearchForge** — AI Research Paper Assistant (Gen AI) |
| **Course** | BIT4543 Artificial Intelligence |
| **Project number** | #17 |
| **Type** | University capstone + public portfolio project |
| **Owner skill level** | **Complete beginner** in AI / RAG / backend development |

### University requirements (non-negotiable)
The delivered system **must**:
1. Allow users to **upload research papers**.
2. Generate **summaries** of research papers.
3. Identify **research gaps**.
4. Produce **literature reviews**.
5. Provide a **Research Assistant Application** as the final application.

No milestone is "done" if it moves the project away from these five outcomes.

---

## 2. How to Work With Me (Communication Rules)

- **I am a complete beginner.** Explain things in plain language. Assume I do
  not know what an embedding, a vector index, a migration, or a virtualenv is
  until you have explained it.
- **Explain every major technical decision** before acting on it: what the
  options are, what you recommend, and *why*.
- **Never make an architecture decision silently.** Database schema, AI
  provider, framework choice, folder layout, auth model — all require my
  explicit approval.
- When you use jargon, define it inline the first time in that session.
- Prefer **short, concrete next steps** over long theory.
- Tell me honestly when something failed, was skipped, or is uncertain.
  Never report success you have not verified.

---

## 3. Development Discipline

- **Work in small milestones.** One milestone at a time.
- **Test after every milestone** before moving to the next one.
- **Do not build the entire application at once.**
- **Stop and report** at the end of each milestone. Wait for my go-ahead.
- Inspect existing files before writing anything.
- Small, reviewable changes beat large sweeping rewrites.

---

## 4. File Safety Rules

- **NEVER delete existing files.**
- **NEVER overwrite an existing file without asking me first.**
- Prefer creating new files or making additive edits.
- If a file must be replaced, show me what changes and get approval.
- Do not restructure directories without approval.

---

## 5. Integrity Rules (Academic Honesty)

This is graded university work. Fabrication is a serious offence.

- **NEVER create fake data.**
- **NEVER create fake research results.**
- **NEVER create fake evaluation results, benchmarks, scores, or metrics.**
- Every number in `results/` must come from a real script run on real input.
- If an evaluation has not been run, the file must say **"not yet run"** —
  not a placeholder number.
- Sample papers must be **real, openly licensed** papers (e.g. arXiv), with
  the source recorded in `data/samples/SOURCES.md`.
- AI-generated summaries must be traceable to real uploaded source text
  (this is what the RAG citations are for).

---

## 6. Secrets & Security Rules

- **NEVER put an API key, password, token, or secret in any committed file.**
- **NEVER hard-code credentials in source code.**
- All secrets come from **environment variables** only.
- `.env` is git-ignored. `.env.example` is committed and contains
  **placeholders only**.
- The Supabase **service role key** is backend-only. It must never reach the
  frontend or appear in any `NEXT_PUBLIC_*` variable.
- Anything prefixed `NEXT_PUBLIC_` is **visible to the whole internet**.
- If a secret is ever committed by accident: rotate the key immediately,
  then clean history. Rotation first.

---

## 6a. 🚨 RPOMS ISOLATION — ABSOLUTE RULE

**RPOMS is a separate, critical production project. It is completely
off-limits. This rule overrides convenience, speed, and every other
instruction in this file.**

### Never, under any circumstances:
- Read, open, or inspect RPOMS files, credentials, or `.env`
- Copy, reuse, or reference any RPOMS secret, key, token, or project ID
- Use an RPOMS Supabase URL, database, storage bucket, or connection string
- Run any migration, query, or schema change against an RPOMS database
- Use or deploy to the RPOMS Vercel account or project
- Modify anything in an RPOMS repository

### ResearchForge must be completely independent:
| Resource | Requirement |
|---|---|
| GitHub repository | `tirukon015/researchforge` — its own repo |
| Supabase project | ResearchForge project only |
| Supabase credentials | ResearchForge keys only |
| Vercel project | ResearchForge project only |
| Environment variables | ResearchForge `.env` only |
| Database / storage | ResearchForge only |
| API keys | ResearchForge only |

### Mandatory pre-flight check
**Before ANY database or deployment operation**, print the target and get the
owner's confirmation:

- Before a migration → print the `SUPABASE_URL` **host** and confirm it is the
  ResearchForge project.
- Before a deploy → print the target Vercel project name and confirm.
- Before adding a git remote or pushing → print the remote URL and confirm it
  is `tirukon015/researchforge`.

**If the target cannot be verified, STOP and ask. Never guess.**

### Destructive SQL is forbidden
Migrations may contain `CREATE` and additive `ALTER` only.
**`DROP`, `TRUNCATE`, `DELETE FROM`, and any destructive schema change require
the owner's explicit, written, per-instance approval.**

---

## 7. Portability Rules

I must be able to continue this project from **Mac, Windows, or Linux**.

- **No hard-coded absolute paths.** Never write `/Users/apple/...` into code.
- Build paths with `pathlib.Path` (Python) or `path.join` (Node).
- Reference files **relative to the project root**, not the user's home dir.
- No Mac-only shell commands in scripts that the app depends on.
- No OS-specific line endings assumptions.
- All dependencies must be declared in `requirements.txt` / `package.json`
  so a fresh machine can reproduce the environment.
- Setup instructions in `README.md` must work on all three operating systems.

---

## 8. Git & GitHub Rules

- **GitHub is the source of truth** for the codebase.
- Commit in small, logical units with clear messages.
- Commit message style: `type: short description`
  (`feat:`, `fix:`, `docs:`, `chore:`, `test:`, `refactor:`)
- Never commit: `.env`, `node_modules/`, `venv/`, model weights, uploaded PDFs.
- Never force-push shared branches.
- Only commit or push when I ask.

---

## 9. Technology Stack (agreed baseline)

| Layer | Technology |
|---|---|
| Frontend | Next.js + TypeScript + React + Tailwind CSS |
| Backend / AI | Python + FastAPI |
| Database | Supabase PostgreSQL |
| Vector search | pgvector |
| Frontend hosting | Vercel |
| Backend hosting | Cloud host (TBD) |
| LLM | API-based (**provider not yet chosen**) |
| Embeddings | API or model (**not yet chosen**) |

**Do not install or commit to a specific AI provider or model until I approve
it.** Present the options and trade-offs first.

---

## 10. Repository Layout & Folder Responsibilities (APPROVED — decision D3)

**Project / repository name:** `researchforge`
(lowercase, hyphenated — no spaces, no parentheses. Portable across
Mac / Windows / Linux and safe in shell scripts, Docker, and URLs.)

The lecturer-required folder structure is **kept intact**. The table below
records the agreed responsibility of each folder. **This mapping is approved
and must not be changed without the owner's permission.**

```
researchforge/
├── data/         ├── notebooks/       ├── src/       ├── app/
├── models/       ├── docs/            ├── results/   ├── tests/
├── README.md     ├── PROJECT_PLAN.md  ├── CLAUDE.md
├── LICENSE       ├── requirements.txt └── .gitignore
```

| Folder | Owns | Language | Contains | In Git? |
|---|---|---|---|---|
| **`src/`** | **Python / AI backend** | Python | FastAPI app, RAG pipeline, ingestion, chunking, embedding, retrieval, prompts, evaluation scripts | ✅ Yes |
| **`app/`** | **Next.js frontend** | TypeScript | React pages, components, Tailwind styles, typed API client | ✅ Yes |
| **`data/`** | Papers & derived text | — | `raw/` uploaded PDFs · `processed/` extracted text · `samples/` real open-licence test papers | ⚠️ Partial |
| **`notebooks/`** | Experiments | Python | Jupyter prototyping, before code is moved into `src/` | ✅ Yes |
| **`models/`** | Model configuration | — | Model settings and prompt versions. **Weights are git-ignored** (far too large for Git). | ⚠️ Config only |
| **`docs/`** | Documentation | Markdown | Architecture, schema, decision log, deployment guide, demo script | ✅ Yes |
| **`results/`** | Evaluation outputs | — | **REAL measured results only.** Never fabricated. See §5. | ✅ Yes |
| **`tests/`** | Automated tests | Python / TS | pytest for backend, Vitest for frontend | ✅ Yes |

### Why `src/` = backend and `app/` = frontend
- `src/` holds the **graded core** of the project. This is an *AI* assignment,
  so the AI/RAG code belongs in the conventional source folder, where an
  examiner will look for it first.
- `app/` holds the **application** the user interacts with — the deliverable
  named in university requirement #5 ("Research Assistant Application").
- Inside `app/`, Next.js uses its own `src/app/` App Router directory. That is
  standard Next.js convention and does **not** conflict with the top-level
  `src/`; they are separate scopes.

### Planned internal structure of `src/` (built incrementally, not all at once)
```
src/
├── main.py              # FastAPI entry point
├── config.py            # settings loaded from environment variables
├── api/                 # HTTP route handlers
├── ingestion/           # PDF extraction, cleaning, chunking
├── rag/                 # embedding, retrieval, prompt building, generation
├── db/                  # database models, queries, migrations
├── prompts/             # versioned prompt templates
└── evaluation/          # real evaluation scripts (never fake output)
```

---

## 11. Code Quality Rules

- Python: type hints on public functions, docstrings on modules and services.
- TypeScript: `strict` mode on. Avoid `any`.
- Keep AI prompts in dedicated, version-controlled prompt files — not scattered
  inline strings — so they can be reviewed and improved.
- Validate all API input with Pydantic (backend) and Zod or equivalent (frontend).
- Handle errors explicitly. Never swallow an exception silently.
- Comment the *why*, not the *what*.

---

## 12. AI-Specific Rules

- **Every generated claim must be grounded in retrieved source text.**
  Summaries, gap analyses, and literature reviews must cite the paper and
  section they came from.
- If the retrieval step finds nothing relevant, the system must say
  *"insufficient evidence"* — it must **not** invent an answer.
- Log token usage and cost so the project stays affordable.
- Prompts are project assets: store them, version them, document changes.

---

## 13. Definition of Done (applies to every milestone)

A milestone is complete only when **all** of these are true:

1. The code runs without errors on a clean environment.
2. It has been **actually tested** — and the test output was shown to me.
3. No secrets are committed.
4. No hard-coded absolute paths.
5. No fake data or fake results.
6. Documentation is updated (`README.md` and/or `docs/`).
7. `PROJECT_PLAN.md` progress is updated.
8. I have been told plainly what works and what does not.

---

## 14. Current Status

- **Phase:** 1 — Environment & Foundations ✅ complete (2026-08-11)
- **Next phase:** 2 — Database Foundation (awaiting my approval)
- **Working:** Python 3.12.10 venv, FastAPI with `/health`, 9/9 tests passing
- **Still open:** LLM provider (D5), embedding model (D6), backend host (D7)
- **No external API connected yet. No database yet. No RAG built yet.**

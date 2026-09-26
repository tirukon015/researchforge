# Project Specification

The long-term functional specification of ResearchForge. **Read this first** before changing
anything. It describes what the application must keep doing. For *how* it is built, see
[ARCHITECTURE.md](ARCHITECTURE.md). For *what it looks like*, see
[DESIGN_SYSTEM.md](DESIGN_SYSTEM.md). For *where the code lives*, see
[COMPONENT_MAP.md](COMPONENT_MAP.md).

Baseline written 2026-09-26 against `main` at `7ca2528`. When something here stops being true,
update this file in the same change (see [MAINTENANCE.md](MAINTENANCE.md)).

---

## 1. Purpose

ResearchForge is an AI research-paper assistant. A signed-in user uploads **one academic PDF**
and receives three structured analyses, each **grounded only in that paper**:

1. **Summary**: research problem, methodology, key findings, conclusion.
2. **Research gaps**: stated limitations plus identified gaps, each carrying quoted evidence.
3. **Literature review**: the prior work *the paper itself* discusses.

Results can be saved to a private library, and two or more saved papers can be combined into
one cross-paper literature review. It is a university capstone (BIT4543) and a public
portfolio project. Live: `https://researchforge.rukon.dev`.

## 2. Routes

| Route | Access | Purpose |
|---|---|---|
| `/` | Public | Marketing landing page (`MarketingShell`) |
| `/sign-in`, `/sign-up`, `/forgot-password`, `/reset-password` | Public | Account flows (`authshell`, no nav) |
| `/auth/callback` | Public | Completes Google OAuth (PKCE) and password-reset links |
| `/dashboard` | Signed in | Upload, analyse, recent analysis, library stats |
| `/papers` | Signed in | My Papers: search, filter, sort, open, delete |
| `/papers/[id]` | Signed in | One saved paper and its analysis |
| `/workspace` | Signed in | Select papers for a cross-paper review |
| `/literature-review` | Signed in | Generate/read a cross-paper review; single-paper review of the current visit |
| `/settings` | Signed in | Account, password, sign-out, theme, owner-only AI configuration |
| `GET /health`, `GET /` (API) | Public | Backend liveness and capability flags |
| `/api/*` | Bearer token | Analysis, library, reviews, owner config (see `API.md`) |

Signed-in routes render inside `AppShell` → `TopNav` + `AuthGate` + `Footer`. `AuthGate`
redirects anonymous visitors to `/sign-in?next=…`. It is **UX only**; security is enforced
by the API and Postgres RLS.

## 3. Major functionality and required behaviour

### Upload and analysis
- PDF only, **25 MB** max, checked in the browser *and* on the server. The server checks the
  real byte count and the `%PDF` signature.
- Encrypted PDFs: one empty-password attempt, then **422**. Under 200 usable characters is
  treated as a scanned PDF and gets **422**. There is no OCR.
- Papers ≤ 400,000 characters are analysed **whole**. Longer papers are chunked (40,000
  characters with 2,000 overlap) into digests (map-reduce).
- **Three separate, sequential, schema-constrained model calls.** Every reply is validated
  with Pydantic. Invalid output is **refused, never repaired**.
- A content-hash cache returns an identical earlier analysis with **no model call**. Only
  successful analyses are cached.
- Nothing is stored in the library until the user clicks **Save to library**.

### Grounding (must never regress)
- The system prompt requires every statement to come from the supplied paper and treats the
  paper as **data, never instructions**.
- Schemas carry `insufficient_evidence` fields; each research gap has a required `evidence`
  field.
- The UI shows scope notes ("only the prior work this paper discusses") and
  insufficient-evidence messages.

### AI providers
- Two providers: **Anthropic** (Claude) and **Groq** (Qwen 3.6 27B). The owner picks the
  **primary**, and the other is automatically the **fallback**. There is no "auto" option.
- Fallback happens **at most once per analysis**, and **only** for rate limits or transient
  failures (a whitelist). It never happens for bad PDFs, validation failures or missing keys.
- A provider switched off by the owner is never constructed.
- Every analysis records the provider and model that **actually** produced it,
  `fallback_used`, `processing_time_ms` and `cache_hit`.

### Library and reviews
- Every paper, analysis and review belongs to one account, enforced by **Postgres RLS**.
  Another user's row returns **404**.
- Cross-paper reviews read the **stored analyses** of 2 or more papers (not the PDFs) in one
  model call, and record which papers they used.
- Deleting a paper used by a saved review returns **409**.

### Error contract
401 · 404 · 409 · 413 · 422 · 429 (with `Retry-After` / `X-Quota-Exhausted`) · 502 · 503.
**No expected condition returns 500.** The frontend relies on these codes. Don't change them
without updating `app/src/lib/api.ts`.

## 4. Responsive behaviour

- Desktop-first layout, max content width **1180px** (`.page`).
- Top navigation collapses to a menu button at **≤ 900px**. The main breakpoints are 1100,
  980, 900, 640, 560 and 380px (see DESIGN_SYSTEM §7).
- Nothing may scroll the body horizontally. Wide content scrolls inside itself.
- Light, dark and system themes. The theme is applied before paint by `THEME_INIT_SCRIPT`,
  so there is no flash.
- `prefers-reduced-motion` disables the progress and spinner animations.

## 5. External integrations

| Service | Used for | Where |
|---|---|---|
| Supabase Auth | Sign-up/in, Google OAuth (PKCE), password reset, token verification | `app/src/lib/supabase.ts`, `src/api/auth.py` |
| Supabase Postgres (via PostgREST) | Library, cache, settings, RLS | `src/db/supabase.py` |
| Anthropic Messages API | Provider | `src/rag/llm/anthropic_provider.py` |
| Groq (OpenAI-compatible REST) | Provider | `src/rag/llm/groq_provider.py` |
| Vercel | Hosting: one project, two services | `vercel.json` |

**Not connected:** Jina embeddings (request builder only), pgvector retrieval, Supabase
Storage. **Retired:** Google Gemini.

## 6. Important constraints

- **Vercel function limit: 300 s.** A full analysis (three calls) must fit inside it.
- **One origin.** The frontend calls the API with a **relative path**, and
  `NEXT_PUBLIC_API_BASE_URL` is **unset in production**.
- **The Vercel project is not linked to GitHub.** Pushing does not deploy; use
  `vercel deploy --prod`.
- Tests must run **offline**, with providers faked and **no paid calls**.
- Secrets live in server env vars only. The service-role key must never appear in a
  `NEXT_PUBLIC_*` variable.
- Migrations are **additive only** (`CREATE`, `ADD COLUMN IF NOT EXISTS`). Destructive SQL
  requires the owner's written approval.
- The embedding dimension is **locked at 1024** (column type). Changing it means re-embedding.

## 7. Must not be changed accidentally

1. The **grounding contract** (prompt wording rules, `insufficient_evidence`, required
   `evidence`, refuse-don't-repair).
2. **Data requests run as the user** (anon key + user JWT). Never switch data access to the
   service-role key; that makes every RLS policy inert.
3. The **fallback whitelist** and "one switch per analysis".
4. The **status-code contract** in §3.
5. **Same-origin API calls** and the `vercel.json` rewrites.
6. `require_user` **before** reading the upload in `/api/analyze`.
7. The PKCE flow type in `lib/supabase.ts`.
8. Honest labelling: this is **not RAG**. Don't describe it as retrieval-augmented until
   retrieval exists.

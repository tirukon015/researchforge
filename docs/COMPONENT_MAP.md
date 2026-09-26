# Component Map

Where things live, and what uses them. Use this to find the right file without reading the
whole codebase. Paths are relative to the repo root. Verified 2026-09-26.

---

## Frontend: `app/src/`

### Root and shells

| File | Role | Used by |
|---|---|---|
| `app/layout.tsx` (server) | HTML shell, metadata, `THEME_INIT_SCRIPT`, providers: `ThemeProvider` → `AuthProvider` → `SessionProvider` → `SelectionProvider` → `AppShell` | every route |
| `components/AppShell.tsx` | Picks the frame by path: **auth routes** → `.authshell`; **`/`** → `MarketingShell`; **everything else** → `TopNav` + `AuthGate` + `Footer`. Also exports `isAuthRoute`, `isPublicRoute` | `layout.tsx` |
| `components/MarketingShell.tsx` | Landing header (nav, theme, CTAs) and landing footer | `AppShell` |
| `components/TopNav.tsx` | App header: brand, route links, theme, `AccountMenu`, mobile menu | `AppShell` |
| `components/AccountMenu.tsx` | Avatar/name dropdown, sign-out | `TopNav` |
| `components/AuthGate.tsx` | Redirects anonymous users to `/sign-in?next=`; shows loading and unconfigured states. **UX only** | `AppShell` |
| `components/Footer.tsx` | App footer | `AppShell` |
| `components/ResearchBackdrop.tsx` | Faint decorative background | `AppShell` |

### Pages (`app/<route>/page.tsx`)

| Route | Main components |
|---|---|
| `/` (server) | `HeroVisual`, `Icons` |
| `/sign-in`, `/sign-up` | `AuthCard`, `GoogleButton` |
| `/forgot-password`, `/reset-password`, `/auth/callback` | `AuthCard` |
| `/dashboard` | `UploadPanel`, `ResultsView`, `BackendStatus`, `EmptyState` |
| `/papers` | `LibraryUI` |
| `/papers/[id]` | `LibraryUI`, `AnalysisSections`, `EmptyState` |
| `/workspace` | `LibraryUI`, `EmptyState` |
| `/literature-review` | `LibraryUI`, `AnalysisSections`, `EmptyState` |
| `/settings` | `AccountSettings`, `OwnerAiSettings`, `BackendStatus`, `ThemeToggle` |

Each protected route has a small **server** `layout.tsx` that exports `metadata` only. The
pages themselves are client components.

### Reusable components

| Component | Purpose | Used in |
|---|---|---|
| `Icons.tsx` | All inline SVG icons (the only icon source) | 18 files |
| `AuthCard.tsx` | Card frame and fields for account screens | 5 auth routes, `AccountSettings` |
| `EmptyState.tsx` | Standard empty/explanatory state | dashboard, papers/[id], workspace, literature-review, `LibraryUI` |
| `LibraryUI.tsx` | Library toolbar (search/filter/sort), paper cards with selection checkbox | papers, papers/[id], workspace, literature-review |
| `AnalysisSections.tsx` | Renders Summary / Gaps / Literature Review / Paper info blocks | `ResultsView`, papers/[id], literature-review |
| `ResultsView.tsx` | Tabbed result card with provenance badges | dashboard |
| `SavePaperButton.tsx` | Save an analysis to the library | `ResultsView` |
| `CopyButton.tsx` | Copy a section to the clipboard | `AnalysisSections` |
| `UploadPanel.tsx` | Drop zone, file checks, analyse, progress, error mapping | dashboard |
| `BackendStatus.tsx` | Pill reading real `/health` | dashboard, settings |
| `ThemeToggle.tsx` | Light / Dark / System segmented control | `TopNav`, `MarketingShell`, settings |
| `GoogleButton.tsx` | "Continue with Google" (PKCE) | sign-in, sign-up |
| `AccountSettings.tsx` | Name, password, sign-out | settings |
| `OwnerAiSettings.tsx` | Owner-only primary provider + availability | settings |
| `HeroVisual.tsx` | Illustrative (not real) analysis panel on the landing page | `/` |

### Client state and services (`app/src/lib/`)

| File | Exports | Notes |
|---|---|---|
| `api.ts` | `checkHealth`, `analyzePaper`, `setTokenReader`, `savePaper`, `listPapers`, `getPaper`, `deletePaper`, `getLibraryStats`, `createCrossReview`, `listReviews`*, `deleteReview`*, `getOwnerStatus`, `getAiConfig`, `setAiConfig`, `API_BASE_URL` | Typed client; attaches the bearer token; maps status codes to messages. *Defined but unused by any screen |
| `auth.tsx` | `AuthProvider`, `useAuth`, `rememberDestination`, `takeDestination`, `humanError`, `isValidEmail`, `passwordProblem`, `MIN_PASSWORD_LENGTH` (8) | Auth state machine: loading / anonymous / signed-in / unconfigured |
| `session.tsx` | `SessionProvider`, `useSession`, `sessionStats` | The current visit's unsaved analyses |
| `library.tsx` | `useLibrary`, `usePaper`, `useMostRecentPaper`, `useLibraryStats`, `SelectionProvider`, `useSelection`, `formatSize`, `formatDate` | Selection is **in memory only**; lost on reload |
| `supabase.ts` | `getSupabase` (lazy, PKCE), `isAuthConfigured`, `authRedirectUrl`, `isSafeReturnPath` | Auth only; never reads data. Has Vitest tests |
| `theme.tsx` | `ThemeProvider`, `useTheme`, `THEME_INIT_SCRIPT` | No-flash theme |

Styles: `app/src/app/globals.css` (see DESIGN_SYSTEM.md). Brand images: `app/public/brand/`.

---

## Backend: `src/`

| Module | Role |
|---|---|
| `main.py` | FastAPI app, CORS, `/`, `/health`, router wiring |
| `config.py` | `Settings` (pydantic-settings); **every env var is read here** |
| `api/auth.py` | `require_user`: verifies the bearer token with Supabase `/auth/v1/user`, 5 s cache |
| `api/analyze.py` | `POST /api/analyze`; `get_provider` dependency (per-request router) |
| `api/papers.py` | `/api/papers` CRUD + stats; `get_library` dependency |
| `api/reviews.py` | `/api/reviews` cross-paper create/list/get/delete |
| `api/owner.py` | `/api/owner/status`, `/api/owner/ai-config` |
| `services/analysis.py` | `analyse_paper`: whole-document or map-reduce, then 3 structured calls |
| `services/cross_review.py` | Builds the multi-paper prompt from stored analyses |
| `services/content_hash.py` | SHA-256 of normalised text, `ANALYSIS_VERSION` |
| `ingestion/pdf.py` | Validate, extract (pypdf), clean; `MIN_USABLE_CHARS = 200` |
| `ingestion/chunking.py` | `needs_chunking`, `chunk_text` (map step only) |
| `prompts/analysis.py` | All prompts; `PROMPT_VERSION` |
| `schemas/analysis.py`, `schemas/library.py` | Pydantic request/response and output models |
| `rag/llm/base.py` | `LLMProvider` interface and error types |
| `rag/llm/router.py` | `RoutedLLMProvider`, `is_retryable`, `PROVIDERS`, `DISPLAY_NAMES` |
| `rag/llm/__init__.py` | `build_routed_provider` factory |
| `rag/llm/anthropic_provider.py`, `groq_provider.py` | Active vendors |
| `rag/llm/gemini_provider.py` | **Retired**; kept for historical rows |
| `rag/embeddings/base.py`, `jina.py` | **Unused scaffolding** (no HTTP call) |
| `db/supabase.py` | PostgREST repository **as the user**; per-migration column degradation; publishable-key guard |
| `db/repository.py` | `PaperRepository` interface, errors, `get_repository` |
| `db/analysis_cache.py` | Content-hash cache (fail-open) |
| `db/migrations/001–006` | Additive SQL, run manually in the Supabase SQL editor |

## Tests: `tests/`

One file per area: `test_auth`, `test_analysis`, `test_analysis_cache`, `test_library`,
`test_ownership`, `test_owner`, `test_router`, `test_llm_providers`, `test_groq_provider`,
`test_rate_limit`, `test_provider_availability`, `test_supabase_repository`,
`test_key_type_guard`, `test_content_hash`, `test_embeddings`, `test_main`, and
`test_provider_smoke` (live, opt-in). Fixtures: `auth_fixtures.py`, `pdf_fixtures.py`.
Frontend: `app/src/lib/supabase.test.ts`.

# Features

The living list of what ResearchForge does. **Update it in the same change whenever a feature
is added, removed or changed.** Statuses: **Live** (in production) · **Built, not wired**
(code exists, no user path) · **Planned** · **Retired**.

Last verified: 2026-09-26 (production and `main` at `7ca2528`).

## Accounts and access
| Feature | Status | Where |
|---|---|---|
| Public landing page | Live | `/`, `MarketingShell`, `HeroVisual` |
| Email + password sign-up / sign-in | Live | `/sign-up`, `/sign-in`, `lib/auth.tsx` |
| Forgot / reset password | Live | `/forgot-password`, `/reset-password`, `/auth/callback` |
| Google sign-in (PKCE) | Live | `GoogleButton`, `/auth/callback` |
| Return to the intended page after sign-in (`?next=`, open-redirect safe) | Live | `AuthGate`, `lib/supabase.ts::isSafeReturnPath` (Vitest) |
| Account settings: name, password change, sign-out | Live | `AccountSettings` |
| Route guard for app pages | Live | `AuthGate` (UX only) |

## Analysis
| Feature | Status | Where |
|---|---|---|
| PDF upload (drag and drop or picker), 25 MB, type/empty checks | Live | `UploadPanel`, `api/analyze.py` |
| Server-side signature, encryption and scanned-PDF rejection | Live | `ingestion/pdf.py` |
| Summary, research gaps (with evidence), literature review | Live | `services/analysis.py`, `AnalysisSections` |
| Insufficient-evidence reporting | Live | schemas + UI |
| Long-paper map-reduce (>400k chars) | Live (unit-tested; not seen in production use) | `ingestion/chunking.py` |
| Honest progress display with elapsed time | Live | `UploadPanel` |
| Rate-limit handling with `Retry-After` countdown | Live | `api/analyze.py`, `lib/api.ts` |
| Content-hash reuse of identical analyses | Live | `db/analysis_cache.py` |
| Provenance badges (provider, fallback, model) | Live | `ResultsView` |
| Copy any section | Live | `CopyButton` |

## AI configuration
| Feature | Status | Where |
|---|---|---|
| Two providers (Claude, Groq Qwen 3.6 27B), owner-chosen primary, automatic fallback | Live (production: Groq primary) | `rag/llm/router.py`, `OwnerAiSettings` |
| Per-provider on/off | Live | migration 006, `api/owner.py` |
| Gemini provider | Retired | `gemini_provider.py` |

## Library and reviews
| Feature | Status | Where |
|---|---|---|
| Save analysis to a private library | Live | `SavePaperButton`, `api/papers.py` |
| My Papers: search, status filter, sort, open, delete | Live | `/papers`, `LibraryUI` |
| Paper detail with tabs and measured document facts | Live | `/papers/[id]` |
| Library stats on the dashboard | Live | `useLibraryStats` |
| Per-user isolation by Postgres RLS | Live | migrations 002–003, `db/supabase.py` |
| Workspace selection for cross-paper review | Live | `/workspace`, `useSelection` |
| Cross-paper literature review | Live | `/literature-review`, `api/reviews.py` |
| List / reopen saved cross-paper reviews | **Built, not wired**: API + `listReviews()` exist; no screen | `lib/api.ts` |

## Interface
| Feature | Status | Where |
|---|---|---|
| Light / Dark / System theme, no flash | Live | `lib/theme.tsx`, `ThemeToggle` |
| Responsive layout, mobile menu | Live | `globals.css`, `TopNav` |
| Backend status pill | Live | `BackendStatus` |
| Decorative research backdrop | Live | `ResearchBackdrop` |

## Not built
| Feature | Status |
|---|---|
| Embeddings / vector search / RAG | Planned (F3). Scaffolding only |
| Grounded Q&A chat | Planned (F8) |
| Page- or chunk-level citations | Planned (F9) |
| Export (Markdown / PDF / BibTeX) | Planned (F10, E4) |
| OCR for scanned PDFs | Not planned; scanned files are rejected |
| Bibliographic metadata extraction | Built, not wired (columns only) |
| Stored PDF files | Built, not wired (`storage_path` unused) |
| Application-level rate limiting | Planned |

## Known copy/content defects
- The dashboard "How ResearchForge works" card says the paper goes to **Gemini**. It should
  name the configured providers.

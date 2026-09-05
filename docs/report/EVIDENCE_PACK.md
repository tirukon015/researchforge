# ResearchForge — Evidence Pack

**BIT 4543 Artificial Intelligence · Project #17**

Everything an examiner needs to check a claim in the report against the thing
that produced it. No number in this pack was typed by hand; each traces to a
file in `results/` or to a command that can be re-run.

Companion documents: `PROJECT_REPORT.md` · `DIAGRAMS.md` · `SLIDES.md` ·
`SPEAKING_SCRIPT.md` · `POSTER.md`

---

## 1. Requirements Traceability

### University requirements

| # | Requirement | Implemented in | Verified by | Evidence |
|---|---|---|---|---|
| 1 | Upload research papers | `src/api/analyze.py`, `/dashboard` | 15 live uploads across 3 passes | `results/evaluation/runs.json` |
| 2 | Generate summaries | `src/prompts/analysis.py`, `src/services/analysis.py` | 10 summaries, median 8 key findings | `results/evaluation/raw/*.json` |
| 3 | Identify research gaps | same | 10 gap analyses, median 9 gaps | `results/evaluation/summary.txt` |
| 4 | Produce literature reviews | `src/services/cross_review.py`, `/literature-review` | 10 reviews; cross-paper review verified live | `results/evaluation/isolation_test.txt` §7 |
| 5 | Research Assistant Application | `app/` — 12 routed pages | Deployed and reachable | `researchforge.rukon.dev/health` |

### Project objectives

| # | Objective | Enforced by | Verified by | Evidence |
|---|---|---|---|---|
| 1 | Structured, grounded outputs | Three-pass pipeline | 10 complete analyses | `raw/*.json` |
| 2 | Grounding enforced structurally | Schema-constrained generation; discard-on-mismatch | 49 + 30 provider tests | `tests/test_llm_providers.py`, `test_groq_provider.py` |
| 3 | Two providers, fallback, availability | `src/rag/llm/router.py`, `__init__.py` | 36 + 30 tests; 5/5 live fallbacks; pass C proves a disabled provider is unreachable | `test_router.py`, `test_provider_availability.py`, `runs.json` |
| 4 | Database-enforced isolation | RLS + per-user access token | **26 live checks, 0 failures** | `results/evaluation/isolation_test.txt` |
| 5 | No redundant computation | `src/services/content_hash.py`, `src/db/analysis_cache.py` | 30 + 22 tests; 4-signal live test | `results/evaluation/cache_test.txt` |
| 6 | Empirical evaluation | 3 passes over 5 real papers | Partially met — see §4 | `results/evaluation/summary.txt` |

---

## 2. Dataset Documentation

**Five real, openly available arXiv papers.** No paper was written for this
project; no PDF was modified. Metadata was fetched from the arXiv API rather
than transcribed.

| arXiv ID | Title | Year | Authors | Pages | Bytes |
|---|---|---|---|---|---|
| 1706.03762 | Attention Is All You Need | 2017 | 8 | 15 | 2,215,244 |
| 1810.04805 | BERT: Pre-training of Deep Bidirectional Transformers | 2018 | 4 | 16 | 775,166 |
| 1903.10676 | SciBERT: A Pretrained Language Model for Scientific Text | 2019 | 3 | 6 | 120,281 |
| 2004.04228 | Asking and Answering Questions to Evaluate Factual Consistency | 2020 | 3 | 13 | 1,182,348 |
| 2005.11401 | Retrieval-Augmented Generation for Knowledge-Intensive NLP | 2020 | 12 | 19 | 885,323 |

Full manifest with DOIs, URLs, licences and dates: `data/dataset_manifest.csv`.
PDFs: `data/samples/`.

**Selection rationale.** Influential NLP papers a student might genuinely
upload, varying in length (6–19 pages), age (2017–2020), and author count
(3–12). **Selection bias is acknowledged:** all five are arXiv cs.CL,
English-language, well-structured, and born-digital. Nothing here establishes
behaviour on scanned documents, other disciplines, or other languages.

---

## 3. Preprocessing

Extraction happens **before** any model is called, so these figures are
properties of the corpus, not of a provider.

| Paper | Pages | Characters | Chars/page | Chunks | Truncated |
|---|---|---|---|---|---|
| 1706.03762 | 15 | 39,489 | 2,632 | 1 | No |
| 1810.04805 | 16 | 63,578 | 3,973 | 1 | No |
| 1903.10676 | 6 | 23,767 | 3,961 | 1 | No |
| 2004.04228 | 13 | 46,601 | 3,584 | 1 | No |
| 2005.11401 | 19 | 69,097 | 3,636 | 1 | No |

**Pipeline:** `pypdf` text extraction → reject if no extractable text (HTTP 422)
→ NFKC Unicode normalisation → SHA-256 over normalised text + `ANALYSIS_VERSION`
→ whole document into context.

**Three consequences worth noting.**

1. **Consistent yield (2,632–3,973 chars/page)** indicates the extractor handled
   two-column academic layout without dropping content.
2. **No paper required chunking or truncation.** Every one fitted in a single
   context window. This is the empirical basis for not building retrieval —
   `chunk_text` exists only as a size guard above 400,000 characters and was
   never invoked.
3. **Identity is content, not filename.** `paper.pdf` and `final_v3.pdf` are the
   same document if the text matches. This is what makes the cache correct, and
   it is also what caused two measurement errors (§5).

---

## 4. Test-Case Table

### Automated suite — 538 passing, 0 failing

Command: `python -m pytest -q` and `npx vitest run`.

```
522 passed, 5 skipped, 1 warning in 6.32s     (backend)
 16 passed                                     (frontend)
```

The 5 skipped are opt-in live-provider tests, skipped by design; they run only
with `RESEARCHFORGE_LIVE_PROVIDER_TEST=1` and a real key. **No test in the suite
calls a paid API** — every provider is faked, so the suite is offline, free, and
deterministic.

| Module | Tests | Protects |
|---|---|---|
| `test_auth.py` | 61 | Token verification, expiry, malformed and absent credentials |
| `test_llm_providers.py` | 49 | Provider behaviour, error translation, schema validation |
| `test_supabase_repository.py` | 48 | Every database access path |
| `test_rate_limit.py` | 42 | Rate-limit handling and retry discipline |
| `test_router.py` | 36 | Primary/fallback routing, retryable whitelist |
| `test_library.py` | 35 | Library reads and writes |
| `test_analysis.py` | 31 | The three-pass pipeline |
| `test_provider_availability.py` | 30 | A disabled provider is never constructed |
| `test_groq_provider.py` | 30 | Groq client and JSON validation |
| `test_content_hash.py` | 30 | Normalisation and cache identity |
| `test_embeddings.py` | 29 | Unused embedding scaffolding |
| `test_owner.py` | 28 | Owner-only configuration endpoints |
| `test_key_type_guard.py` | 22 | Publishable-key-in-private-slot guard |
| `test_analysis_cache.py` | 22 | Cache correctness and versioning |
| `test_ownership.py` | 20 | Caller identity carried through faithfully |
| `test_main.py` | 9 | Application wiring and health |
| `test_provider_smoke.py` | 5 | Live provider calls (opt-in, skipped) |

### Live system tests

| ID | Test | Expected | Result | Evidence |
|---|---|---|---|---|
| L1 | Protected routes without a token | 401 | Pass | `isolation_test.txt` §1 |
| L2 | New user's library is empty | 0 papers | Pass | §2 |
| L3 | User B reads User A's paper by id | 404 (not 403) | Pass | §3 |
| L4 | User B deletes User A's paper | 404 | Pass | §3 |
| L5 | Dashboard counts are per account | own work only | Pass | §6 |
| L6 | User B adds User A's paper to a review | 404 | Pass | §7 |
| L7 | Direct PostgREST with the browser key | **0 rows** | Pass | §8 |
| L8 | Signed-out token after cache expiry | 401 | Pass | §9 |
| L9 | Sign-out window is bounded | refused by ~6 s | Pass — 6.1 s | `logout_window.txt` |
| L10 | First upload is a cache miss | `cache_hit=false`, model called | Pass — 32.4 s | `cache_test.txt` §4 |
| L11 | Repeat upload is a hit | `cache_hit=true`, no model call | Pass — 3.2 s | §5 |
| L12 | Different user gets the hit, no leakage | hit, nothing about User A | Pass — 2.7 s | §6 |
| L13 | `processing_time_ms` is the original | 29,823 unchanged | Pass | §5 |
| L14 | `hit_count` increments | +1 per hit | Pass | §5 |

**Totals: 26 isolation checks passed / 0 failed; cache test fully passing.**

### Provider evaluation

| ID | Test | Result | Evidence |
|---|---|---|---|
| P1 | Claude primary, 5 papers | 5/5 by Claude | `runs.json` pass A |
| P2 | Groq primary, both enabled | 5/5 completed, **0/5 by Groq** | pass B |
| P3 | Groq only, Claude disabled | **0/5** | pass C |
| P4 | Groq token requirement vs limit | every paper 1.1×–2.9× over | `groq_capacity.json` |
| P5 | Disabled provider is unreachable | confirmed — no fallback occurred in pass C | pass C |

---

## 5. Measurement Errors Found and Corrected

Recorded because each produced a plausible-looking wrong number. An evaluation
that reports only its successes is not evidence of care.

| # | Error | How it would have misled | Correction |
|---|---|---|---|
| 1 | Cloudflare replaced provider errors with `error code: 502` | Every failure looked identical and gave no cause; the ITPM limit was invisible | Address the Vercel origin directly |
| 2 | A cache hit read as a Groq success | Two papers returned HTTP 200 under Groq-only — but Claude had just analysed them and the cache is keyed by content | Clear cache rows before measuring |
| 3 | The cache test's own fixture was cached from a prior run | The "first upload" was a hit, so every downstream assertion failed | The test now clears its own fixture row |
| 4 | Two transient 502s read as systematic failures | Pass B would have been reported as 3/5 | Re-ran both under the identical configuration; both completed |
| 5 | The isolation test asserted instant logout | Reported a security failure that did not exist — it re-checked at 2 s against a 5 s cache | Measured the real window (6.1 s); test now asserts the actual contract |

Errors 2 and 3 have the same root cause — a cache keyed by content — which is
why the report labours the point.

---

## 6. Reproducing the Evaluation

```bash
# Automated suite (offline, free, deterministic)
python -m pytest -q
cd app && npx vitest run
```

Live evaluation requires the production service-role key and touches real
provider quota. Three requirements, each corresponding to a mistake in §5:

1. **Group by `actual_provider`, never `configured_provider`.**
2. **Clear `analysis_cache` rows for the corpus before each pass**, or the
   second pass is served the first pass's answer.
3. **Address `researchforge-ten.vercel.app`, not the custom domain**, or
   Cloudflare replaces provider error messages.

Aggregation is `results/evaluation/summary.txt`, regenerated from
`runs_*.json` and `groq_capacity.json`.

---

## 7. Artefact Index

| File | Contents |
|---|---|
| `data/dataset_manifest.csv` | The five papers, metadata from the arXiv API |
| `data/samples/*.pdf` | Unmodified source PDFs |
| `results/evaluation/raw/*.json` | Every analysis response as returned |
| `results/evaluation/runs_*.json` | One record per run, per pass |
| `results/evaluation/runs.json` | All runs merged, labelled by pass |
| `results/evaluation/groq_capacity.json` | Groq's own token-limit refusals |
| `results/evaluation/summary.txt` | Aggregated tables used in Chapter 5 |
| `results/evaluation/isolation_test.txt` | 26 passed, 0 failed |
| `results/evaluation/cache_test.txt` | Four-signal cache verification |
| `results/evaluation/logout_window.txt` | Measured sign-out window |
| `src/db/migrations/00*.sql` | Six additive migrations |
| `docs/report/DIAGRAMS.md` | Seven diagrams (conceptual, architecture, pipeline, routing, use case, activity, ERD) |

---

## 8. Screenshot Checklist

Screenshots are the one part of this pack that must be captured by hand. Take
each at **1440 × 900 or wider**, in light mode, signed in as a normal (non-owner)
account except where noted. Save to `docs/report/screenshots/`.

| # | File | Screen | Shows |
|---|---|---|---|
| 1 | `01-landing.png` | `/` signed out | Public landing page |
| 2 | `02-signup.png` | `/sign-up` | Account creation |
| 3 | `03-dashboard-empty.png` | `/dashboard`, new account | **Empty library — Requirement 4 visible** |
| 4 | `04-upload.png` | `/dashboard` mid-upload | Upload in progress |
| 5 | `05-summary.png` | `/papers/[id]` | Summary with key findings — **Req. 2** |
| 6 | `06-gaps.png` | `/papers/[id]` gaps section | Research gaps — **Req. 3** |
| 7 | `07-review.png` | `/literature-review` | Cross-paper review — **Req. 4** |
| 8 | `08-library.png` | `/papers` | Private library — **Req. 1** |
| 9 | `09-settings-account.png` | `/settings` | Account settings |
| 10 | `10-settings-ai.png` | `/settings` **as owner** | Provider selection and availability — **Obj. 3** |
| 11 | `11-cache-hit.png` | Re-upload of an analysed paper | Fast return — **Obj. 5** |
| 12 | `12-mobile.png` | `/dashboard` at 390 px | Responsive layout |

**Do not** screenshot anything showing an API key, a token, a `.env` file, or a
real email address other than a throwaway test account.

---

## 9. Assessment Component Traceability

The project brief allocates 100 marks across eight components. Each row states
where the evidence is and what, if anything, is still missing. Rows are marked
*Complete* only where the evidence exists and has been verified.

| Component | Marks | Evidence | Gaps / risks | Status |
|---|---|---|---|---|
| Proposal | 10 | `PROJECT_PLAN.md` — problem, solution, architecture, 13-milestone roadmap, decision log; report §1.1–1.5 | None | Complete |
| Dataset & Preparation | 10 | `data/dataset_manifest.csv` (arXiv API metadata), `data/samples/` (5 unmodified PDFs), report §3.3–3.4, Appendix C; extraction figures in §5.4 | Corpus is 5 papers from one arXiv category; bias stated in §5.4 | Complete |
| AI Model Implementation | 25 | Report §3.5, §4.6, Appendix B; provider selection, prompt construction, schema-constrained generation, discard-on-mismatch, routing, fallback, provenance | The insufficient-evidence path is unit-tested but was never triggered by the corpus (§5.4) | Complete |
| Application Development | 20 | Deployed at researchforge.rukon.dev; 12 routed pages; report §4.1–4.6; `/health` returns `library: true, auth: true` | Screenshots must be captured by hand (§8) | Complete |
| Testing & Evaluation | 10 | 538 automated tests passing; 22 documented test cases (§4); live isolation, cache and logout runs in `results/evaluation/` | No ground-truth grading; stated as the primary limitation | Complete |
| GitHub Repository Quality | 10 | `github.com/tirukon015/researchforge`; `CLAUDE.md`, `PROJECT_PLAN.md`, `README.md`, `docs/` (14 documents), additive-only migrations, `.env.example` with placeholders only | Final commit and push of the report and evaluation artefacts is outstanding | Outstanding action |
| Final Report | 10 | `ResearchForge_Report.docx` — Chapters 1–7 in the lecturer's structure, 10,535 words (limit 8,000–12,000), APA 7th references, Appendices A–D | Names, student IDs and submission date are placeholders; TOC must be generated in Word; diagram images must be rendered | Outstanding action |
| Presentation & Demo | 5 | `ResearchForge_Slides.pptx` (14 slides), `ResearchForge_Speaking_Script.docx` (timed to 20 minutes, with anticipated questions and demo notes) | Not yet rehearsed against a clock | Complete |

### The five submission components

| # | Component | Requirement | Delivered | Status |
|---|---|---|---|---|
| 1 | Project Report | Chapters 1–7, 8,000–12,000 words | `ResearchForge_Report.docx` — 10,535 words, lecturer's exact structure | Met |
| 2 | System / App | Interface and database | Deployed; Next.js frontend, FastAPI backend, Supabase PostgreSQL with RLS | Met |
| 3 | Slides Presentation | Minimum 10 slides | `ResearchForge_Slides.pptx` — 14 slides | Met |
| 4 | Presentation | 20 minutes | `ResearchForge_Speaking_Script.docx` — timed per slide to 20:00, plus Q&A | Met |
| 5 | Poster / Infographic | — | `ResearchForge_Poster_A1.pptx` — A1 portrait, print-ready | Met |

### AI Model Implementation evidence (25-mark component)

The brief asks for explicit technical evidence on eleven points. Each is
answered in the report at the location given.

| # | Required evidence | Where |
|---|---|---|
| A | Why Claude was selected | §3.5 — schema-constrained parsing directly into a validated model |
| B | Why Groq/Qwen is the secondary provider | §3.5 — architectural independence and speed; §5.4 records that its free tier cannot serve a paper |
| C | How PDF text becomes model input | §4.3, §3.4 — pypdf extraction, NFKC normalisation, whole document in context |
| D | How prompts are constructed | §3.5, §4.6 — three versioned prompts in `src/prompts/analysis.py` |
| E | How the model produces each output | §4.3 — three separate grounded passes, not one combined prompt |
| F | How structured output is validated | §4.6, Appendix B.5 — Pydantic validation against a declared schema |
| G | How grounding is enforced | §4.6 — prompt, schema, validation, and an explicit insufficient-evidence field |
| H | How unsupported claims are minimised | §6.3 — discard-on-mismatch; output that does not conform is never displayed |
| I | How provider failure is handled | §4.6 — one sticky fallback, retryable failures only, via a whitelist |
| J | How fallback is recorded | §4.4 — `model_provider`, `model_used`, `fallback_used` stored per analysis |
| K | Remaining model limitations | §6.3 — grounding is not truth verification; no OCR; one discipline; no ground truth |

**Terminology.** The system performs **inference** against hosted foundation
models. No model is trained, fine-tuned, or otherwise fitted by this project,
and the report does not describe it as such.

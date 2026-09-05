@FRONTMATTER

# 1. PURPOSE OF THIS PACK

This pack lets an examiner check any claim in the final report against the thing
that produced it. Every figure traces to a file in the repository or to a
command that can be re-run.

Nothing in this pack was typed from memory. Where a value could not be measured,
the pack says so rather than estimating.

**Companion documents.** `ResearchForge_Final_Project_Report.docx` (Chapters 1
to 7, Appendices A to D), `ResearchForge_Final_Presentation.pptx` (15 slides)
and `ResearchForge_Final_Speaking_Script.docx`.

**Live system.** https://researchforge.rukon.dev
**Repository.** https://github.com/tirukon015/researchforge

@PAGEBREAK

# 2. REQUIREMENTS TRACEABILITY

## 2.1 University requirements

@TABLE|Table 1|The five required outcomes and where each is evidenced
| # | Required outcome | Implemented in | Evidence | Report |
|---|---|---|---|---|
| 1 | Allow users to upload research papers | Analyse endpoint, dashboard | 15 live uploads across three evaluation passes | §4.5, §4.11 |
| 2 | Generate summaries of research papers | First structured pass | 10 summaries, median 8 key findings | §4.12, Table 5.9 |
| 3 | Identify research gaps | Second structured pass | 10 gap analyses, median 9 gaps | §4.13, Table 5.9 |
| 4 | Produce literature reviews | Third pass and cross-review service | 10 reviews, median 8 themes; cross-paper review verified live | §4.14, §4.15 |
| 5 | Research assistant application | Next.js frontend, 15 routes | Deployed and publicly reachable | §4.5, Figures 4.4 to 4.11 |

## 2.2 Project objectives

@TABLE|Table 2|The ten project objectives, their evidence and outcome
| # | Objective (§1.3) | Evidence | Outcome |
|---|---|---|---|
| 1 | Upload research papers | 15 live uploads; Figure 4.5 | Achieved |
| 2 | Extract text from PDFs, rejecting documents without text | Table 5.7; HTTP 422 on scanned input | Achieved |
| 3 | Structured summaries and key findings | 10 summaries; Figure 4.6 | Achieved |
| 4 | Identify research gaps | 10 gap analyses; Figure 4.7 | Achieved |
| 5 | Generate literature review content | 10 reviews; Table 5.9 | Achieved |
| 6 | Cross-paper literature review | Verified live over two papers; Figure 4.8 | Achieved |
| 7 | Usable research assistant interface | 15 routes, responsive; Figures 4.4 to 4.11 | Achieved |
| 8 | Secure accounts and per-user ownership | 26 live checks, 0 failures; Table 5.3 | Achieved |
| 9 | Reduce duplicate AI processing | Table 5.5; 32.4 s to 3.2 s, no model call | Achieved |
| 10 | Owner-controlled AI provider configuration | Figure 4.10; disabled provider unreachable, Table 5.4 | Achieved in mechanism; see note |

**Note on objective 10.** The mechanism is implemented and verified: the owner
selects the primary provider, a disabled provider is never constructed, and the
fallback operates correctly. Its practical effect is limited because the
configured primary cannot process a full paper at its free service tier. That is
a limitation of the service tier, not of the implementation, and is analysed in
§5.14 and §6.6.

@PAGEBREAK

# 3. DATASET DOCUMENTATION

Five real, openly available arXiv papers form the evaluation corpus. No paper was
written for this project and no PDF was modified. Metadata was retrieved from the
arXiv application programming interface rather than transcribed by hand.

@TABLE|Table 3|Evaluation corpus with source and file details
| arXiv ID | Title | Year | Authors | Pages | File size |
|---|---|---|---|---|---|
| 1706.03762 | Attention Is All You Need | 2017 | 8 | 15 | 2,215,244 B |
| 1810.04805 | BERT: Pre-training of Deep Bidirectional Transformers | 2018 | 4 | 16 | 775,166 B |
| 1903.10676 | SciBERT: A Pretrained Language Model for Scientific Text | 2019 | 3 | 6 | 120,281 B |
| 2004.04228 | Asking and Answering Questions to Evaluate Factual Consistency | 2020 | 3 | 13 | 1,182,348 B |
| 2005.11401 | Retrieval-Augmented Generation for Knowledge-Intensive NLP | 2020 | 12 | 19 | 885,323 B |

**Manifest.** `data/dataset_manifest.csv` carries the full record for each paper:
identifier, title, authors, author count, year, publication date, source, primary
category, DOI, abstract URL, PDF URL, licence, local file path and file size.

**Files.** `data/samples/*.pdf`, unmodified.

**Licensing.** All five are arXiv open access; each paper's own licence line is
recorded in the manifest.

**Selection rationale.** Influential natural language processing papers a student
might genuinely upload, varying in length (6 to 19 pages), publication year (2017
to 2020) and author count (3 to 12).

**Selection bias, stated.** All five are English-language computational
linguistics papers from a single arXiv category, and all are born-digital with a
proper text layer. Nothing in this project establishes behaviour on scanned
documents, other disciplines or other languages.

**What this corpus is not.** It is evaluation data, not training data. No model
is trained or fine-tuned by this project, and there is no labelled
machine-learning dataset. The distinction is maintained in §3.4 of the report.

@PAGEBREAK

# 4. PREPROCESSING NOTES

## 4.1 Pipeline

Text extraction with pypdf, then rejection of any document yielding no usable
text (HTTP 422), then NFKC Unicode normalisation with whitespace collapsed, then
a SHA-256 hash over the normalised text combined with the analysis version. The
whole normalised document is then supplied to the model as context.

No feature engineering, missing-value imputation or numerical normalisation is
performed, because the system does not fit a statistical model. The preprocessing
that exists serves extraction quality and document identity.

## 4.2 Measured extraction results

@TABLE|Table 4|Extraction results across the corpus, identical for both providers
| Paper | Pages | Characters | Characters per page | Chunks | Truncated |
|---|---|---|---|---|---|
| 1706.03762 | 15 | 39,489 | 2,632 | 1 | No |
| 1810.04805 | 16 | 63,578 | 3,973 | 1 | No |
| 1903.10676 | 6 | 23,767 | 3,961 | 1 | No |
| 2004.04228 | 13 | 46,601 | 3,584 | 1 | No |
| 2005.11401 | 19 | 69,097 | 3,636 | 1 | No |

## 4.3 Three consequences

**Consistent yield.** Between 2,632 and 3,973 characters per page indicates the
extractor handled two-column academic layout without dropping content.

**No chunking or truncation was required.** Every paper fitted in a single model
context window. This is the empirical basis for the decision in §3.8 not to build
a vector retrieval pipeline: retrieval would have added a failure mode, in which
an incorrect retrieval silently degrades the answer, without solving a problem
the system had.

**Identity is content, not filename.** Normalisation before hashing means two
renderings of the same paper produce the same identity, which is what makes the
cache correct. It is also what caused two measurement errors during evaluation,
recorded in §7 of this pack.

@PAGEBREAK

# 5. TEST-CASE TABLE

## 5.1 Automated suite

Commands: `python -m pytest -q` and, in `app/`, `npx vitest run`.

Verified result on the current repository:

@CODE
522 passed, 5 skipped, 1 warning        (pytest, backend)
 16 passed                              (Vitest, frontend)
@ENDCODE

**538 tests pass, none fail.** The 5 skipped are opt-in live-provider tests that
cost tokens; they run only when `RESEARCHFORGE_LIVE_PROVIDER_TEST=1` is set with
a real key. No test in the suite calls a paid interface: every provider is
replaced by a fake, so the suite runs offline, free and deterministically.

Static checks, also verified: Ruff reports no issues and no formatting
differences across the application source and tests; the TypeScript compiler
reports no errors; the production build completes and produces 15 routes.

@TABLE|Table 5|Automated backend tests by module
| Module | Tests | What it protects |
|---|---|---|
| Authentication | 61 | Token verification, expiry, malformed and absent credentials |
| LLM providers | 49 | Provider behaviour, error translation, schema validation |
| Repository | 48 | Every database access path |
| Rate limiting | 42 | Rate-limit recognition and retry discipline |
| Provider router | 36 | Primary and fallback routing, retryable whitelist |
| Library | 35 | Library reads and writes |
| Analysis | 31 | The three-pass pipeline |
| Provider availability | 30 | A disabled provider is never constructed |
| Groq provider | 30 | Client behaviour and JSON validation |
| Content hash | 30 | Normalisation and cache identity |
| Embeddings | 29 | The unused embedding scaffolding |
| Owner configuration | 28 | Owner-only endpoints |
| Key type guard | 22 | A publishable key placed in a private slot |
| Analysis cache | 22 | Cache correctness and versioning |
| Ownership | 20 | Caller identity carried through faithfully |
| Application wiring | 9 | Startup, health and route registration |
| Live provider smoke tests | 5 | Live provider calls, opt-in and skipped |

## 5.2 Live system test cases

Executed against the deployed system and the production database. Evidence files
are named in §8.

@TABLE|Table 6|Live test cases, expected and actual results
| ID | Test case | Expected result | Actual result | Status |
|---|---|---|---|---|
| L1 | Access a protected route with no token | HTTP 401 | HTTP 401 | Pass |
| L2 | New account opens its library | Empty, no pre-existing papers | 0 papers | Pass |
| L3 | User A uploads a paper | Appears in User A library only | 1 paper, correct title | Pass |
| L4 | User B lists papers | User A paper absent | Absent | Pass |
| L5 | User B opens User A paper by identifier | HTTP 404, not 403 | HTTP 404 | Pass |
| L6 | User B deletes User A paper | HTTP 404, paper intact | HTTP 404 | Pass |
| L7 | User B searches for User A title | No results | No results | Pass |
| L8 | Dashboard counters | Count only own work | Own work only | Pass |
| L9 | User B adds User A paper to a review | HTTP 404 | HTTP 404 | Pass |
| L10 | User A reviews own two papers | HTTP 201, both papers named | HTTP 201, both named | Pass |
| L11 | Query the database directly with the browser publishable key | Zero rows | Zero rows | Pass |
| L12 | Use a token after sign-out, past the cache window | HTTP 401 | HTTP 401 at t+6.1 s | Pass |
| L13 | First upload of a document | Cache miss, model called | 32.4 s, cache_hit false | Pass |
| L14 | Same document, same user | Cache hit, no model call | 3.2 s, cache_hit true | Pass |
| L15 | Same document, different user | Cache hit, nothing leaked about first user | 2.7 s, no leakage | Pass |
| L16 | Processing time reported on a hit | The original run figure | 29,823 ms unchanged | Pass |
| L17 | Hit counter after two hits | Incremented | Incremented | Pass |
| L18 | Upload a PDF with no extractable text | Rejected, not analysed | HTTP 422 | Pass |
| L19 | Analyse with Anthropic primary | 5 of 5 complete | 5 of 5 by Anthropic | Pass |
| L20 | Analyse with Groq primary, both enabled | Completes | 5 of 5, all via fallback | Pass |
| L21 | Analyse with Groq only, Anthropic disabled | Groq succeeds or fails honestly | 0 of 5, token-limit refusal | Pass as a test |
| L22 | Disabled provider is unreachable | No fallback occurs | No fallback occurred | Pass |

**Totals.** 26 isolation checks passed with 0 failures (L1 to L12); the cache
test passed on all four independent signals (L13 to L17).

**On L21.** The test is marked as passing because it did what it was designed to
do: it produced a truthful measurement. What it measured is a failure of the
provider, analysed in §5.14 of the report.

@PAGEBREAK

# 6. SCREENSHOT INDEX

Eleven screenshots were captured from the live system. There is deliberately no
cache screenshot: cache behaviour is evidenced by the measured test in Table 5.5
of the report instead, and no image was fabricated to fill the gap.

@TABLE|Table 7|Screenshots, their figure numbers and what each evidences
| File | Figure | Screen | Evidences |
|---|---|---|---|
| 01-landing.png | Figure 4.4 | Public landing page, signed out | Public entry point |
| 02-signup.png | Figure D.1 | Account creation | Objective 8 |
| 03-dashboard-empty.png | Figure 4.5 | Dashboard, new account | Empty library, per-user isolation |
| 04-upload.png | Figure D.2 | Upload and analysis in progress | Objective 1 |
| 05-summary.png | Figure 4.6 | Summary and key findings | Requirement 2, objective 3 |
| 06-gaps.png | Figure 4.7 | Research gaps and limitations | Requirement 3, objective 4 |
| 07-review.png | Figure 4.8 | Cross-paper review of two papers | Requirement 4, objective 6 |
| 08-library.png | Figure 4.9 | Private research library | Requirement 1, objective 8 |
| 09-settings-account.png | Figure D.4 | Account settings | Objective 8 |
| 10-settings-ai.png | Figure 4.10 | Owner AI configuration | Objective 10 |
| 12-mobile.png | Figure 4.11 | Dashboard at a mobile viewport | Non-functional requirement, responsive |

Seven of these also appear in the presentation: slides 5, 8, 9, 10 and 11.

No screenshot contains an API key, a token, an environment file or a real email
address other than a throwaway test account.

@PAGEBREAK

# 7. MEASUREMENT ERRORS FOUND AND CORRECTED

Recorded because each produced a plausible but wrong number. An evaluation that
reports only its successes is not evidence of care.

@TABLE|Table 8|Measurement errors, their effect and the correction
| # | Error | What it would have shown | Correction |
|---|---|---|---|
| 1 | A content delivery network replaced provider error bodies with a short generic message | Every failure looked identical and carried no cause; the token limit was invisible | Address the application origin directly |
| 2 | A cache hit read as a provider success | Two papers returned HTTP 200 under a provider-only configuration without the request reaching that provider | Clear the relevant cache rows before measuring |
| 3 | The cache test fixture was still cached from a previous run | The run first upload was a hit, so every dependent assertion failed | The test now clears its own fixture row before starting |
| 4 | Two transient failures read as systematic | One pass would have been reported as 3 of 5 | Re-ran both under the identical configuration; both completed |
| 5 | A test asserted that sign-out takes effect instantly | Reported a security failure that did not exist, re-checking at 2 s against a 5 s cache | Measured the real window at 6.1 s; the test now asserts the actual contract |

Errors 2 and 3 share a root cause: a cache keyed by content. This is why §3.11 and
§4.16 of the report labour the point, and why the reproduction instructions below
list cache clearing as a requirement rather than a suggestion.

@PAGEBREAK

# 8. ARTEFACT INDEX

@TABLE|Table 9|Where each piece of evidence lives
| Path | Contents |
|---|---|
| `data/dataset_manifest.csv` | The five corpus papers, metadata from the arXiv API |
| `data/samples/*.pdf` | The unmodified source PDFs |
| `results/evaluation/raw/*.json` | Every complete analysis response, as returned |
| `results/evaluation/runs_*.json` | One record per run, per configuration |
| `results/evaluation/runs.json` | All runs merged and labelled by pass |
| `results/evaluation/groq_capacity.json` | The provider's own token-limit refusals, per paper |
| `results/evaluation/summary.txt` | Aggregated tables reproduced in Chapter 5 |
| `results/evaluation/isolation_test.txt` | Live two-account isolation run, 26 passed, 0 failed |
| `results/evaluation/cache_test.txt` | Live cache verification, four signals |
| `results/evaluation/logout_window.txt` | Measured sign-out acceptance window |
| `src/db/migrations/00*.sql` | Six additive-only migrations |
| `docs/report/screenshots/` | The eleven interface screenshots |
| `docs/report/diagrams/` | Diagram sources and rendered images |

@PAGEBREAK

# 9. REPRODUCING THE EVALUATION

## 9.1 Automated suite

Offline, free and deterministic. No provider key required.

@CODE
python -m pytest -q
cd app && npx vitest run
python -m ruff check src tests
cd app && npx tsc --noEmit && npx next build
@ENDCODE

## 9.2 Live evaluation

Requires the production service-role key and consumes real provider quota. Three
requirements, each corresponding to a mistake in §7 above:

1. **Group results by the provider that actually answered**, never by the one
   configured. The two differ whenever the primary fails and the fallback takes
   over, and grouping by configuration credits one provider with another's work.
2. **Clear the relevant `analysis_cache` rows before each pass**, or the second
   pass is served the first pass's stored answer and records a comparison that
   never happened.
3. **Address the application origin rather than the proxied custom domain**, or
   provider error messages are replaced and the cause of a failure is lost.

@PAGEBREAK

# 10. ASSESSMENT COMPONENT AUDIT

@TABLE|Table 10|The eight assessment components, evidence and status
| Component | Marks | Evidence | Gaps or risks | Status |
|---|---|---|---|---|
| Proposal | 10 | `PROJECT_PLAN.md`; report §1.1 to §1.5 | None | Complete |
| Dataset and preparation | 10 | Manifest, five unmodified PDFs, report §3.4 to §3.7, Appendix C | Corpus is five papers from one arXiv category; bias stated | Complete |
| AI model implementation | 25 | Report §3.8 to §3.11, §4.12 to §4.18, Appendix B | Insufficient-evidence path unit-tested but never triggered by the corpus | Complete |
| Application development | 20 | Deployed system, 15 routes, report §4.5 | None | Complete |
| Testing and evaluation | 10 | 538 automated tests, 22 live test cases, `results/evaluation/` | No ground-truth grading; stated as the primary limitation | Complete |
| GitHub repository quality | 10 | Repository, documentation set, additive-only migrations, placeholder-only `.env.example` | Final commit and push of report and evaluation artefacts outstanding | Outstanding action |
| Final report | 10 | `ResearchForge_Final_Project_Report.docx`, Chapters 1 to 7, Appendices A to D | Names, student IDs and submission date are placeholders; contents page must be generated in Word | Outstanding action |
| Presentation and demo | 5 | 15-slide deck and timed 20-minute script | Not yet rehearsed against a clock | Complete |

## 10.1 AI model implementation evidence

The brief asks for explicit technical evidence on eleven points for the 25-mark
component. Each is answered in the report at the location given.

@TABLE|Table 11|The eleven required points of AI implementation evidence
| # | Required evidence | Where in the report |
|---|---|---|
| A | Why the primary provider was selected | §3.8 |
| B | Why the secondary provider is used | §3.8; §5.14 records that it cannot serve papers at its free tier |
| C | How PDF text becomes model input | §3.6, §3.7, §4.11 |
| D | How prompts are constructed | §3.10 |
| E | How the model produces each output | §3.8, §4.12 to §4.14 |
| F | How structured output is validated | §3.10, Appendix B.5 |
| G | How grounding is enforced | §3.10 |
| H | How unsupported claims are minimised | §3.10; discard on mismatch |
| I | How provider failure is handled | §3.9, §4.17 |
| J | How fallback is recorded | §4.9, §4.17; provenance columns |
| K | Remaining model limitations | §6.9 |

**Terminology.** The system performs **inference** against hosted foundation
models. No model is trained, fine-tuned or otherwise fitted by this project, and
the report does not describe it as such.

## 10.2 Submission components

@TABLE|Table 12|The five required submissions
| # | Component | Requirement | Delivered |
|---|---|---|---|
| 1 | Project report | Chapters 1 to 7 | `ResearchForge_Final_Project_Report.docx`, 11,929 words |
| 2 | System and application | Interface and database | Deployed; Next.js, FastAPI, Supabase PostgreSQL with RLS |
| 3 | Slides | Minimum 10 | `ResearchForge_Final_Presentation.pptx`, 15 slides |
| 4 | Presentation | 20 minutes | `ResearchForge_Final_Speaking_Script.docx`, timed to 19:35 |
| 5 | Poster or infographic | — | `POSTER.md` specification, for layout by the group |

@PAGEBREAK

# 11. HONEST LIMITATIONS

Repeated here so that nothing in this pack is read as a stronger claim than the
evidence supports.

**No ground truth.** Every number measures how much the system produced or how
long it took, not whether the output is correct. A system inventing nine
plausible research gaps would score identically to one identifying nine real
ones. There is no labelled benchmark, and no accuracy value is claimed anywhere.

**The provider comparison could not be completed.** At its free service tier the
configured primary provider allows 7,000 input tokens per minute, while every
corpus paper required between 7,920 and 20,362 in a single request. It produced
no analysis, and the fallback carried all of them.

**The insufficient-evidence path was never triggered.** Across ten analyses, none
reported insufficient evidence, because the corpus papers were complete and
well-structured. That safeguard is verified by the automated suite, not by this
evaluation.

**This is not retrieval-augmented generation.** The production pipeline supplies
the whole extracted document as context. The embedding provider, `chunks` table
and pgvector column in the repository are prepared scaffolding and are not called
during analysis.

**A bounded window after sign-out.** A revoked token continues to be accepted for
up to about five seconds, measured at 6.1 s, as a deliberate trade against
contacting the authentication service on every request.

**Narrow evaluation.** Five papers from one discipline, each analysed once per
configuration, evaluated by the project team rather than independently.

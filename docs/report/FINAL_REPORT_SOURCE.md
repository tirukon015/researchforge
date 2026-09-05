@FRONTMATTER

## Declaration

We declare that this report is our own work and that all sources of information
have been acknowledged. The system was designed, implemented, deployed and tested
by the project group. All results in Chapter 5 were produced by running the
deployed system against real research papers; no result, test count or evaluation
figure has been estimated or invented. Where a planned capability was not built, or
an evaluation could not be completed, this is stated explicitly.

Where a planned capability was not built, or where an evaluation could not be
completed, this is stated explicitly rather than omitted.

## Acknowledgement

We thank our lecturer, Encik Azuan Nazeer, for guidance throughout the BIT4543
Artificial Intelligence group project. We also acknowledge the authors of the
five open-access arXiv papers used as evaluation input, and the maintainers of
the open-source libraries on which the system is built.

@PAGEBREAK

## Abstract

Researchers spend a substantial part of their time reading academic papers in
order to decide which papers are worth reading closely. This project developed
ResearchForge, a deployed web application that assists this first pass by
accepting an uploaded research paper in PDF form and generating a structured
summary with key findings, an analysis of research gaps, and literature review
content, all saved into a private per-user research library.

The system performs inference against hosted large language models rather than
training a model of its own. Two providers operate behind a single interface: Groq
running qwen/qwen3.6-27b as the configured primary, and Anthropic claude-opus-5 as
the automatic fallback. Model output is constrained to a declared schema and
validated before storage, and output that fails validation is discarded rather than
repaired. The production pipeline supplies the whole extracted document as context;
the retrieval infrastructure in the repository is prepared scaffolding and is not
called during analysis.

Testing combined 522 automated backend tests and 16 frontend tests, all passing,
with live verification against the deployed system. Per-user isolation enforced by
PostgreSQL Row Level Security passed 26 live checks with no failures, including a
direct database query that bypassed the application and returned zero rows. A
content-addressed cache reduced a repeated analysis of the same paper from 32.4
seconds and three model calls to 3.2 seconds and none. Evaluation also produced a
significant negative finding: at its free service tier the configured primary
provider could not process any paper in the evaluation corpus, and every analysis
was completed by the fallback provider.

@PAGEBREAK

@TOC

@PAGEBREAK

@LISTOFFIGURES

@PAGEBREAK

@LISTOFTABLES

@PAGEBREAK

# CHAPTER 1: INTRODUCTION

## 1.1 Background

Academic research depends on reading. Before contributing to a field, a researcher must establish what the field already claims, which questions remain open, and how studies relate to one another. A search on a narrow topic returns dozens of candidates, and each must be assessed for what it claims, what evidence supports it, and whether it justifies reading in full.

Recent progress in large language models has made document-level understanding
practical for small teams, since hosted models are reached through an interface and
need no training or labelled corpus. This shifts the engineering problem from model
training to system design: how the document is supplied, how output is constrained
and validated, how provider failures are handled, and how user data is kept
private.

ResearchForge was built to address that problem for the specific task of
research paper analysis. It is a deployed, publicly reachable web application
in which a researcher uploads a paper and receives structured analysis saved
into a private library.

## 1.2 Problem Statement

The obvious approach is to paste a question into a general-purpose chatbot. This fails in a way that is damaging for research: such a system will answer confidently about a paper it has not read, drawing on prior knowledge of similar work, and may produce a plausible summary or a citation that does not correspond to the document.

For a researcher an unreliable summary is worse than none. A fabricated claim costs more time to detect than the summary saved, and if undetected it propagates into the researcher own writing. Any system assisting genuine research must therefore treat groundedness as a design requirement rather than as a hoped-for property of the model.

## 1.3 Objectives

The project set the following objectives.

1. To allow authenticated users to upload research papers in PDF form.
2. To extract text reliably from uploaded PDF documents, and to reject
   documents from which no text can be extracted.
3. To generate structured summaries and key findings grounded in the uploaded
   document.
4. To identify research gaps supported by the document.
5. To generate literature review content from an analysed paper.
6. To support cross-paper literature review across several analysed papers.
7. To provide a usable research assistant interface.
8. To provide secure user accounts with per-user ownership of the research
   library, enforced at the database level.
9. To reduce duplicate AI processing through same-paper analysis caching.
10. To provide owner-controlled AI provider configuration.

## 1.4 Scope

**Included.** The system covers account creation and sign-in by email or Google,
PDF upload and text extraction, generation of summary, key findings, research gaps
and literature review content, cross-paper review, a private per-user library,
account settings, owner-controlled provider selection and availability, and a
same-paper analysis cache. It is deployed and publicly accessible.

**Excluded.** The system does not train or fine-tune any model; it performs
inference against hosted foundation models. It has no optical character
recognition, so scanned papers cannot be analysed. It does not implement an
active vector retrieval pipeline: the embedding provider, chunks table and
pgvector column in the repository are prepared infrastructure the production path
does not call. It provides no grounded question-and-answer chat, document export
or citation extraction, and the evaluation includes no labelled benchmark or
expert grading, for the reasons in Section 5.14.

## 1.5 Significance of the Project
For the user, the system reduces the effort of the first reading pass while
keeping output checkable: every section is constrained to the uploaded document,
and where the document does not support a section the system reports
insufficient evidence rather than generating text to fill the gap.

# CHAPTER 2: LITERATURE REVIEW

## 2.1 Introduction
This chapter reviews the AI technologies relevant to document intelligence,
examines existing systems addressing parts of the same problem, identifies the
gap this project addresses, and presents the conceptual framework.

## 2.2 Artificial Intelligence Technologies Relevant to the Project
**Artificial intelligence** builds systems that perform tasks normally requiring
human intelligence. This project sits within applied AI: it composes an
application from existing components rather than advancing model capability.

**Natural language processing** concerns human language. Devlin et al. (2018)
showed with BERT that bidirectional pre-training followed by fine-tuning
produces strong results across language tasks. Beltagy et al. (2019) showed with
SciBERT that pre-training on scientific text improves performance on scientific
tasks, which is evidence that academic writing has distinctive characteristics.

**Large language models and inference.** Contemporary models are accessed as
hosted services: an application supplies a prompt and receives generated text,
with model parameters fixed. This is **inference**, not training, and the
distinction matters for how this project is described and assessed.

**Grounding and retrieval.** A model asked about a document it has not been
given will answer from prior knowledge. Retrieval-augmented generation (Lewis et
al., 2020) retrieves relevant passages and supplies them as context.
Alternatively, a document small enough to fit the context window can be supplied
whole. ResearchForge uses the second approach, for reasons in Section 3.8.

**Evaluating generated text.** Wang et al. (2020) proposed generating questions
from a summary and answering them against the source as an automatic,
reference-free measure of factual consistency. This is directly relevant to
ungrounded summaries, though it requires a question-answering pipeline this
project did not build.

## 2.3 Related Works
**General-purpose conversational assistants** can summarise a pasted document.
They are flexible and need no setup, but offer no guarantee the answer derives
from the supplied text, no persistent library, and no structured output an
application can validate.

**Reference managers** such as Zotero and Mendeley organise papers and generate
citations. They solve storage and bibliography, which this project does not
attempt, but do not analyse paper content.

**Academic search services** such as Semantic Scholar provide search, citation
graphs and short generated summaries over an indexed corpus rather than over a
document the user supplies, and do not produce a gap analysis for a specific
paper.

**Retrieval-augmented question answering systems** follow Lewis et al. (2020):
a corpus is chunked, embedded and indexed, and relevant passages are retrieved
to answer a query. This scales beyond a context window but introduces failure
modes, since a retrieval step returning the wrong passage silently degrades the
answer.

**Research on factual consistency**, including Wang et al. (2020), addresses
measurement rather than system construction: it scores whether a summary is
consistent with its source but does not prevent unsupported generation.

@TABLE|Table 2.1|Comparison of related systems and approaches
| Study or system | Method used | Strengths | Limitations |
|---|---|---|---|
| Conversational assistants | Prompt a hosted model directly | Flexible; no setup | No guarantee output derives from the document; no library |
| Zotero, Mendeley | Reference storage and citation | Reliable organisation | No content analysis or summarisation |
| Semantic Scholar | Indexed corpus, citation graph | Large coverage; discovery | Not user-supplied documents; no per-paper gap analysis |
| Lewis et al. (2020) | Retrieve passages, then generate | Scales beyond a context window | Retrieval errors silently degrade output |
| Wang et al. (2020) | Question generation and answering | Reference-free consistency signal | Measures consistency; does not prevent it |
| ResearchForge | Whole-document grounded generation, schema-constrained | Validated output; database-level isolation; fallback; caching | Bounded by context window; no retrieval; no labelled benchmark |

## 2.4 Comparison of Related Systems

Two design consequences follow. If output is to be trustworthy the constraint must be enforced by the system rather than requested of the model, which led to schema-constrained generation with discard-on-mismatch. Retrieval, meanwhile, is a means to an end: where a document fits in the context window, supplying it whole avoids retrieval error entirely.

## 2.5 Research Gap
The reviewed work leaves a gap: systems that analyse a user-supplied paper
generally do not enforce that their output derives from it; systems that enforce
grounding through retrieval add a layer whose failures are hard to observe; and
systems that organise literature do not analyse it. Multi-user research tools
also rarely make explicit how one user documents are kept from another.

ResearchForge addresses this by combining whole-document grounded generation with
structural enforcement of output validity, database-level isolation, and recorded
provenance. It does not close the gap entirely: without a labelled benchmark it
cannot show that the gaps it identifies are those a domain expert would identify,
as stated in Section 5.14.

## 2.6 Conceptual Framework

The conceptual framework in Figure 2.1 shows how an input paper becomes research
insight. An uploaded PDF is extracted, normalised and hashed, and the hash is used
to look up a previous analysis. On a miss the document is submitted in three
grounded passes, with one fallback attempt for retryable failures, and validated
before storage; on a hit the stored analysis is reused with no model call. The
framework contains no vector retrieval stage, because the production pipeline
performs none.

The framework deliberately does not include a vector retrieval stage, because
the production pipeline does not perform retrieval.

@FIG|fig2_1_conceptual|Figure 2.1|Conceptual framework of the ResearchForge analysis pipeline

## 2.7 Chapter Summary
The conclusions carried into the methodology are that grounding must be enforced
structurally rather than requested, that retrieval is unnecessary when a document
fits in context, and that per-user isolation must be enforced below the
application layer.

# CHAPTER 3: METHODOLOGY

## 3.1 Introduction
This chapter describes the development methodology and process, how input
documents were collected and prepared, how text is extracted and preprocessed,
how the AI component was designed, the provider architecture, the structured
generation approach, the cache, the database design and the tools used.

## 3.2 Development Methodology
The project used an incremental, milestone-based methodology: work was divided
into small milestones, each ending with a test and a review before the next
began. This suited a project in which several design questions could only be
answered by measurement. The decision not to build vector retrieval was made
only after measuring that real papers fit within the context window, and the
decision to move isolation into the database followed a defect showing that
application-level filtering had failed silently.

## 3.3 System Development Process
Each milestone followed the same process: inspect existing code, make a small
additive change, run the automated suite, verify behaviour against the deployed
system where relevant, and record the outcome. Database changes were made
through numbered migration files containing only CREATE and additive ALTER
statements; no migration contains DROP, TRUNCATE or DELETE, so applying one
cannot destroy existing data. Six migrations were applied in sequence: initial
schema; analyses and reviews; authentication and ownership; owner and AI
configuration; the analysis cache; and provider availability.

## 3.4 Data Collection

**Operational data** is whatever papers users choose to upload. There is no
fixed operational dataset; the system processes documents supplied at runtime.

**Evaluation data** is a fixed corpus assembled specifically to measure the
system. It consists of five open-access research papers from arXiv.

## 3.5 Dataset and Research Paper Preparation

Five real, openly available arXiv papers were selected as the evaluation
corpus. Metadata was retrieved from the arXiv application programming interface
rather than transcribed by hand, and is recorded in the dataset manifest
alongside the source URLs and licence information. The PDFs are stored
unmodified in the project repository.

@TABLE|Table 3.1|Evaluation corpus of open-access research papers
| arXiv ID | Title | Year | Authors | Pages |
|---|---|---|---|---|
| 1706.03762 | Attention Is All You Need | 2017 | 8 | 15 |
| 1810.04805 | BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding | 2018 | 4 | 16 |
| 1903.10676 | SciBERT: A Pretrained Language Model for Scientific Text | 2019 | 3 | 6 |
| 2004.04228 | Asking and Answering Questions to Evaluate the Factual Consistency of Summaries | 2020 | 3 | 13 |
| 2005.11401 | Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks | 2020 | 12 | 19 |

Papers were chosen to vary in length, publication year and author count. The
selection is acknowledged as narrow: all five are English-language computational
linguistics papers from one arXiv category, all born-digital with a text layer.
Nothing here establishes behaviour on scanned documents, other disciplines or
other languages. The project has no labelled machine-learning training dataset,
because no model is trained.

## 3.6 PDF Text Extraction

Text extraction uses the pypdf library, chosen because it is pure Python and
introduces no system-level dependency, which suits deployment to a serverless
platform.

Extraction is deliberately strict: a PDF yielding no usable text is rejected with
HTTP 422 and no model is called. A language model given empty input still
produces fluent, confident output, which would be entirely ungrounded, so
rejecting the document is correct even though scanned papers cannot be processed.

## 3.7 Text Preprocessing

Extracted text is normalised before use: Unicode is normalised using NFKC and
runs of whitespace collapsed. Two PDF renderings of the same paper can differ
invisibly in ligatures, non-breaking spaces or line endings, and without
normalisation the same paper would hash differently and be analysed twice. The
normalised text is then hashed with SHA-256 together with an analysis version
constant, giving the document identity used for caching in Section 3.11.

The normalised text is then hashed with SHA-256 together with an analysis
version constant. The resulting hash is the document identity used for caching,
described in Section 3.11.

## 3.8 AI Model Development
The AI component performs **inference** against hosted foundation models. No
model is trained, fine-tuned or otherwise fitted by this project, and no
proprietary labelled dataset exists.

**Model and provider selection.** Two providers sit behind one interface. Groq,
running qwen/qwen3.6-27b, is the configured primary and was selected for speed
and for independence from a single supplier. Anthropic claude-opus-5 is the
automatic fallback, selected because its interface parses directly into a
declared schema, strengthening the validation guarantee in Section 3.10.

**How the document becomes model input.** The whole normalised paper is placed in
the prompt as context: full-document grounded generation. The repository contains
an embedding provider, a chunks table and a pgvector column, but the production
path does not call them; they are prepared scaffolding. The system must therefore
not be described as implementing retrieval-augmented generation.

The decision was empirical: every corpus paper fitted a single context window
with no truncation or chunking (Section 5.13). Retrieval would have added a
failure mode, in which an incorrect retrieval silently degrades the answer,
without solving a problem the system had. A map-reduce digest exists as a size
guard above 400,000 characters and was never invoked.

**Inference process.** Analysis makes three separate structured calls: summary
and key findings, research gaps, and literature review content. They are
separate because a single combined prompt produced a noticeably weaker gap
analysis, with attention dominated by the summary.

## 3.9 AI Provider Architecture
The owner selects one provider as the global primary. The other enabled provider
automatically acts as the fallback; there is no separate automatic setting, and
normal users cannot select or switch providers.

Two rules govern routing. **One switch per analysis:** an analysis makes at least
three calls, and a per-call switch would let different parts be written by
different models, making the recorded model identity meaningless. **Fallback only
for retryable failures:** the check is a whitelist, so a new error type does not
become retryable by default. A rate limit is worth a second attempt; a malformed
PDF, a validation failure or a missing key is not.

Only **one** fallback attempt is made. The system does not retry indefinitely,
and not all errors trigger fallback.

Provider availability is enforced when the router is constructed rather than
checked at call time, so a provider the owner has switched off is never
constructed and no code path can call it. Routing applies globally; existing
analyses are not reprocessed when configuration changes.

An earlier version of the project used Google Gemini. Gemini is a historical
provider only: it is not part of the current architecture, and current analyses
are not produced by it.

## 3.10 Prompt and Structured Generation Approach

Grounding is enforced through four layers rather than requested in the prompt
alone.

The **prompt** requires every claim to be traceable to the supplied text and
requires the model to report insufficient evidence rather than fill a gap. The
prompts are stored in version-controlled files rather than scattered through the
code.

The **schema** constrains the output. Each of the three passes declares a
Pydantic model describing the expected structure, including explicit
insufficient-evidence fields that give the model a way to decline that is as
easy as complying.

**Validation** checks the returned data against that schema. The Anthropic
provider parses directly into the declared model; the Groq provider requests
JSON and validates it against the same model.

**Discard on mismatch** is the rule that makes the previous layers meaningful.
Output that fails validation is rejected, not repaired. A partially valid
analysis that the system patched up would be an invented analysis, which is
precisely what the grounding claim forbids.

## 3.11 Same-Paper Analysis Cache

Analysing the same paper twice costs two sets of tokens and produces two answers
to one question. The cache prevents this.

The cache is keyed by the content hash together with the analysis version. Because the key derives from normalised content, a paper is recognised regardless of filename, and the version component allows deliberate invalidation when the analysis method changes.

The cache is **global internal infrastructure, not a user library**. If one user
uploads a paper another has already analysed, the stored analysis is reused
instead of making duplicate model calls, while each user still receives their own
private paper, analysis and library records. The cache does not reveal who first
uploaded a document, and it does not replace Row Level Security: the cache table
has Row Level Security enabled with no policy at all, so it is unreachable by
user requests and accessible only to the backend.

Only successful, schema-validated analyses are cached; failed, rate-limited, malformed or incomplete results are never written. A uniqueness constraint on the key prevents duplicate rows and makes concurrent writes safe. Because the key excludes the provider, changing provider configuration does not invalidate a valid cached analysis.

## 3.12 Database Design and Data Management

The database is Supabase PostgreSQL. PostgreSQL was selected specifically for
Row Level Security, which is the mechanism behind the per-user ownership
objective.

Ownership columns default to the authenticated identity supplied by the database, so a row cannot be inserted without an owner even if application code omits it. Records created before authentication remain unowned: they were neither deleted nor assigned to a user whose ownership could not be established, and are unreachable because a null owner never matches an authenticated identity.

## 3.13 Development Tools and Technologies

@TABLE|Table 3.2|Development tools and technologies
| Layer | Technology | Reason |
|---|---|---|
| Frontend | Next.js 16, React 19, TypeScript | Server-rendered pages, typed API client |
| Styling | Hand-written CSS custom properties | One token set drives both themes |
| Backend | Python 3.14, FastAPI, Pydantic | Validates API input and model output alike |
| PDF extraction | pypdf | Pure Python, no system dependency |
| Database | Supabase PostgreSQL | Row Level Security for per-user isolation |
| Authentication | Supabase Auth | Email and Google; no password stored here |
| AI providers | Groq qwen3.6-27b; Anthropic claude-opus-5 | Schema-constrained generation, second vendor |
| Testing | pytest, Vitest | Offline suites running against fakes |
| Linting | Ruff | Lint and format in one tool |
| Hosting | Vercel | Both services in one project, one origin |

Neither TensorFlow nor PyTorch is used, because no model is trained. Neither
MySQL nor MongoDB is used, because PostgreSQL was chosen specifically for Row
Level Security.

## 3.14 Chapter Summary
The methodology combined incremental development with measurement-driven
decisions. The AI component performs inference with output constrained by a
declared schema, and the cache is keyed by normalised content so duplicate
inference is avoided without compromising isolation.

# CHAPTER 4: SYSTEM DESIGN AND IMPLEMENTATION

## 4.1 Introduction
This chapter describes the requirements the system was built against, its
interface, architecture, use cases, process flow and database design, and the
implementation of each major module.

## 4.2 System Requirements
Requirements were derived from the objectives in Section 1.3 and refined during
development as defects revealed unstated expectations.

## 4.3 Functional Requirements

@TABLE|Table 4.1|Functional requirements and implementation status
| ID | Requirement | Implemented in | Status |
|---|---|---|---|
| F1 | Create an account and sign in by email or Google | Supabase Auth | Implemented |
| F2 | Upload a research paper in PDF form | Analyse endpoint | Implemented |
| F3 | Generate a structured summary with key findings | Analysis service | Implemented |
| F4 | Identify research gaps supported by the paper | Analysis prompts | Implemented |
| F5 | Generate literature review content | Analysis service | Implemented |
| F6 | Review across several saved papers | Cross-review service | Implemented |
| F7 | Papers, analyses and reviews private to their owner | RLS, migration 003 | Implemented |
| F8 | Owner selects primary provider and switches one off | Owner API | Implemented |
| F9 | An analysed paper is not analysed again | Analysis cache | Implemented |
| F10 | A PDF without extractable text is rejected | Ingestion module | Implemented |
| F11 | Change display name and password, and sign out | Settings page | Implemented |

## 4.4 Non-Functional Requirements

@TABLE|Table 4.2|Non-functional requirements and supporting evidence
| ID | Category | Requirement | Evidence |
|---|---|---|---|
| N1 | Performance | New analysis within about two minutes | 32.4 s, Section 5.10 |
| N2 | Performance | Repeated analysis in a few seconds | 3.2 s and 2.7 s, Section 5.10 |
| N3 | Security | No cross-user access even if application code is wrong | 26 checks passed, Section 5.7 |
| N4 | Security | No secret reaches the browser or version control | Environment variables; key-type guard |
| N5 | Security | A revoked session stops working | Refused at 6.1 s, Section 5.6 |
| N6 | Reliability | A retryable provider failure does not fail the request | 5 of 5 fallbacks, Section 5.9 |
| N7 | Scalability | Repeated uploads cost one analysis | Content-addressed cache |
| N8 | Portability | Runs on Windows, macOS and Linux | pathlib; no platform-specific commands |

## 4.5 User Interface Design and Implementation
The interface consists of fifteen routes built with Next.js and hand-written CSS
using custom properties, so a single set of design tokens drives light and dark
themes.

Figure 4.4 shows the public landing page, which introduces the product to
visitors who are not signed in and provides the entry points to sign in and
create an account. No application data is reachable from it.

@FIG|01-landing|Figure 4.4|ResearchForge public landing page

Figure 4.5 shows the dashboard for a newly created account: the library is empty
and the counters read zero, the visible consequence of requirement F7, since a
new user sees nothing belonging to any other user. The upload area is the entry
point for analysis.

@FIG|03-dashboard-empty|Figure 4.5|Empty dashboard for a newly created user account

Figure 4.6 shows the summary and key findings generated for an uploaded paper,
satisfying requirement F3.

@FIG|05-summary|Figure 4.6|Generated research paper summary and key findings

Figure 4.7 shows the identified research gaps and the limitations stated by the
authors, the output of the second structured pass described in Section 3.8.

@FIG|06-gaps|Figure 4.7|Generated research gaps and limitations

Figure 4.8 shows the cross-paper literature review interface, in which the user
selects several analysed papers and generates a review across them. The example
is a review generated from two papers; the feature requires more than one paper
by design.

@FIG|07-review|Figure 4.8|Cross-paper literature review interface

Figure 4.9 shows the private research library, containing only the signed-in
user papers.

@FIG|08-library|Figure 4.9|User research paper library

Figure 4.10 shows the Owner AI Configuration panel, visible only to an account
registered as an application owner. It provides selection of the global primary
provider and per-provider availability. Normal users have no equivalent control
and the panel does not appear in their settings.

@FIG|10-settings-ai|Figure 4.10|Owner AI configuration and provider availability controls

Figure 4.11 shows the dashboard at a mobile viewport. The layout reflows to a
single column, the account name is hidden below 900 pixels to prevent header
overflow, and card content is not clipped. Both behaviours were corrections made
after testing on a real handset.

@FIG|12-mobile|Figure 4.11|ResearchForge responsive dashboard on a mobile viewport

## 4.6 System Architecture

The system is deployed as a single Vercel project running two services that
share one origin: a Next.js frontend and a FastAPI backend. Because they share
an origin, the frontend calls the backend using a relative path.

Figure 4.1 shows the architecture. A request carries the bearer token and PDF to the backend, which verifies the token, extracts and normalises the text, computes the hash and consults the cache. On a miss the router calls the primary provider, with one fallback attempt for retryable failures, and the response is validated before being written to PostgreSQL. Results return filtered by the authenticated identity.

@FIG|fig4_1_architecture|Figure 4.1|ResearchForge system architecture

The retrieval infrastructure present in the repository is not shown as part of
the production flow because the analysis path does not call it.

## 4.7 Use Case Design

Figure 4.2 shows the use cases and two actors. A User manages their account,
uploads and analyses papers, views the generated output, performs cross-paper
review and manages their library. An Owner additionally reaches the AI
configuration. Owner privileges are determined on the server from the
authenticated identity and the owner register; there is no separate owner login
page.

@FIG|fig4_2_usecase|Figure 4.2|Use case diagram

## 4.8 Activity Flow

Figure 4.3 shows the activity flow, making the cache path explicit: a hit reuses
the stored, previously validated analysis with no model call while still creating
that user own records. On a miss the request goes to the primary provider, one
fallback attempt is permitted for a retryable failure, and the response must pass
schema validation before the analysis and cache entry are stored.

@FIG|fig4_3_activity|Figure 4.3|Activity flow for analysing an uploaded paper

## 4.9 Database and ERD Design

Figure 4.12 shows the entity relationship design. The authentication users
entity represents identity managed by Supabase Auth and is shown for context; it
is not an application table. Papers, analyses and reviews each carry an owning
user. Reviews relate to papers through a join table, which allows one review to
cover several papers.

@FIG|fig4_4_erd|Figure 4.12|Entity relationship diagram

Three aspects deserve comment. Ownership columns default to the authenticated
identity, so a row cannot be created without an owner. The analyses table records
provenance: the provider that actually produced the result, the model, whether the
fallback was used, whether the response came from cache, and the processing time.
The analysis cache table has no user column, being keyed by content.

## 4.10 Authentication and User Ownership

Authentication uses Supabase Auth with email and password and Google sign-in; no
password is stored by this project. Every route except the public landing page
and the health endpoint requires a valid bearer token.

The isolation guarantee is not the token check. It rests on which credential the
backend uses to reach the database: requests are made as the signed-in user, so
PostgreSQL resolves the authenticated identity and applies every Row Level
Security policy automatically. A forgotten ownership filter therefore returns
nothing rather than everything. Section 6.7 describes the defect that made this
change necessary.

The property this produces is that a forgotten ownership filter returns nothing
rather than everything. Isolation stops being something every query must
remember and becomes a property the database enforces. Section 6.7 describes the
defect that made this change necessary.

## 4.11 Research Paper Processing Module
The processing module checks the uploaded file against the size limit, rejecting
oversized uploads with HTTP 413, then extracts text with pypdf. A document
yielding no usable text is rejected with HTTP 422 and never reaches a model. The
extracted text is normalised and hashed as described in Section 3.7, producing
the identity used for caching.

## 4.12 AI Analysis Module
The analysis module orchestrates the three structured passes described in
Section 3.8. It is deliberately unaware of provider routing: it calls a provider
interface and the routing happens beneath it, which meant that adding a second
provider and a fallback changed no business logic. Each pass supplies the whole
normalised document together with the pass-specific prompt and declared output
schema, and the response is validated before it is accepted.

## 4.13 Research Gap Detection
Gap detection is the second structured pass. The prompt directs the model to
identify gaps the paper itself supports, drawing on the limitations the authors
state and the future work they propose, rather than speculating about the field.
The schema separates identified gaps from author-stated limitations and carries
an explicit insufficient-evidence flag.

## 4.14 Literature Review Module
The third pass produces review content for a single paper: the major themes it
engages with, the comparisons it draws with prior work, and the future
directions it identifies. As with the other passes, content is constrained to
the uploaded document.

## 4.15 Cross-Paper Literature Review
Cross-paper review operates over papers the user has already analysed. The user
selects papers from their own library and the system generates a review across
them. It requires more than one paper, since a review across a single paper is
that paper own review content. Only the requesting user papers can be selected;
an attempt to include another user paper fails, as verified in Section 5.7.

## 4.16 Same-Paper Cache
The cache is implemented as described in Section 3.11, keyed by content hash and
analysis version. On a hit the stored payload is returned and the hit counter
incremented; the response reports the cache hit flag as true and preserves the
original run processing time rather than the time taken to serve the cached
copy. That preserved value is what distinguishes a genuine cache hit from a
merely fast analysis.

## 4.17 AI Provider Routing and Fallback
Routing is implemented in a component that itself satisfies the provider
interface, so the analysis module needs no knowledge of it. It holds the primary
provider and, when a second is enabled, the fallback, and applies the two rules
from Section 3.9. Each analysis records the provider that actually produced it,
the model used, and whether the fallback was involved.

## 4.18 Owner AI Configuration
Owner configuration is stored as two values: the active primary provider, and
the set of providers enabled at all. The set is stored as one value rather than
a boolean per provider, so the state in which no provider is enabled cannot be
represented; a database check constraint permits only the three valid
combinations. Write access is restricted to accounts in the owner register.

## 4.19 Error Handling
Errors are translated into meaningful HTTP responses rather than generic
failures: 413 for an oversized upload, 422 for a document without extractable
text, 429 for a provider rate limit with retry information where supplied and an
exhausted quota distinguished from temporary throttling, 503 for credential
problems, and 502 with the reason when a response fails validation.

## 4.20 Responsive Interface
The interface adapts to small viewports, as shown in Figure 4.11. Two
corrections were required: decorative artwork inside cards is clipped only at
widths of 561 pixels and above, because clipping unconditionally cut off real
content on small screens, and the account name is hidden below 900 pixels
because it caused the header to overflow. Both defects were found only by
opening the deployed site on a physical device.

## 4.21 Chapter Summary
The system is a Next.js interface and a FastAPI backend sharing one deployment,
with Supabase providing authentication and a PostgreSQL database whose Row Level
Security enforces ownership. Analysis is three schema-constrained passes over the
whole document, routed to a primary provider with a single retryable fallback.

# CHAPTER 5: TESTING AND EVALUATION

## 5.1 Introduction
This chapter reports how the system was tested and what testing found. All
results were produced by running the tests described; no figure has been
estimated or adjusted.

## 5.2 Testing Strategy
Testing operates at three levels, kept separate because each can pass while
another fails. The isolation defect described in Section 6.7 passed every
automated test while being wrong in production, which demonstrates why one level
is insufficient.

No test in the automated suite calls a paid interface. Every provider is replaced
by a fake, so the suite runs offline, costs nothing and is deterministic. A small
number of live-provider tests exist but are skipped unless explicitly enabled.

## 5.3 Unit Testing

The backend suite was executed with pytest and the frontend suite with Vitest. The verified result is 522 backend tests passing with 5 skipped, and 16 frontend tests passing: 538 passing tests with no failures. The 5 skipped are the opt-in live provider tests, skipped by design rather than by failure.

@TABLE|Table 5.1|Automated backend test distribution by module
| Test module | Tests | What it protects |
|---|---|---|
| Authentication | 61 | Token verification, expiry, bad credentials |
| LLM providers | 49 | Provider behaviour, error translation, validation |
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
| Key type guard | 22 | A publishable key in a private slot |
| Analysis cache | 22 | Cache correctness and versioning |
| Ownership | 20 | Caller identity carried faithfully |
| Application wiring | 9 | Startup, health, route registration |
| Live provider smoke tests | 5 | Live calls, opt-in and skipped |

The largest single module is authentication, which reflects a deliberate
judgement that this is where a silent failure is most costly.

Static quality checks were also run. Ruff reported no issues and no formatting differences across the application source and tests, the TypeScript compiler reported no type errors, and the production build completed successfully, producing 15 routes.

## 5.4 Integration Testing
Integration testing exercised the complete path from browser to database against
the deployed system. Because the isolation guarantee is enforced by the database
rather than by application code, it cannot be verified with a fake: the
ownership unit tests prove the application carries each caller identity
faithfully, but they model Row Level Security with a stub. The live scripts
create throwaway accounts, run a scenario as two different people, and then
delete only what they created using the product own endpoints.

## 5.5 API Testing
The API was tested for error semantics as well as success paths: 401 for
unauthenticated requests, 413 for oversized uploads, 422 for PDFs without
extractable text, 429 for provider rate limiting rather than a generic server
error, and 502 with an explanatory message when a response fails validation.

## 5.6 Authentication and Security Testing

Authentication testing covered account creation, sign-in, sign-out, password
change and session behaviour, and is the largest module in the automated suite.

One finding initially appeared to be a security defect. A live test asserted that a
token was refused immediately after sign-out, and it failed. The assertion, not the
system, was wrong: token verifications are cached for five seconds so that one page
load does not generate a burst of authentication requests, and the test re-checked
after two seconds.

What matters is whether the acceptance window is bounded, which was measured by
sampling after sign-out.

@TABLE|Table 5.2|Measured acceptance of a revoked session token after sign-out
| Time after sign-out | Result |
|---|---|
| 1.6 seconds | Still accepted |
| 3.9 seconds | Still accepted |
| 6.1 seconds | Refused with 401 |
| 8.0 to 20.7 seconds | Refused with 401 |

The window is bounded and consistent with the documented five-second
verification cache. The test now asserts the real contract, which is that
sign-out takes effect once the cache expires. The residual behaviour is recorded
as a limitation in Section 6.9.

## 5.7 User Ownership and Row Level Security Testing

This is the test the automated suite cannot perform. Two throwaway accounts were created against the production system and a full scenario executed as two different people. The run passed 26 checks with no failures.

@TABLE|Table 5.3|Live data isolation test cases and results
| Test case | Expected | Actual | Status |
|---|---|---|---|
| Protected route with no token | 401 | 401 | Pass |
| New account opens its library | Empty | 0 papers | Pass |
| User A uploads a paper | In User A library only | 1 paper, correct title | Pass |
| User B lists papers | User A paper absent | Absent | Pass |
| User B opens User A paper by id | 404, not 403 | 404 | Pass |
| User B deletes User A paper | 404, paper intact | 404 | Pass |
| User B searches User A title | No results | No results | Pass |
| Dashboard counters | Own work only | Own work only | Pass |
| User B adds User A paper to a review | 404 | 404 | Pass |
| User A reviews own two papers | 201, both named | 201, both named | Pass |
| Direct database query with browser key | Zero rows | Zero rows | Pass |
| Token used after sign-out, past cache | 401 | 401 at 6.1 s | Pass |

Two results deserve emphasis. Requests for another user resource return 404 rather than 403, so the system does not confirm that a resource exists. More importantly, querying the database directly with the key that ships inside the browser, bypassing the application entirely, returns zero rows: isolation does not depend on the application being correct.

## 5.8 AI Provider Testing

Provider behaviour was unit-tested for both providers: request construction, translation of provider errors, rate-limit handling, rejection of an unknown model, and validation of structured output. The router was tested for correct primary and fallback selection with either provider configured as primary, and for the rule that a disabled provider is never constructed.

Live testing against the deployed system used the five-paper evaluation corpus
described in Section 3.5, analysed under three configurations.

## 5.9 AI Fallback Testing
The fallback mechanism was verified live. With Groq configured as primary and
Anthropic enabled, all five papers completed, and in every case the analysis was
produced by the fallback, with the fallback flag recorded as true.

@TABLE|Table 5.4|Live provider configurations and completion results
| Configuration | Papers completed | Completed by the configured primary |
|---|---|---|
| Anthropic primary, both enabled | 5 of 5 | 5 of 5 |
| Groq primary, both enabled | 5 of 5 | 0 of 5 |
| Groq only, Anthropic switched off | 0 of 5 | 0 of 5 |

The third configuration was added during evaluation because every run in the second
had fallen back, which meant it measured the fallback rather than Groq. Switching
Anthropic off removed the safety net and confirmed that a disabled provider is
unreachable. Only one fallback attempt is made per analysis, and only for
whitelisted retryable failures. Unit tests verify selection in both directions; the
live evidence covers the Groq to Anthropic direction.

## 5.10 Same-Paper Cache Testing

Cache behaviour was verified against the deployed system using one document uploaded three times: by a first user, again by the same user, then by a second user. Four independent signals were checked, because a cache hit must not merely be faster, it must demonstrably make no model call.

@TABLE|Table 5.5|Controlled production cache test results
| Request | Latency | Cache hit flag | Model called |
|---|---|---|---|
| First upload, User A | 32.4 seconds | False | Yes, three structured calls |
| Same document, User A | 3.2 seconds | True | No |
| Same document, User B | 2.7 seconds | True | No |

The four signals were the cache hit flag in the response; the collapse in latency; the preserved processing time, which remained the original figure of 29,823 milliseconds on both hits rather than the time taken to serve the cached copy; and the increment of the hit counter. The third is the signal a merely fast response could not fake.

The test also verified that one shared cache row was reused while the two users
retained separate private library records, and that nothing identifying the first
user appeared in the second user response. An earlier run during development
produced 24.7 seconds for the miss and about 2.3 and 2.0 seconds for the hits;
Table 5.5 reports the most recent verified run.

An earlier run of the same test, conducted during development, produced 24.7
seconds for the miss and approximately 2.3 and 2.0 seconds for the two hits. The
values reported in Table 5.5 are from the most recent verified run.

## 5.11 User Interface Testing
Interface behaviour was verified by performing each required capability through
the browser as a user would: creating an account, uploading a paper, reading the
summary and gaps, building a cross-paper review, and confirming a second account
could see none of it. Fifteen live uploads were performed across the three
evaluation configurations, and the frontend unit suite contributed 16 automated
tests.

## 5.12 Responsive and Mobile Testing
The interface was opened on a physical handset and at reduced viewport widths.
This found two defects desktop testing had not: decorative artwork clipping real
content on narrow screens, and the account name causing header overflow. Both
were fixed as described in Section 4.20, and the corrected layout is shown in
Figure 4.11.

## 5.13 System Performance

Performance was measured on the deployed system. The values below are what was observed in the tests described; they are not guarantees, and processing time varies with document length and provider load.

@TABLE|Table 5.6|Observed processing performance
| Measurement | Observed value |
|---|---|
| New analysis, controlled cache test | 32.4 seconds |
| Cache hit, same user | 3.2 seconds |
| Cache hit, different user | 2.7 seconds |
| New analysis of corpus papers, median | 98.8 seconds |
| New analysis of corpus papers, range | 72.6 to 115.2 seconds |

The difference between the controlled test and the corpus papers reflects document size: the controlled test uses a short fixture, whereas corpus papers are complete research papers of 6 to 19 pages. A new analysis of a full paper therefore takes on the order of one and a half minutes, because three separate passes are made over the entire document.

Text extraction was measured across the corpus and is identical for both
providers, since it happens before any model call.

@TABLE|Table 5.7|Text extraction results for the evaluation corpus
| Paper | Pages | Characters extracted | Characters per page | Chunks | Truncated |
|---|---|---|---|---|---|
| 1706.03762 | 15 | 39,489 | 2,632 | 1 | No |
| 1810.04805 | 16 | 63,578 | 3,973 | 1 | No |
| 1903.10676 | 6 | 23,767 | 3,961 | 1 | No |
| 2004.04228 | 13 | 46,601 | 3,584 | 1 | No |
| 2005.11401 | 19 | 69,097 | 3,636 | 1 | No |

Extraction yield is consistent across the corpus, indicating that the extractor handled two-column academic layout without dropping content. No paper required chunking or truncation, which is the empirical basis for the decision in Section 3.8 not to build a retrieval pipeline.

## 5.14 Evaluation Results

**Why standard accuracy metrics do not apply.** Accuracy, precision, recall and F1
require labelled ground truth. Generating a literature review has no single correct
output, and no labelled corpus of correct research gaps exists within the project,
so reporting classification metrics would be fabrication presented as rigour and
none are reported. The evaluation instead measures properties observable without
ground truth: completion rate, fallback behaviour, provenance accuracy, latency,
output completeness, rejection of invalid output, and cost avoidance.

The evaluation instead measures properties that can be observed without ground
truth: completion rate, fallback behaviour, provenance accuracy, latency, output
completeness, whether invalid output is rejected, and cost avoidance through
caching.

**The principal finding.** The intended comparison between the two providers could not be completed. With the fallback removed, Groq refused every request, and its own error message gives the reason: the free service tier permits 7,000 input tokens per minute, and each paper required more than that in a single request.

@TABLE|Table 5.8|Input token requirement of each corpus paper against the free-tier limit
| Paper | Pages | Input tokens requested | Tier limit | Ratio |
|---|---|---|---|---|
| 1903.10676 | 6 | 7,920 | 7,000 | 1.1 times over |
| 1706.03762 | 15 | 11,745 | 7,000 | 1.7 times over |
| 2004.04228 | 13 | 12,661 | 7,000 | 1.8 times over |
| 1810.04805 | 16 | 18,498 | 7,000 | 2.6 times over |
| 2005.11401 | 19 | 20,362 | 7,000 | 2.9 times over |

This is not a pacing problem. A per-minute allowance can normally be satisfied by waiting, but a single request of 7,920 tokens can never fit within a 7,000-token-per-minute allowance however long the system waits. Even the shortest paper exceeds the limit, so at this service tier the configured primary provider cannot analyse a research paper of realistic length.

**Output characteristics.** Ten analyses completed successfully across the first
two configurations, and all ten were produced by Anthropic.

@TABLE|Table 5.9|Output produced across ten completed analyses
| Measure | Median | Range |
|---|---|---|
| Key findings per summary | 8 | 6 to 11 |
| Research gaps identified | 9 | 7 to 10 |
| Limitations extracted | 11.5 | 7 to 12 |
| Literature review themes | 8 | 5 to 9 |
| Comparisons with prior work | 7.5 | 5 to 12 |
| Future directions identified | 5 | 3 to 7 |

No analysis reported insufficient evidence in any of the ten runs, which is expected for complete, well-structured papers but means the corpus did not exercise that path at all. The safeguard is verified by the automated suite rather than by this evaluation.

## 5.15 Discussion of Results
The three configurations in Table 5.4 say something together that none says
alone. The system completed every paper it was given, yet under the
configuration the owner had selected it never once used the provider selected as
primary. The fallback worked exactly as designed, and in working perfectly it
made a completely non-functional provider invisible: every analysis succeeded,
the interface reported no error, and a user would have noticed nothing.

The failure was detectable only because each analysis records which provider
actually produced it, and because results were grouped by that record rather than
by configuration. Grouping by configuration would have reported that both
providers performed comparably while measuring the same provider twice. The system
is therefore single-provider in effect though dual-provider in architecture.

Two measurement errors occurred and were corrected, described in Section 6.8;
both produced plausible but wrong numbers, and both arose because the cache is
keyed by content.

**Threats to validity.** The corpus is small and narrow: five English-language
computational linguistics papers. There is no ground truth, so Table 5.9 measures
how much was produced rather than whether it was correct. The provider comparison
could not be completed, the insufficient-evidence path was never triggered, each
paper was analysed once per configuration, and the evaluation was performed by the
project team rather than independently.

## 5.16 Chapter Summary
The system passes 538 automated tests with no failures, and static analysis, type
checking and the production build are clean. Live testing verified per-user
isolation across 26 checks, including direct database access that bypassed the
application. The cache reduces a repeat analysis from 32.4 seconds and three
model calls to about 3 seconds and none. The provider evaluation produced a
negative finding: the configured primary cannot process papers at its free tier,
and the fallback concealed this.

# CHAPTER 6: DISCUSSION

## 6.1 Introduction
This chapter interprets the results of Chapter 5 against the project objectives,
identifies the strengths of the delivered system, records the challenges
encountered, and states the limitations and mitigations.

## 6.2 Achievement of Project Objectives

@TABLE|Table 6.1|Achievement of project objectives with supporting evidence
| Objective | Evidence | Result |
|---|---|---|
| 1. Upload research papers | 15 live uploads across three configurations | Achieved |
| 2. Extract text from PDFs | Table 5.7; documents without text rejected | Achieved |
| 3. Structured summaries and key findings | 10 summaries, median 8 findings | Achieved |
| 4. Identify research gaps | 10 gap analyses, median 9 gaps | Achieved |
| 5. Literature review content | 10 reviews, median 8 themes | Achieved |
| 6. Cross-paper literature review | Verified live over two papers; Figure 4.8 | Achieved |
| 7. Usable research assistant interface | Figures 4.4 to 4.11; clean build | Achieved |
| 8. Secure accounts and per-user ownership | 26 live checks, no failures | Achieved |
| 9. Reduce duplicate AI processing | 32.4 s to 3.2 s, no model call | Achieved |
| 10. Owner-controlled provider configuration | Figure 4.10; disabled provider unreachable | Mechanism achieved |

## 6.3 System Strengths
Four strengths are worth stating. **Isolation is a database property**, so a
forgotten ownership filter returns nothing rather than everything. **Grounding is
enforced structurally**, since output is constrained to a schema and discarded when
it does not conform. **Provenance is recorded for every analysis**, which is what
made the central evaluation finding detectable. **Duplicate inference is avoided
without compromising privacy**, because the cache is keyed by content while each
user retains a separate private record.

## 6.4 Challenges Encountered
The most significant challenges were a data isolation defect that no test
detected, provider rate limiting that initially presented as generic server
errors, an infrastructure layer that concealed provider error messages, and a
fallback mechanism so effective that it hid a non-functional provider. Each is
described in the sections that follow.

## 6.5 Technical Challenges
**A database change broke every library read.** Queries were updated to select
new provenance and cache columns before the corresponding migration had been
applied. The database rejected the entire request rather than the missing
columns, so all reads failed. The fix retries and degrades one migration level
at a time, returning the columns that do exist rather than failing completely.

**An external service concealed provider error messages.** The custom domain is
served through a content delivery network that replaces an origin error body
with a short generic message, so every failed analysis looked identical and
carried no explanation. Addressing requests directly to the application origin
returned the real provider message, which is how the token limit in Section 5.14
was identified. Without this step the central finding of the evaluation would
have remained invisible.

## 6.6 AI Provider and Rate-Limit Challenges

Provider rate limiting was encountered repeatedly and shaped several design
decisions.

During earlier development the project used a different provider whose free tier returned frequent rate-limit responses, initially surfaced as generic server errors. Handling was rewritten to be vendor-neutral: rate limits are recognised, retry information is passed through, an exhausted quota is distinguished from temporary throttling, and hidden retries inside client libraries were disabled because they multiply cost without informing the caller.

## 6.7 Authentication and Data Ownership Challenges
The most instructive defect in the project was in data isolation. An earlier
version of the backend connected to the database using a privileged key that is
designed to bypass Row Level Security. Every policy was present and correctly
written, and every policy was inert. The application worked, every feature
behaved correctly and the automated tests passed, because at the unit level
nothing was wrong.

The defect was found by signing in as a second real account and checking whether
the first account papers were visible. The fix, described in Section 4.10, was
to connect as the signed-in user so that the database resolves the caller
identity and applies the policies itself.

Records created before authentication existed remain unowned. They were
deliberately neither deleted nor assigned to an owner who could not be
established, and they are unreachable because a null owner never matches an
authenticated identity.

## 6.8 Same-Paper Cache Challenges
Because the cache is keyed by content rather than by user or provider, a cached
result can be returned where a fresh analysis was expected. This affected
measurement twice during evaluation, as described in Section 5.15: once when two
papers returned successful responses under a configuration intended to exercise
a different provider, and once when the cache test own fixture was still cached
from a previous run.

Neither was a defect in the cache, which behaved as designed. Both were defects
in measurement, resolved by clearing the relevant cache rows before measuring.
The episode is recorded because it demonstrates a general risk: a
correctness-preserving optimisation can invalidate an experiment silently.

## 6.9 Limitations
**Effectively single-provider.** The architecture supports two providers and the
fallback is verified, but the configured primary cannot process papers at its
free tier, so genuine redundancy is not currently achieved.

**No verification of truth.** The system is grounded, which is weaker and more
precise than accurate: output is constrained to the supplied document and
non-conforming output is discarded, but nothing establishes that a summary is
correct. Generated content requires researcher verification before it is relied
upon or cited.

**No labelled benchmark dataset**, so no accuracy figure can be reported.

**Full-document context rather than active retrieval.** This is appropriate for
papers that fit a context window, and every paper tested did, but it bounds
document size.

**Extraction quality varies with document structure**, and scanned documents are
rejected because there is no optical character recognition.

**A bounded window after sign-out**, in which a revoked token is accepted for up
to about five seconds, as a deliberate trade against contacting the
authentication service on every request.

**Cache depends on identical normalised content and on versioning**: a document
differing after normalisation is treated as different, and the analysis version
must change when the analysis method changes.

**Narrow evaluation:** five papers from one discipline, analysed once per
configuration, evaluated by the project team.

## 6.10 Mitigation Strategies
Provider dependence is mitigated by the two-provider architecture itself, which
would deliver genuine redundancy as soon as a second provider capable of
accepting a full paper is configured; the routing, availability control and
provenance recording required already exist and are tested. Rate limiting is
mitigated by accurate error reporting and by the cache.

The absence of truth verification is mitigated by design decisions that make output
checkable, and the user manual states that generated content should be checked
against the paper before being cited. The absence of a labelled benchmark is
mitigated by reporting only observable properties, and in the longer term by the
evaluation proposed in Section 7.5.

## 6.11 Chapter Summary
Nine objectives are fully achieved and verified; the tenth is achieved in
mechanism but limited by an external service tier. The challenges encountered
were mostly failures invisible until deliberately checked, which is the main
methodological lesson of the project.

# CHAPTER 7: CONCLUSION AND FUTURE WORK

## 7.1 Conclusion

This project set out to build an AI research paper assistant that accepts
uploaded research papers and produces structured summaries, research gap
analyses and literature review content, delivered as a usable application with
secure per-user accounts. That system was built, deployed and tested, and it is
publicly reachable.

The work that proved most consequential was not the generation itself. The substantial engineering lay around the model call: constraining output to a schema and discarding what does not conform, enforcing isolation in the database rather than in application code, recording which provider actually produced each result, and avoiding duplicate inference through caching.

The evaluation produced a finding of wider interest. The configured primary provider could not process any corpus paper at its free tier, yet every analysis completed because the fallback handled all of them. A redundancy mechanism conceals the failure it compensates for, and this was detectable only because the system records the provider that actually served each request.

## 7.2 Achievement of Objectives
All ten objectives were addressed. Nine are fully achieved and supported by
evidence in Chapter 5: upload, extraction, summarisation, gap identification,
literature review generation, cross-paper review, a usable interface, secure
per-user ownership, and reduced duplicate processing. The tenth,
owner-controlled provider configuration, is implemented and verified as a
mechanism, but its practical effect is constrained by the service tier described
in Section 6.6.

## 7.3 Contributions of the Project
The project contributes a **working, deployed application** performing grounded
document analysis with per-user isolation, provider fallback and content-addressed
caching; a **demonstration that grounding can be enforced structurally**, since
schema validation with discard-on-mismatch makes output validity a property of the
system rather than a request to the model; and a **methodological observation**,
that automatic fallback hides the failure it compensates for, so such a system must
record which path was taken and be evaluated by that record rather than by
configuration.

## 7.4 Limitations
The limitations detailed in Section 6.9 are summarised here. The system is
effectively single-provider at present. It does not verify the truth of what it
generates, only that the output derives from the supplied document and is
structurally valid. It has no labelled benchmark and therefore reports no
accuracy figure. It processes documents that fit within a model context window
rather than retrieving from a corpus, and it cannot process scanned documents. A
revoked session remains valid for a few seconds. The evaluation covers five
papers from a single discipline, assessed by the project team.

## 7.5 Future Improvements
The following are proposed as future work and are **not** implemented.

1. **Ground-truth evaluation.** Assemble papers annotated by domain experts with
   the gaps a human reader identifies, and score system output against them. This
   is the highest-value next step, because it is the only way to show that the
   right gaps were found.
2. **Restore genuine provider redundancy** with a second provider able to accept a
   full paper, on a paid tier or by adding a provider.
3. **Deliberately exercise the insufficient-evidence path** with documents that
   lack the requested content.
4. **Production vector retrieval**, using the prepared embedding and pgvector
   infrastructure, for documents larger than a context window.
5. **Citation-aware evidence linking**, so each statement points to its supporting
   passage.
6. **Streamed partial results**, so the summary can be read while gap analysis
   continues.
7. **Optical character recognition**, evaluation **beyond one discipline**, and a
   **human evaluation study** of usefulness.
8. **Additional features**: document versioning, reference extraction, a research
   knowledge graph, multilingual support and usage analytics.

## 7.6 Final Summary
ResearchForge is a deployed AI research paper assistant that analyses uploaded
papers, generating summaries, research gaps and literature review content
grounded in the document, with per-user isolation enforced by the database,
owner-controlled provider configuration, automatic fallback and
content-addressed caching. It passes 538 automated tests with no failures and has
been verified live against the deployed system.

Its most valuable results came from checking what the system actually did rather
than trusting what the code implied: policies that were correct but inert, a
fallback that concealed a dead provider, and a cached result that would have been
recorded as another provider success.

# REFERENCES

Beltagy, I., Lo, K., & Cohan, A. (2019). *SciBERT: A pretrained language model
for scientific text* (arXiv:1903.10676). arXiv.
https://arxiv.org/abs/1903.10676

Devlin, J., Chang, M.-W., Lee, K., & Toutanova, K. (2018). *BERT: Pre-training
of deep bidirectional transformers for language understanding*
(arXiv:1810.04805). arXiv. https://arxiv.org/abs/1810.04805

Lewis, P., Perez, E., Piktus, A., Petroni, F., Karpukhin, V., Goyal, N.,
Kuttler, H., Lewis, M., Yih, W.-t., Rocktaschel, T., Riedel, S., & Kiela, D.
(2020). *Retrieval-augmented generation for knowledge-intensive NLP tasks*
(arXiv:2005.11401). arXiv. https://arxiv.org/abs/2005.11401

Vaswani, A., Shazeer, N., Parmar, N., Uszkoreit, J., Jones, L., Gomez, A. N.,
Kaiser, L., & Polosukhin, I. (2017). *Attention is all you need*
(arXiv:1706.03762). arXiv. https://arxiv.org/abs/1706.03762

Wang, A., Cho, K., & Lewis, M. (2020). *Asking and answering questions to
evaluate the factual consistency of summaries* (arXiv:2004.04228). arXiv.
https://arxiv.org/abs/2004.04228

@PAGEBREAK

# APPENDIX A: PROJECT SCHEDULE
The project followed a thirteen-milestone roadmap recorded in the project plan,
in which each milestone ended with a test and a review before the next began.
The observed development period was 1 to 4 September 2026, taken from the
repository file history rather than estimated.

@TABLE|Table A.1|Project milestones and completion status
| Milestone | Deliverable | Status |
|---|---|---|
| 0. Setup and planning | Repository structure, project plan, coding rules | Complete |
| 1. Environment and foundations | Environment, dependencies, health endpoint, tests | Complete |
| 2. Database foundation | Supabase project, initial migrations, verified connection | Complete |
| 3. PDF ingestion | Upload endpoint and extraction verified on real papers | Complete |
| 4. Chunking and embedding | Chunking with metadata, embeddings stored | Not built, see note |
| 5. Retrieval and question answering | Grounded answers from retrieved passages | Not built, see note |
| 6. Summarisation | Structured summaries with key findings | Complete |
| 7. Research gaps | Evidence-backed gap analysis | Complete |
| 8. Literature review | Literature review content generation | Complete |
| 9. Frontend foundation | Layout, API client, upload and library pages | Complete |
| 10. Frontend features | Summary, gaps and review pages with error states | Complete |
| 11. Deployment | Live deployment with a working public URL | Complete |
| 12. Evaluation and documentation | Evaluation against real papers, results recorded | Complete |

Work added after the original roadmap comprised authentication and per-user
isolation, owner AI configuration, the analysis cache, and provider availability
control, corresponding to migrations 003 to 006.

**Note on milestones 4 and 5.** These were planned but deliberately not built. Measurement during milestone 3 established that every corpus paper fits within a single context window without chunking (Table 5.7), so retrieval would have introduced a failure mode without addressing a problem the system had. The infrastructure remains as prepared scaffolding and is not called in production.

# APPENDIX B: SOURCE CODE

This appendix reproduces representative extracts that implement the claims made
in the report. The complete source is in the project repository. No credential,
key or environment value appears in any extract.

## B.1 Data isolation

The single change that converted isolation from an application responsibility
into a database guarantee. The anonymous key identifies the project and the user
own access token identifies the person, so PostgreSQL resolves the caller
identity and applies every Row Level Security policy.

@CODE
self._headers = {
    "apikey": settings.supabase_anon_key.strip(),   # identifies the PROJECT
    "Authorization": f"Bearer {token}",             # identifies the PERSON
    "Content-Type": "application/json",
}
@ENDCODE

An earlier version used a privileged key here, which is designed to bypass Row
Level Security and therefore made every policy inert while every feature
continued to work.

## B.2 Provider routing and the retryable whitelist

Fallback is permitted only for failures on an explicit whitelist, so that a
newly introduced error type does not silently become retryable.

@CODE
PROVIDERS = ("anthropic", "groq")
OPPOSITE = {"anthropic": "groq", "groq": "anthropic"}

def is_retryable(error: LLMError) -> bool:

    A rate limit or a temporary outage is worth a second vendor. A bad PDF, a
    validation failure, a missing key or an unknown model is not: retrying
    those spends a second quota to produce the same error.
    return isinstance(error, (LLMRateLimitError, LLMTransientError))
@ENDCODE

## B.3 Provider availability

A provider that the owner has disabled is never constructed, so no code path can
call it. Availability is applied when the router is built rather than checked
when it is used.

@CODE
def build_routed_provider(primary, settings, enabled=None):
    allowed = tuple(enabled) if enabled else PROVIDERS
    fallback_name = OPPOSITE[primary]
    fallback = (_construct(fallback_name, settings)
                if fallback_name in allowed else None)
    return RoutedLLMProvider(primary=_construct(primary, settings),
                             fallback=fallback)
@ENDCODE

## B.4 Document identity and caching

Normalisation before hashing means two renderings of the same paper produce the
same identity. The analysis version is part of the key so that the cache can be
invalidated deliberately when the analysis method changes.

@CODE
ANALYSIS_VERSION = "v1"   # declared once; a test asserts this

def normalise_text(text: str) -> str:

    Two PDFs of the same paper can differ in invisible ways - ligatures,
    non-breaking spaces, line-ending style - and would otherwise hash
    differently and be analysed twice.
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).strip()

def content_hash(text: str) -> str:
    payload = f"{ANALYSIS_VERSION}\n{normalise_text(text)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
@ENDCODE

## B.5 Structured output validation

Output that does not match the declared schema is discarded rather than
repaired, which is the mechanism behind the grounding claim.

@CODE
try:
    return output_model.model_validate(parsed)
except ValidationError as exc:
    raise LLMResponseError(
        "The provider returned an analysis that did not match the expected "
        "structure, so it was discarded rather than partially used."
    ) from exc
@ENDCODE

## B.6 Row Level Security policy

Ownership is defaulted by the database and enforced by policy, so a row cannot
be created without an owner and cannot be read by another user.

@CODE
ALTER TABLE papers ALTER COLUMN user_id SET DEFAULT auth.uid();

CREATE POLICY papers_select_own ON papers
    FOR SELECT USING (user_id = auth.uid());

CREATE POLICY lrp_owner_only ON literature_review_papers AS RESTRICTIVE
    USING (EXISTS (SELECT 1 FROM literature_reviews r
                   WHERE r.id = review_id AND r.user_id = auth.uid()));
@ENDCODE

@PAGEBREAK

# APPENDIX C: DATASET SAMPLES

## C.1 Evaluation corpus

Five real, openly available arXiv papers form the evaluation corpus. No paper
was written for this project and no PDF was modified. Metadata was retrieved
from the arXiv application programming interface rather than transcribed.

@TABLE|Table C.1|Evaluation corpus with source and licence information
| arXiv ID | Title | Year | Source | Licence |
|---|---|---|---|---|
| 1706.03762 | Attention Is All You Need | 2017 | arxiv.org/abs/1706.03762 | arXiv open access |
| 1810.04805 | BERT: Pre-training of Deep Bidirectional Transformers | 2018 | arxiv.org/abs/1810.04805 | arXiv open access |
| 1903.10676 | SciBERT: A Pretrained Language Model for Scientific Text | 2019 | arxiv.org/abs/1903.10676 | arXiv open access |
| 2004.04228 | Asking and Answering Questions to Evaluate Factual Consistency | 2020 | arxiv.org/abs/2004.04228 | arXiv open access |
| 2005.11401 | Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks | 2020 | arxiv.org/abs/2005.11401 | arXiv open access |

## C.2 Manifest record format

Each corpus entry is recorded with the following fields.

@CODE
paper_id, title, authors, author_count, year, published,
venue_or_source, primary_category, doi, url, pdf_url,
licence, file, file_size_bytes
@ENDCODE

## C.3 Sample of extracted input

The opening of paper 1903.10676 after extraction and normalisation, as the model
receives it.

@CODE
SciBERT: A Pretrained Language Model for Scientific Text
Iz Beltagy Kyle Lo Arman Cohan
Allen Institute for Artificial Intelligence, Seattle, WA, USA
Abstract
Obtaining large-scale annotated data for NLP tasks in the scientific
domain is expensive and time consuming. [...]
@ENDCODE

## C.4 Sample of stored output

An abridged extract from the stored analysis of the same paper. The provenance
fields record which provider actually produced the analysis.

@CODE
{
  "document": { "page_count": 6, "extracted_characters": 23767,
                "chunk_count": 1, "truncated": false },
  "model_provider": "anthropic",
  "model_used": "claude-opus-5",
  "fallback_used": false,
  "cache_hit": false,
  "processing_time_ms": 72564,
  "summary": { "key_findings": [ "..." ] },
  "research_gaps": { "identified_gaps": [ "..." ],
                     "insufficient_evidence": false }
}
@ENDCODE

No user identifier, email address or credential appears in stored analysis
records reproduced here.

@PAGEBREAK

# APPENDIX D: USER MANUAL

## D.1 Creating an account
Open the ResearchForge web address and choose **Sign up**, then either enter an
email address and password or choose **Continue with Google**. If you register
by email, confirm the address using the message sent to you.

@FIG|02-signup|Figure D.1|ResearchForge account creation screen

After signing in you arrive at the dashboard. Your library is empty, and no other
user papers are ever visible to you.

## D.2 Uploading and analysing a paper
On the dashboard, drag a PDF onto the upload area or use the file chooser.

@FIG|04-upload|Figure D.2|Research paper upload and analysis progress

A new paper takes roughly one and a half minutes, because three separate
grounded passes are made over the whole document. If the same paper has already
been analysed the result returns in about three seconds, and nothing about the
other person is shown to you.

If your PDF is rejected it is almost certainly a scanned document. The system
requires extractable text and refuses documents without it rather than producing
confident output about a document it cannot read.

## D.3 Viewing analysis results
When analysis completes you are shown the summary and key findings, the
identified research gaps and stated limitations, and literature review content.
Where the paper does not support a section, the system reports insufficient
evidence instead of generating text. Treat the output as a guide to reading
rather than a substitute for it, and check any claim against the paper before
citing it.

## D.4 Managing account settings
Open **Settings** to change your display name, change your password, or sign
out. Changing your password requires your current password.

@FIG|09-settings-account|Figure D.4|Account settings for an authenticated user

Signing out takes effect within about five seconds.

## D.5 Owner AI configuration
If your account is registered as an application owner, Settings additionally
shows AI Configuration, illustrated in Figure 4.10. The **primary provider**
setting selects which provider leads, and the other enabled provider
automatically becomes the fallback. The **availability** controls switch a
provider off entirely, and a provider that is off is never called. The
configuration in which no provider is enabled cannot be saved. Normal users do
not see this panel.

## D.6 Viewing your research library
Open **My Papers** to see everything you have analysed, and select any paper to
reopen its summary, key findings and research gaps. Only you can see, open or
delete your papers, and this is enforced by the database rather than the
application.

## D.7 Generating literature reviews
Literature review content for a single paper is produced as part of that paper
analysis and appears with its results. No separate action is required.

## D.8 Cross-paper literature review
Open **Literature Review** to build a review across several of your saved
papers. Select the papers to include and generate the review. The feature
requires more than one paper, and only papers in your own library can be
selected.

## D.9 Signing out and password recovery
Use **Sign out** in Settings to end your session. If you have forgotten your
password, choose **Forgot password** on the sign-in page and follow the link sent
to your email address.

## D.10 Troubleshooting

@TABLE|Table D.1|Common problems and their resolution
| Symptom | Cause | What to do |
|---|---|---|
| PDF rejected as having no extractable text | The file is a scanned image | Use a text-based PDF; the system has no optical character recognition |
| Upload rejected as too large | The file exceeds the size limit | Use the published version rather than a large preprint bundle |
| Analysis seems slow | Normal; three passes are made over the whole paper | Allow about one and a half minutes for a new paper |
| Still signed in immediately after signing out | Sessions are verified with a short cache | Wait about five seconds |
| An analysis fails with a rate-limit message | The AI provider has throttled requests | Wait and try again; the message states the provider guidance |

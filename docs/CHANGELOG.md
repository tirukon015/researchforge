# Changelog

Significant changes, newest first. Keep entries short. Every feature, route, integration,
architecture or design-system change gets an entry (see [MAINTENANCE.md](MAINTENANCE.md)).
Entries before 2026-09-26 were reconstructed from Git history.

## 2026-09-26

### Added
- Maintenance baseline docs: `PROJECT_SPEC.md`, `DESIGN_SYSTEM.md`, `COMPONENT_MAP.md`,
  `FEATURES.md`, `CHANGELOG.md`, `MAINTENANCE.md`, plus a quick-reference section in
  `ARCHITECTURE.md`.

## 2026-09-25

### Added
- Portfolio case study: `PROJECT_DOCUMENTATION.md`, `CASE_STUDY.md`, `SCREENSHOT_PLAN.md`,
  13 screenshots, 5 generated diagrams, fictional demo-paper sources (PR #1).

## 2026-09-10

### Changed
- `CLAUDE.md` removed from the public GitHub repository (it is kept locally).

## 2026-09-06

### Added
- Five-paper evaluation corpus and evidence in `results/evaluation/`; report, presentation
  and poster deliverables; Mermaid diagram sources.

## 2026-09-04

### Added
- Authentication (email/password), private per-user libraries, public landing page at `/`
  (the app moved to `/dashboard`).
- Google sign-in; Claude + Groq provider routing with owner-only AI configuration.
- Account settings; reuse of analyses by content hash; owner-controlled provider availability.
- Research-themed backdrop and content-aware card motifs.

### Fixed
- PKCE flow pinned and every redirect derived from the running origin.
- Logout takes effect promptly (auth cache cut to 5 s).
- Library keeps working when the schema is behind the code (per-migration degradation).
- Mobile header overflow.

## 2026-09-03

### Fixed
- Library queries and Gemini rate-limit handling hardened.
- A publishable Supabase key in the private slot is refused instead of showing an empty library.

## 2026-09-02

### Added
- Google Gemini provider (later retired); frontend rebuilt as a research dashboard; top
  navigation, themes, and the research library end to end.

### Fixed
- Frontend calls the backend same-origin, so the custom domain works.
- Gemini errors translated by status code; logo served without the image optimizer.

## 2026-09-01

### Added
- Analysis MVP: PDF upload → extraction → summary, research gaps, literature review
  (stateless).

## 2026-08-11

### Added
- Project structure, rules and plan; FastAPI foundation with `/health` and tests
  (Milestone 1); initial database schema (Milestone 2).

### Technical
- Embedding decision D6 locked to Jina `jina-embeddings-v3` at 1024 dimensions.

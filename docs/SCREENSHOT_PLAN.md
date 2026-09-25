# Screenshot Plan: ResearchForge Case Study

Every image listed here exists in `docs/screenshots/case-study/`. None is a mock-up.
The app screenshots come from the **live production deployment**
(`https://researchforge.rukon.dev`) on **25 September 2026**. The diagrams were drawn from
the code at commit `33bc740`.

## How the screenshots were made

| Item | Detail |
|---|---|
| Application | The deployed production build (Vercel project `researchforge`). Not a local build, not a mock-up. |
| Account | The owner's own account. Its display name is **blurred** in every signed-in capture by a CSS filter added at capture time (`.account__trigger { filter: blur(7px) }`). No other visual change was made. |
| Demo data | Two short papers written for this purpose and **labelled fictional on their first line** (`demo-data/`). All authors, institutions, participants, numbers and citations in them are invented. They are *not* sample papers: `data/samples/` holds real, openly licensed papers only (CLAUDE.md §5), and none of this touches `results/`. |
| What was run | Demo paper 1 was analysed once, then re-uploaded, which hit the content-hash cache with no model call. Demo paper 2 was analysed once. Both were saved. One cross-paper review was generated, and the capture needed a second run, so **two review rows exist**. Model spend: 8 Claude calls (3 + 3 + 1 + 1), plus the Groq attempts that were refused and triggered each fallback. |
| Library view | Filtered with the app's own search box to `DEMO`, so none of the owner's other papers appear. |
| Browser | Chrome, at 160% page zoom so a very wide window renders like a ~1450px viewport. The captures are JPEG from the browser tool, cropped and saved as PNG. The public pages (01, 02, 12) came from a clean headless Chrome profile with no session. |
| Where the demo data lives now | Kept in the owner's production library at their request: 2 papers, 2 analyses, 2 cross-paper reviews. Delete them from **My Papers** if they're no longer wanted. The reviews can only be removed through the API, because the UI has no review list. |

## What never appears

API keys, tokens, `.env` contents, the Supabase URL or keys, email addresses, the account
name (blurred), anyone else's papers, a terminal, an IDE, or the DevTools console.

**One capture was thrown away:** the first Settings screenshot showed the full name and email
field. It was deleted and never copied into the repo or the portfolio. `10_owner_ai_settings.png`
is scrolled so the Account section is off-screen.

---

## Screenshot inventory

| # | File | Page / feature | Purpose | Case-study section | Priority |
|---|---|---|---|---|---|
| 01 | `01_landing_hero.png` | `/` public landing | Hero, first impression | Hero / Overview | High |
| 02 | `02_sign_in_mobile.png` | `/sign-in` at 500px | Auth UI, mobile | Source for 13 | Low |
| 03 | `03_analysis_in_progress.png` | `/dashboard` during analysis | Shows the real wait and honest progress | How it works | High |
| 04 | `04_analysis_result_provenance.png` | `/dashboard` result card | Provenance badges: provider, fallback, model | Providers and fallback; homepage thumbnail | High |
| 05 | `05_research_gaps_evidence.png` | `/papers/[id]` Research Gaps tab | Gaps carry quoted evidence | Engineering approach (grounding) | High |
| 06 | `06_single_paper_literature_review.png` | `/papers/[id]` Literature Review tab | The review states its own scope | Engineering approach (grounding) | High |
| 07 | `07_paper_details_provenance.png` | `/papers/[id]` Paper Details tab | Measured facts vs generated content | Library | Medium |
| 08 | `08_workspace_selection.png` | `/workspace` | Picking papers for a cross-paper review | Library and cross-paper review | High |
| 09 | `09_cross_paper_review.png` | `/literature-review` after generation | Cross-paper output, sources named | Library and cross-paper review | High |
| 10 | `10_owner_ai_settings.png` | `/settings` owner AI section | Primary/fallback choice, availability | Providers and fallback | High |
| 11 | `11_dark_mode_research_gaps.png` | `/papers/[id]` dark theme | Theming; stated limitations | Interface | Medium |
| 12 | `12_landing_mobile.png` | `/` at 500px | Responsive layout | Source for 13 | Low |
| 13 | `13_mobile_landing_and_sign_in.png` | 12 + 02 side by side | One landscape figure instead of two tall ones | Interface | Medium |

## Per-screenshot detail

### 01 — Landing hero
- **Show:** headline, CTAs, the three promises, the illustrative analysis panel.
- **Don't show:** anything signed-in.
- **Caption:** "The public landing page at researchforge.rukon.dev. Everything past it requires an account."
- **Description:** Public marketing page. The right-hand panel is an illustration built from divs (`HeroVisual.tsx`), not a real analysis.
- **Privacy check:** ✅ No session, no data.

### 02 / 12 / 13 — Mobile
- **Show:** landing and sign-in at 500px (headless Chrome on Windows can't go below about 500px).
- **Don't show:** any typed credentials. Both forms are empty.
- **Caption (13):** "Landing and sign-in at mobile width. Google sign-in uses the PKCE flow, so no token ever appears in a URL."
- **Privacy check:** ✅ Clean profile, empty forms.

### 03 — Analysis in progress
- **Show:** progress bar, elapsed time, the five listed steps, the note that the backend does not report which step is running.
- **Caption:** "Analysis in progress. The steps are listed but none is marked complete, because the backend does not report which one is running."
- **Privacy check:** ✅ Name blurred; only the demo file.

### 04 — Result with provenance
- **Show:** `ReyesLind_Peer_Circles_DEMO.pdf`, badges **Claude · Fallback used · claude-opus-5**, summary tab.
- **Why it matters:** Groq was the configured primary. The record shows Claude actually produced the analysis, which is the provenance feature working.
- **Caption:** "Provenance on a real result: Groq was primary, Claude wrote it, and the record says so."
- **Privacy check:** ✅

### 05 — Research gaps with evidence
- **Show:** stated limitations, then Gap 1 with *Why it matters* and *Evidence from the paper*, quoting the demo paper.
- **Caption:** "Each gap carries the paper's own wording as evidence. Evidence is a required field in the response schema, so a gap returned without it fails validation."
- **Privacy check:** ✅

### 06 — Single-paper literature review
- **Show:** the blue scope notice. The model itself noted that the paper is labelled fictional.
- **Caption:** "The single-paper review states its own scope: only the prior work this paper discusses, with the cited works not consulted."
- **Privacy check:** ✅ The cited authors (Marlowe & Chen, etc.) are invented.

### 07 — Paper details
- **Show:** pages 3, characters 7,393, 6 KB, single document, claude-opus-5, truncated: No.
- **Caption:** "Measured document facts, kept apart from anything a model generated."
- **Privacy check:** ✅

### 08 — Workspace selection
- **Show:** the two demo papers ticked, the Selected papers panel, the Generate button.
- **Caption:** "Choosing papers for a cross-paper review. The panel refuses to continue with fewer than two."
- **Privacy check:** ✅ Library filtered to `DEMO`.

### 09 — Cross-paper review
- **Show:** title, papers included, scope notice, themes attributed per paper.
- **Caption:** "The cross-paper review names the papers it was built from and attributes each theme to its source paper."
- **Privacy check:** ✅

### 10 — Owner AI settings
- **Show:** primary = Groq Qwen 3.6 27B, fallback = Claude (automatic), both providers enabled.
- **Don't show:** the Account section (name, email). It is scrolled out of frame.
- **Caption:** "The owner-only control. Choosing a primary makes the other provider the fallback; switching one off removes it from routing entirely. API keys are never stored or shown here."
- **Privacy check:** ✅ Verified no `@` in frame.

### 11 — Dark mode
- **Show:** saved paper, Research Gaps tab, dark theme. The theme was switched back to Light after capture.
- **Caption:** "Dark theme. The limitations the authors state are listed separately from the gaps the analysis identifies."
- **Privacy check:** ✅

---

## Diagrams (`docs/screenshots/case-study/diagrams/`)

The source is `build_diagrams.py`, which writes the SVG files; headless Chrome renders the PNGs.
Legend: **solid blue** is current, **violet** is an external service, **dashed** is planned
scaffolding that nothing calls, **dotted** is retired.

| File | Shows | Case-study section |
|---|---|---|
| `architecture.svg/.png` | Vercel single origin, two services, Supabase Auth and Postgres (RLS), Anthropic, Groq; Jina/pgvector as planned, Gemini as retired | Architecture |
| `workflow.svg/.png` | The nine-step user journey plus error, cache and owner branches | How it works |
| `data-flow.svg/.png` | One analysis from bytes to response; cache and library writes | Architecture |
| `ai-pipeline.svg/.png` | `RoutedLLMProvider` decision logic | Providers and fallback |
| `database.svg/.png` | Tables, foreign keys, RLS, planned `chunks` | Accounts and data ownership |

## Portfolio mapping

The portfolio (`Desktop/Portfolio/public/images/researchforge/`) uses 01, 03–11, 13 and all five
diagrams, with the diagrams resized to 1600px wide. 02 and 12 are kept only as sources for 13.

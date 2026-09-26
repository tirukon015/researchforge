# ResearchForge documentation

Start with [DOCUMENTATION](DOCUMENTATION.md). Everything here describes the
implementation as it actually exists. Where something is designed but not
built, it is marked as not implemented rather than described as though it
works.

## Start here: maintenance baseline (current as of 2026-09-26)

These files describe the application **as it is now**. Where an older document below
disagrees (for example "the application is stateless" or "Gemini is the provider"), these win.

| Document | Read it when you want to know |
| --- | --- |
| [MAINTENANCE](MAINTENANCE.md) | How to make a change without re-auditing the whole project |
| [PROJECT_SPEC](PROJECT_SPEC.md) | What the app must do, its routes, constraints, and what must not change |
| [COMPONENT_MAP](COMPONENT_MAP.md) | Which file implements what, and who uses it |
| [DESIGN_SYSTEM](DESIGN_SYSTEM.md) | Colours, type, components, breakpoints, motion |
| [FEATURES](FEATURES.md) | What is live, built-but-unwired, planned or retired |
| [CHANGELOG](CHANGELOG.md) | What changed and when |
| [PROJECT_DOCUMENTATION](PROJECT_DOCUMENTATION.md) · [CASE_STUDY](CASE_STUDY.md) | Full technical record and portfolio case study |

## Index

| Document | Read it when you want to know |
| --- | --- |
| [DOCUMENTATION](DOCUMENTATION.md) | How the whole system fits together, and what is and is not built |
| [ARCHITECTURE](ARCHITECTURE.md) | The technical design, request lifecycle and data lifecycle |
| [API](API.md) | Every endpoint, its request, response and error codes |
| [DATABASE](DATABASE.md) | The schema, Row Level Security, and why nothing is persisted yet |
| [SETUP](SETUP.md) | How to run it locally |
| [DEPLOYMENT](DEPLOYMENT.md) | How production is built, deployed and verified |
| [ENVIRONMENT](ENVIRONMENT.md) | Every environment variable and where it belongs |
| [SECURITY](SECURITY.md) | Secrets, CORS, upload validation, prompt injection |
| [TROUBLESHOOTING](TROUBLESHOOTING.md) | A specific symptom you are looking at right now |
| [PROJECT_STRUCTURE](PROJECT_STRUCTURE.md) | Where a given file lives and what it does |

## Quick answers

**Is anything saved?** No. The application is stateless. See
[DATABASE](DATABASE.md).

**Why does production still show old code after I pushed?** The Vercel project
has no Git integration. Run `vercel deploy --prod`. See
[DEPLOYMENT](DEPLOYMENT.md).

**Analysis returns 503.** No AI key is configured for the selected provider.
See [TROUBLESHOOTING](TROUBLESHOOTING.md).

**Analysis returns 502 about quota.** The free tier allowance is spent. One
analysis costs three requests. See [TROUBLESHOOTING](TROUBLESHOOTING.md).

**Why was my PDF rejected?** Most often it is scanned, so it has no text layer
and there is no OCR step.

## Related

Project rules and constraints live in [CLAUDE.md](../CLAUDE.md). Milestones and
the decision log live in [PROJECT_PLAN.md](../PROJECT_PLAN.md). Neither is
documentation of the implementation; this folder is.

- [HANDOVER](HANDOVER.md) - what is done, what is blocked, and the exact steps
  to finish. **Read this first if you are picking the project up.**
- [EVALUATION](EVALUATION.md) - the evaluation protocol and scoring rubric,
  fixed before any scoring. No results yet; the experiment needs an API key.
- [AUTH](AUTH.md) - how sign-in works, and the **required Supabase dashboard
  configuration**. Read this first if a sign-in or an email link sends someone
  to the wrong host.

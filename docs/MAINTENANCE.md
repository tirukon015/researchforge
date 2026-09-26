# Maintenance Workflow

How to make future changes **without re-auditing the whole project**. The current codebase
plus these docs are the source of truth:

| Question | Read |
|---|---|
| What must the app keep doing? What must not change? | [PROJECT_SPEC.md](PROJECT_SPEC.md) |
| How is it built? | [ARCHITECTURE.md](ARCHITECTURE.md) (see "Maintenance quick reference" at the end) |
| Where is the code for X? | [COMPONENT_MAP.md](COMPONENT_MAP.md) |
| What does it look like? | [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md) |
| What exists today? | [FEATURES.md](FEATURES.md) |
| What changed recently? | [CHANGELOG.md](CHANGELOG.md) |

Project rules in `CLAUDE.md` (local) still apply: small milestones, no fake data, no secrets,
additive migrations, and ask before overwriting files.

## Normal change process

1. **Understand** the request.
2. **Read** only the relevant docs above.
3. **Locate** the affected files with COMPONENT_MAP, then inspect that code and its direct
   dependencies. Don't inspect unrelated sections.
4. **Before coding, answer briefly:** Which files? Which components? What existing behaviour
   could break? Which docs apply? Is a new reusable component needed, or can an existing one
   be extended? Does it change the design system? Does it change architecture?
5. **Implement only what is needed.** Extend existing components and classes, keep the design
   tokens, and don't rewrite or restyle unrelated code.
6. **Verify with the smallest adequate set:**

   | Change | Run |
   |---|---|
   | Small UI | `cd app && npm run typecheck`, then a visual check of the affected page (light + dark, 1440 + 390px) |
   | Frontend logic | the above + `npm test` |
   | Backend | `pytest tests/<affected>.py`, then `pytest`, then `ruff check src tests` |
   | Major / cross-cutting | `pytest`, `npm test`, `npm run typecheck`, `npm run build`, broader visual QA |

7. **Update docs** when you add or change a feature (FEATURES), route or component
   (COMPONENT_MAP, PROJECT_SPEC), token or reusable class (DESIGN_SYSTEM), or architecture,
   integration or env var (ARCHITECTURE).
8. **Add a CHANGELOG entry.**

## When a full audit *is* warranted

Only when the owner asks for one; for an architecture change, a global design-system change,
a framework migration, a redesign of several unrelated areas, or an app-wide refactor; or when
the docs are found to be seriously out of date. In that case, fix the docs first.

## Guardrails that apply to every change

- Tests stay offline. Never call a paid API from a test.
- Never use the service-role key for a data request.
- Keep the status-code contract and the grounding contract (PROJECT_SPEC §7).
- Migrations: new numbered file, additive only, run manually in the Supabase SQL editor.
- Deploying is manual (`vercel deploy --prod`), because pushing to GitHub does not deploy.
  Confirm the target project is `researchforge` first.

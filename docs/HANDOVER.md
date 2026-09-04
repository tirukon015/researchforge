# Handover: what is done, what is blocked, and exactly how to finish

Written 4 September 2026, at the end of an autonomous working session.

Everything here is either verified or explicitly marked as not verified. No
status in this document is an expectation.

---

## 1. What is blocked, and the exact action for each

Four things could not be completed here. Each is genuinely external: it needs a
credential, a dashboard, or a decision that is not mine to make.

### 1.1 Provider API keys — blocks analysis and the evaluation

Neither key exists anywhere: not in the shell, not in any `.env`, not in
Vercel. Analysis therefore cannot run, and the Claude-versus-Groq experiment
cannot be conducted. **No results were invented in their absence.**

```bash
# Get a key from console.anthropic.com and/or console.groq.com, then:
cd researchforge-main
npx vercel env add ANTHROPIC_API_KEY production
npx vercel env add ANTHROPIC_API_KEY preview
# and/or
npx vercel env add GROQ_API_KEY production
npx vercel env add GROQ_API_KEY preview
```

At least ONE is required. Both gives you the automatic fallback.

### 1.2 Deployment — deliberately held

**The current `main` is not deployed, and this was a judgement call.**

Gemini has been removed from the active workflow as instructed. With no Claude
or Groq key in Vercel, deploying would leave `POST /api/analyze` returning 503
for every user — taking the project's core feature offline on a live URL. The
brief authorises deployment but also requires existing functionality to be
preserved, and gates deployment on "environment configuration verified", which
currently fails.

So: after doing 1.1, run

```bash
cd researchforge-main
npx vercel --prod
```

Then verify with the checks in section 3.

Everything else in the deploy is ready: tests, lint, formatting, type checking
and the production build all pass on this commit.

### 1.3 Database migrations 003 and 004 — not applied

There is no path from this machine to the database: `psql` is not installed and
no `DATABASE_URL` exists. Both migration files are written, reviewed and
non-destructive.

Open **Supabase Dashboard → SQL Editor → New query**, paste each file whole,
run it, and read the verification queries at the bottom of each:

1. `src/db/migrations/003_authentication_and_ownership.sql`
2. `src/db/migrations/004_owner_and_ai_configuration.sql`

Neither contains `DROP`, `TRUNCATE`, or `DELETE`. Both are safe to re-run.

**Your legacy data is untouched by both.** After running them, query (d) at the
bottom of 004 should still report papers = 2, analyses = 2, reviews = 1.

> Authentication and per-user isolation **already work without these**, because
> migration 002's policies do the enforcement and the application supplies
> `user_id` explicitly. 003 adds defence in depth; 004 adds the owner tables and
> the provenance columns. **The owner AI settings will not work until 004 is
> applied** — the tables do not exist yet.

### 1.4 Supabase dashboard settings

**Authentication → URL Configuration → Redirect URLs.** Add both:

```
https://researchforge.rukon.dev/auth/callback
https://researchforge.rukon.dev/reset-password
```

Without the first, Google sign-in returns to the wrong place and the session is
lost. Without the second, password-reset links bounce.

Keep any existing `http://localhost:3000/*` entries for local development.

### 1.5 Granting yourself owner

Two ways. Either is enough.

**Environment (no SQL):**
```bash
npx vercel env add OWNER_EMAIL production   # your account's email address
```

**Database (durable, survives an env change):** after signing in once, find
your id under **Authentication → Users**, then:
```sql
INSERT INTO app_owners (user_id, note)
VALUES ('YOUR-USER-ID', 'project owner')
ON CONFLICT (user_id) DO NOTHING;
```

Until one of these is done, the owner AI configuration section is invisible to
everyone — including you. That is the intended default: nobody is an owner
until somebody is named.

---

## 2. What was completed and verified

| Area | Evidence |
| --- | --- |
| Google sign-in | Button on both account screens; `/auth/callback` builds and is registered as a public route |
| Supabase Google provider | Verified live: `/auth/v1/authorize?provider=google` returns `302 → accounts.google.com` |
| Claude + Groq providers | Implemented; 66 tests across `test_router.py` and `test_groq_provider.py` |
| Automatic fallback | Retryable-only, once per analysis, sticky afterwards; provenance recorded |
| Gemini retirement | Removed from routing, settings and docs; file kept, historical records untouched |
| Owner authorisation | 28 tests covering the 401 / 403 / 200 split; fails closed |
| Dashboard empty-state bug | Fixed: falls back to the most recently saved paper |
| Test suite | **431 passed, 0 failed** |
| Ruff lint | Clean |
| Ruff format | Clean |
| TypeScript | Clean |
| Next.js build | Clean, 15 routes |
| Secrets | No credential file tracked; the forbidden identity appears nowhere |

### Verified earlier in the same session, against live production

Two-account data isolation: **26 checks, 0 failures**, using two real Supabase
accounts against `researchforge.rukon.dev`. User B could not read, list,
search, delete, or cross-review User A's paper. Test accounts and rows were
removed afterwards and the database confirmed back to its original state.

---

## 3. Verifying after you deploy

```bash
# Health: expect library:true, auth:true
curl -s https://researchforge.rukon.dev/health

# Protected route without a token: expect 401
curl -s -o /dev/null -w "%{http_code}\n" https://researchforge.rukon.dev/api/papers

# Owner config without a token: expect 401
curl -s -o /dev/null -w "%{http_code}\n" https://researchforge.rukon.dev/api/owner/ai-config
```

Then, in a browser: sign in with Google, open Settings, confirm the owner
section appears and that switching the primary provider persists across a
reload. Upload a PDF and confirm the analysis result carries a provider badge.

---

## 4. Honest status of the academic deliverables

The brief asks for a report, slides, a poster, a presentation script and an
evaluation. Here is where each genuinely stands.

| Deliverable | Status |
| --- | --- |
| System / application | **Substantially complete**, pending the blockers above |
| Evaluation protocol | **Written** — `docs/EVALUATION.md`, rubric fixed in advance |
| Evaluation results | **Not run.** Requires 1.1. No numbers were invented |
| Dataset manifest | **Not built.** Requires real papers to be selected and processed |
| Report (8,000–12,000 words) | **Not written** |
| Slides, poster, script | **Not built** |

The report, slides and poster were not attempted, and that is a deliberate
choice rather than an oversight. All three depend on:

1. **Real evaluation results**, which need an API key (1.1). A report whose
   Chapter 5 contains invented numbers would be academic misconduct, and the
   brief forbids it explicitly.
2. **Information I do not have**: group member names and student IDs, the
   lecturer's name, the submission date, and the course materials the brief
   asks me to align terminology with. None are in the repository.

Producing a report around those gaps would mean either fabricating them or
leaving placeholders through every chapter — neither of which is worth more
than an honest note here.

**What is ready for the report to draw on**: the architecture is documented in
`docs/ARCHITECTURE.md` and `docs/DATABASE.md`, the AI methodology and fallback
design are documented in code comments and in `README.md`, the evaluation
method is fixed in `docs/EVALUATION.md`, and the test suite is real evidence
for Chapter 5's testing strategy.

---

## 5. Suggested order when you return

1. Add one provider API key (1.1) — five minutes, unblocks the most.
2. Run migrations 003 and 004 (1.3) — ten minutes.
3. Add the two redirect URLs (1.4) — two minutes.
4. Grant yourself owner (1.5) — two minutes.
5. `npx vercel --prod` (1.2), then the checks in section 3.
6. Select the evaluation corpus and run the experiment in
   `docs/EVALUATION.md`. This is the long pole for the report.
7. Write the report once real results exist.

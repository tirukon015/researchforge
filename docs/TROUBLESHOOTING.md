# Troubleshooting

Each entry gives the symptom, the cause, how to confirm it, and how to fix it.
Everything here has either happened to this project or is a failure the code
explicitly handles.

---

## "Backend offline" in the interface

### Locally

**Cause.** The backend is not running, or it is on a port other than 8000.

**Check.**

```bash
curl http://localhost:8000/health
```

**Fix.** Start it from the repository root with the virtual environment active:

```bash
uvicorn src.main:app --reload --port 8000
```

### In production, on the custom domain only, while the vercel.app URL works

**Cause.** `NEXT_PUBLIC_API_BASE_URL` is set to an absolute host. Next.js
compiles that value into the browser bundle, so a page served from the custom
domain calls a different origin, and the CORS allowlist blocks it.

**Check.** Look for the value inside the shipped JavaScript:

```bash
curl -s https://researchforge.rukon.dev/ \
  | grep -o '/_next/static/chunks/[^"]*\.js' | sort -u \
  | while read -r c; do curl -s "https://researchforge.rukon.dev$c" \
      | grep -o 'researchforge-ten\|localhost:8000'; done
```

Any output confirms it. Then check whether the API itself is fine, which it
will be:

```bash
curl https://researchforge.rukon.dev/health
```

A healthy `/health` with an offline indicator is the signature of this fault.

**Fix.** Remove the variable and redeploy. The frontend falls back to a
relative same origin path, which is correct on every domain.

```bash
vercel env rm NEXT_PUBLIC_API_BASE_URL production
vercel deploy --prod
```

---

## 503 from `/api/analyze`

**Cause.** No AI credentials on the server. The message names the missing
variable.

**Check.**

```bash
curl -X POST https://researchforge.rukon.dev/api/analyze -F "file=@paper.pdf"
```

A response naming `GEMINI_API_KEY` confirms it.

**Fix.** Set the key for the selected provider in the Vercel dashboard, then
redeploy. Values are read at cold start, so adding the variable alone changes
nothing.

Confirm which provider is selected before setting a key. If `LLM_PROVIDER` is
`gemini`, an `ANTHROPIC_API_KEY` will not satisfy it. `has_llm_credentials`
checks the selected provider's key specifically, so a leftover key for the
other vendor cannot make the application look ready.

---

## 502 with a quota message

**Cause.** The AI provider's rate or quota limit was reached. On the Gemini free
tier the daily allowance is small, and **one analysis costs three requests**.

**Check.** The response passes the provider's own text through, which names the
metric and the model:

```
Quota exceeded for metric:
generativelanguage.googleapis.com/generate_content_free_tier_requests,
limit: 20, model: gemini-3.7-flash
```

**Fix.** One of:

- Wait for the quota window to reset.
- Switch `LLM_MODEL` to another model, for example `gemini-2.5-flash`. Quota is
  counted per model, so a different model has its own allowance. No code change
  is needed.
- Enable billing on the Google Cloud project.

Confirm your real limits at `https://aistudio.google.com/rate-limit`. Google
does not publish free tier numbers publicly; they are per account.

---

## 502 saying the response did not match the schema

**Cause.** The model returned something that failed validation. The analysis is
refused rather than partially rendered.

**Fix.** Retry. If it persists, lower `LLM_EFFORT` or try a different
`LLM_MODEL`. A model consistently failing a schema is a model problem, not a
document problem.

---

## 502 saying the response was cut off

**Cause.** The model hit the output token limit mid answer. A truncated reply
arrives as a valid looking JSON object with content missing, so it is rejected
rather than used.

**Fix.** Raise `LLM_MAX_OUTPUT_TOKENS`, or analyse a shorter paper.

---

## 422 when uploading a PDF

**Cause.** The file is not a usable PDF. The common case is a **scanned** paper:
an image of a page carries no text layer, and there is no OCR step.

**Check.** Try selecting text in the PDF in a normal reader. If you cannot,
neither can pypdf.

**Fix.** Use a text based PDF. Encrypted and empty files are rejected for the
same reason.

Note that the declared content type is a hint only. The real PDF signature is
verified, so renaming a file to `.pdf` will not get it through.

---

## 413 when uploading

**Cause.** The file is over `MAX_UPLOAD_SIZE_MB`, default 25 MB. Checked against
the real byte count, not a client supplied header.

**Fix.** Compress the PDF, or raise the limit in the environment and redeploy.
The frontend enforces the same limit as a courtesy, so an oversized file is
usually refused before it is uploaded at all.

---

## Analysis times out

**Cause.** Either the Vercel function limit or the frontend timeout.

**Check.** `vercel.json` must set `maxDuration: 300` on `src/main.py`. The
frontend allows ten minutes.

**Fix.** For a genuinely long paper, lower `LLM_EFFORT` to reduce thinking
time, or analyse a shorter document. Chunking activates automatically above
400,000 characters and adds one model call per chunk, which makes very long
papers slower, not faster.

---

## CORS errors in the browser console

**Cause.** The calling origin is not in `CORS_ALLOWED_ORIGINS`.

**Check.**

```bash
curl -s -o /dev/null -D - \
  -H "Origin: https://researchforge.rukon.dev" \
  https://researchforge.rukon.dev/health | grep -i access-control
```

A missing `Access-Control-Allow-Origin` confirms the origin is not allowed.

**Fix.** Add the origin to the comma separated list and redeploy. Never use
`*`. Note that in normal use the frontend is same origin, so a CORS error
usually means something else is calling the API, or that
`NEXT_PUBLIC_API_BASE_URL` has been set.

---

## Production is serving old code

**Cause.** The Vercel project has **no Git integration**. Pushing to `main`
builds nothing.

**Check.**

```bash
vercel project inspect researchforge
```

**Fix.**

```bash
vercel deploy --prod
```

---

## The custom domain serves something different from the vercel.app URL

**Cause.** The domain is aliased to an older deployment.

**Check.**

```bash
vercel inspect <deployment-url>
```

Read the `Aliases` block.

**Fix.** Redeploy to production. All aliases move to the new deployment
together.

---

## `npm run typecheck` reports errors that make no sense

**Cause.** Stale generated route types, or a stale incremental cache. Next.js
writes route types into `.next/`, and `tsconfig.json` includes them.

**Check.** Does `npm run build` succeed while `typecheck` fails? Then the types
are stale, not the code.

**Fix.**

```bash
rm app/tsconfig.tsbuildinfo
cd app && npm run build && npm run typecheck
```

Run the typecheck **after** the build. Both files are git ignored build output.

---

## Frontend and backend disagree about the response shape

**Symptom.** "The server returned a response in an unexpected shape."

**Cause.** `app/src/lib/api.ts` and `src/schemas/analysis.py` have drifted
apart.

**Check.** Compare the field names in the TypeScript interfaces with the
Pydantic models. They are intended to match exactly.

**Fix.** Update whichever is behind. This check exists so drift fails loudly
instead of rendering blank sections.

---

## Database connection problems

There is no database to connect to. `SUPABASE_URL` and
`SUPABASE_SERVICE_ROLE_KEY` are unset, and no endpoint uses the data layer.

If you have connected one and the library still does not work, note that
credentials alone are not sufficient: the library routes are not registered.
See "Remaining work" in [DATABASE](DATABASE.md).

---

## Tests fail after a dependency change

**Check.** The suite is fully offline and needs no API key. If tests are trying
to reach a network, that is the bug.

```bash
pytest -q
ruff check src tests
```

**Fix.** Tests use a fake provider through FastAPI's dependency overrides. A
test that needs credentials has been written wrongly.

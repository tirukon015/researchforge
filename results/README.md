# Results

This folder holds **real evaluation outputs only**.

## Integrity rule

> Every number in this folder must come from an actual script run against real
> papers. Fabricating results is academic misconduct.

If an evaluation has **not** been run yet, the file says **"not yet run"**.
It never contains a placeholder number that could be mistaken for a real one.

## Current status

**Evaluation run on 4 September 2026** against the live production deployment.
Full write-up in `docs/report/PROJECT_REPORT.md`, Chapter 5.

| File | What it holds |
|---|---|
| `evaluation/raw/*.json` | Every complete analysis response, exactly as returned |
| `evaluation/runs_*.json` | One record per run, per pass |
| `evaluation/runs.json` | All runs merged and labelled by pass |
| `evaluation/groq_capacity.json` | Groq's own token-limit refusals, per paper |
| `evaluation/summary.txt` | The aggregated tables reproduced in Chapter 5 |
| `evaluation/isolation_test.txt` | Live two-account isolation run — 26 passed, 0 failed |
| `evaluation/cache_test.txt` | Live cache verification — all signals passing |
| `evaluation/logout_window.txt` | Measured sign-out acceptance window |

### The headline result is a negative one

The planned Claude-versus-Groq comparison **could not be completed**. Groq's
free tier permits 7,000 input tokens per minute; every paper in the corpus
required between 7,920 and 20,362 tokens in a single request, so Groq produced
no analysis at all. Because this is a limit on one request rather than on a
rate, waiting does not help.

The system still completed every paper, because the fallback correctly handed
each one to Claude. That is reported here in full rather than presented as a
successful comparison: grouping the runs by the provider that was *configured*
would have shown Groq performing identically to Claude, while actually
measuring Claude twice.

Three passes were run, and they are kept distinct because merging them would be
meaningless:

| Pass | Configuration | Completed | By the configured provider |
|---|---|---|---|
| A | Claude primary, both enabled | 5/5 | 5/5 |
| B | Groq primary, both enabled | 5/5 | 0/5 |
| C | Groq only, Claude switched off | 0/5 | 0/5 |

### Two measurement errors, corrected and recorded

Both are documented because each produced a plausible-looking wrong number.

1. **A cache hit almost became a Groq success.** The cache is keyed by content,
   not by provider, so two papers analysed moments earlier by Claude returned
   HTTP 200 under a Groq-only configuration without the request ever reaching
   Groq. Clearing those cache rows first gave the real answer: a token-limit
   refusal.
2. **The cache test's own fixture was cached from a previous run**, so its
   "first upload" was a hit and every downstream assertion failed. The test now
   clears its own fixture row before starting.

A third correction was to an assertion rather than a measurement: the isolation
test reported that sign-out did not work, having re-checked two seconds after
signing out when the token-verification cache is five seconds. The window was
then measured directly (`logout_window.txt`) and found to be bounded at ~6 s,
which is the documented behaviour. The test now asserts that contract.

## Required metadata

Every result file must record:

- Date of the run
- Model and model version used
- Prompt version
- Dataset (which papers, which questions)
- Parameters (chunk size, top-K, temperature, …)
- The raw numbers, including the bad ones

Negative and disappointing results are reported here too. Honest limitations
are worth more marks, and more credibility, than flattering numbers.

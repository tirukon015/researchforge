# Results

This folder holds **real evaluation outputs only**.

## Integrity rule

> Every number in this folder must come from an actual script run against real
> papers. Fabricating results is academic misconduct.

If an evaluation has **not** been run yet, the file says **"not yet run"**.
It never contains a placeholder number that could be mistaken for a real one.

## Current status

**No evaluations have been run yet.** The evaluation harness is built in
Milestone 12. See `PROJECT_PLAN.md` §M for the methodology.

## Required metadata

Every result file must record:

- Date of the run
- Model and model version used
- Prompt version
- Dataset (which papers, which questions)
- Parameters (chunk size, top-K, temperature, …)
- The raw numbers, including the bad ones

Negative and disappointing results are reported here too. Honest limitations
are worth more marks — and more credibility — than flattering numbers.

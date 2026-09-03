# Evaluation protocol

**Status: protocol defined, experiment NOT YET RUN.**

This document defines how ResearchForge's AI output is to be evaluated, and how
the two providers are to be compared. It is written **before** any scoring so
the method cannot be shaped by the results.

There are no scores in this file. There will be none until the experiment is
actually run against real papers with real API keys, and the raw records are
committed to `results/`. An evaluation table filled in from expectation rather
than measurement would be fabricated evidence.

## Why the usual metrics do not apply

ResearchForge does not classify or predict. It reads one document and produces
three pieces of structured prose: a summary, a set of research gaps, and a
literature review of the prior work the paper itself discusses.

There is therefore no ground-truth label, so accuracy, precision, recall and
F1 have nothing to be computed against. Reporting them would be a category
error dressed up as rigour. Reference-overlap metrics (ROUGE, BLEU) are
similarly weak here: a good summary of a paper need not share vocabulary with
any particular reference summary, and a paper has no canonical one.

What can be measured honestly falls into two groups.

### Measured automatically, no judgement required

| Metric | Definition | Why it matters |
| --- | --- | --- |
| Completion rate | Analyses returning a valid structured result / analyses attempted | The system either produced a usable answer or it did not |
| Schema validity | Responses passing Pydantic validation on the first attempt | Groq is not schema-constrained, so this differs by provider |
| Latency | Wall-clock ms, from `analyses.processing_time_ms` | Groq's selling point is speed; this is where it would show |
| Fallback rate | Analyses where the primary failed over | Measures provider reliability under real load |
| Failure taxonomy | Counts by error type (429, timeout, validation, extraction) | Distinguishes "the model was wrong" from "the service was busy" |
| Extraction yield | Characters extracted / page count | Flags PDFs where extraction, not the model, is the limiting factor |

These need no rubric and no human. They come out of the stored metadata that
migration 004 added.

### Scored by a human against a rubric

Five dimensions, 1 to 5, defined here in advance.

| Dimension | 1 | 3 | 5 |
| --- | --- | --- | --- |
| **Groundedness** | Contains claims absent from the paper | Mostly traceable; one or two loose statements | Every claim traceable to the source text |
| **Factual accuracy** | Misstates the paper's method or findings | Broadly right, with an imprecision | Method, findings and conclusion all correctly stated |
| **Completeness** | Omits a major section the paper supports | Covers the main points, thin in places | Covers everything the paper supports |
| **Relevance** | Substantially off-topic material | Some padding | Every sentence earns its place |
| **Usefulness** | A researcher would gain nothing | Saves some reading | Would genuinely shorten a literature search |

**Groundedness is the primary dimension.** It is the one the product's whole
design is built around, and the one where an LLM most plausibly fails
invisibly.

### Scoring rules, fixed in advance

1. Outputs are scored **blind**: the provider name is stripped before scoring.
2. Both providers analyse the **same** papers, so differences are not
   attributable to the corpus.
3. A gap or claim is marked ungrounded unless the scorer can point at the
   supporting passage. The burden is on the output, not the reader.
4. An `insufficient_evidence` flag where the paper genuinely lacks that section
   scores **full marks for groundedness**. Correctly declining is the desired
   behaviour, not a failure.
5. Scores are recorded per paper per dimension, never as a single aggregate
   number invented afterwards.
6. Disagreement, if a second scorer is available, is reported rather than
   averaged away.

## Corpus

Target: **10 papers minimum**, open-access, real, with recorded provenance.

`data/dataset_manifest.csv` is the record. Every row must have a real title, a
real source URL, and a real licence. No paper may be listed that has not
actually been downloaded and processed.

Selection criteria, so the corpus is not cherry-picked:

- open access, legitimately redistributable
- a genuine text layer (scanned papers are out of scope and the system refuses
  them by design)
- spread across subfields rather than all from one venue or group
- a range of lengths, including at least one long enough to trigger the
  map-reduce digest path
- at least one paper with **no** explicit limitations section, to test whether
  the gap analysis correctly reports insufficient evidence rather than
  inventing gaps

## Procedure

1. Record the corpus in `data/dataset_manifest.csv`.
2. Set the primary provider to Claude. Analyse all papers. Record every result.
3. Set the primary provider to Groq. Analyse the same papers. Record every
   result.
4. Export the stored metadata (provider, model, fallback, latency) to
   `results/evaluation/raw/`.
5. Strip provider identifiers; score blind against the rubric above.
6. Aggregate. Report per-dimension means with the spread, not a single figure.
7. Write up what the numbers do and do not support.

## What this evaluation cannot establish

Stated here so the write-up cannot overclaim later:

- **Ten papers is a small sample.** It can show a large difference; it cannot
  establish a small one. No statistical significance should be claimed.
- **One scorer is one opinion.** Without a second scorer there is no
  inter-rater reliability, and the rubric scores are informed judgement rather
  than measurement.
- **Groundedness is judged, not computed.** The scorer checks whether a passage
  supports a claim. That is more reliable than an automatic metric here, and
  still not objective.
- **Latency is confounded** by network conditions, model load and time of day.
  It indicates the order of magnitude, not a benchmark.
- **Neither provider's model was trained or fine-tuned by this project.** This
  is inference against hosted foundation models. Differences reflect the
  models as supplied, not anything built here.

## Reproducing it

```bash
# 1. Provide at least one provider key
export ANTHROPIC_API_KEY=...
export GROQ_API_KEY=...

# 2. The corpus is in data/samples/, listed in data/dataset_manifest.csv

# 3. Set the primary provider in Settings (owner only), then analyse each
#    paper through the application. Stored metadata records which provider
#    actually produced each result.

# 4. Export the raw records
#    (See results/evaluation/README.md once the experiment has been run.)
```

The whole test suite runs offline with no key. Only this evaluation needs one.

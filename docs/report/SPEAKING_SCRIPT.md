# ResearchForge — Speaking Script

**BIT 4543 Artificial Intelligence · Project #17**
Target: **20 minutes** presentation + Q&A. Slides: `SLIDES.md`.

**Timing at a glance**

| Slides | Section | Minutes | Running |
|---|---|---|---|
| 1–3 | Problem and objectives | 3:00 | 3:00 |
| 4–6 | How it works | 4:30 | 7:30 |
| 7 | Isolation, and the bug | 2:00 | 9:30 |
| 8–9 | Evaluation and results | 4:00 | 13:30 |
| 10–11 | The Groq finding | 3:30 | 17:00 |
| 12–14 | Verification, limits, conclusion | 3:00 | 20:00 |

**If you are running short on time:** cut Slide 5 to one sentence and compress
Slide 12's cache table. **Never cut Slides 10 and 11** — they are the strongest
part of the presentation.

---

## Slide 1 — Title *(0:30)*

Good morning. Our project is **ResearchForge**, an AI research paper assistant.
It is project seventeen, and it is deployed and live right now at
researchforge dot rukon dot dev — everything you will see today runs on the
public deployment, not a demo build.

I want to say at the start what the most interesting part of this project
turned out to be. It was not getting the AI to work. It was an evaluation that
**failed**, in a way that taught us something we would not have learned if it
had succeeded. I will get to that in about twelve minutes.

---

## Slide 2 — The Problem *(1:15)*

Researchers spend a large share of their time reading papers in order to decide
whether a paper is worth reading properly.

You run a literature search, you get thirty results, and for each one you have
to work out three things: what does it actually claim, what does it leave open,
and how does it relate to everything else you have read. That first pass is
slow, it is manual, and you repeat it for every single document.

Now, the obvious solution is to ask a chatbot. And that is exactly where the
danger is. A general-purpose chatbot will happily answer questions about a
paper it has never read. It will produce a summary that sounds right, and a
citation that does not exist.

And for a researcher, that is **worse than getting no answer at all** — because
a fabricated citation costs more time to detect than the summary ever saved.
So the problem is not "can we summarise a paper". It is "can we summarise a
paper in a way that is *checkable*".

---

## Slide 3 — Objectives *(1:15)*

That shaped our six objectives.

The first is the visible product: summaries, research gaps, and literature
reviews from uploaded papers. That covers four of the five university
requirements, and the fifth — a working application — is the deployment itself.

But objectives two through five are the ones that took the real work.

Objective two is that grounding is enforced **structurally**, not by
instruction. There is a large difference between telling a model to stick to
the document and building a system where output that strays cannot be
displayed.

Objective three: two AI providers, so we do not depend on one vendor.
Objective four: per-user isolation enforced by the **database**, not by our
code. Objective five: the same paper is analysed once, no matter how many
people upload it.

And objective six is to evaluate all of that empirically. That is the one that
produced the surprise.

---

## Slide 4 — Architecture *(2:00)*

Briefly, how it is built.

There is a Next.js frontend and a FastAPI backend, deployed as **one** Vercel
project sharing a single origin. That matters more than it sounds: because they
share an origin, the frontend calls the backend with a relative path. We
previously set an absolute URL and it turned our own custom domain into a
cross-origin caller, which made a perfectly working system report "backend
offline".

The backend is about six and a half thousand lines of Python across thirty-five
modules. Uploads go through pypdf for text extraction, then to a **provider
router**, which is the component that chooses between Anthropic Claude and Groq.

Storage is Supabase PostgreSQL, and we chose PostgreSQL specifically for **Row
Level Security**. That is not a detail — it is the entire mechanism behind
objective four, and I will come back to it.

One thing I want to be explicit about, because it would be easy to overclaim:
**this is not RAG**. There is no embedding step and no vector search. The whole
paper goes into the model's context. The repository does contain embedding
scaffolding, and nothing calls it — we say so in the report so nobody mistakes
it for a working feature.

---

## Slide 5 — The Pipeline *(1:30)*

The pipeline is: extract the text, hash it, check the cache, and if it is new,
run three separate grounded passes — summary, research gaps, literature review.

Two design decisions worth a sentence each.

We run **three separate calls** rather than one prompt asking for all three.
When we asked for everything at once, the gap analysis got noticeably weaker —
the model spent its attention on the summary.

And we identify a document by a **hash of its content**, not by its filename.
So `paper.pdf` and `final_v3.pdf` are the same document if the text is the same.
That is what makes the cache work, and you can see the effect: a new analysis
takes about thirty-two seconds, a repeat takes about three.

Also — a PDF with no extractable text, like a scan, is **rejected** rather than
sent to a model. If you give a language model no text, it will still produce
fluent output. It will just be about nothing.

---

## Slide 6 — Grounding *(1:00)*

This is objective two, and it is the heart of the AI design.

There are four layers. The prompt requires every claim to be traceable to the
supplied text. The output is constrained to a **declared schema**. Output that
fails validation is **discarded — not repaired**. And the model is required to
say *insufficient evidence* rather than fill a gap.

The third one is the one I would draw your attention to. It is tempting, when
a model returns something almost valid, to patch it up. We deliberately do not.
A partially-valid analysis that we repaired would be an **invented** one — and
that is precisely what we are claiming not to do.

I will be honest about the limit, though: grounding reduces fabrication. It
does **not** verify truth. It constrains the model to the paper; it does not
check that it read the paper correctly.

---

## Slide 7 — The Isolation Bug *(2:00)*

This is the part of the project I would most want you to take away, and it is a
bug we wrote ourselves.

Our first version connected to the database using the **service-role key**.
That key is designed to bypass Row Level Security — that is its purpose. So
every security policy we had written was present, correct, and **completely
inert**.

And here is the uncomfortable part: every test passed. The application worked.
Every feature behaved. There was no error anywhere.

The fix is on the slide. We now send the **anonymous key** to identify the
project, and **the signed-in user's own access token** to identify the person.
PostgreSQL then resolves `auth.uid()` to that specific user, and every policy
filters automatically.

The property that gives us is the one worth having: **a forgotten filter now
returns nothing instead of everything.** Isolation stopped being something every
query has to remember, and became something the database enforces.

How did we find it? Not with a unit test — at the unit level nothing was wrong.
We found it by signing in as a second real account and looking at whether we
could see the first account's papers. Sometimes the only way to test something
is to actually do it.

---

## Slide 8 — Evaluation Design *(1:45)*

For evaluation we used five real papers from arXiv — Attention Is All You Need,
BERT, RAG, SciBERT, and a factual-consistency paper. Six to nineteen pages,
unmodified, with metadata pulled from the arXiv API rather than typed in.

Three decisions were needed to make the numbers mean anything, and I want to
flag that **each one corresponds to a mistake we actually made and then fixed**.

First: group results by the provider that **actually answered**, not the one we
configured. Our system records both, and they are not always the same.

Second: **clear the cache between passes.** The cache is keyed by content, not
by provider — so the second pass would have been served the first pass's answer
and we would have recorded a comparison that never happened. This caught us
twice.

Third: **bypass Cloudflare.** Our custom domain is proxied, and Cloudflare
replaces error messages with a bare "error code 502". Every failure looked
identical and told us nothing until we addressed the origin directly.

We ended up with three passes, not two. Claude primary; Groq primary; and — a
pass we did not originally plan — Groq with Claude switched **off** entirely.

---

## Slide 9 — Results *(2:15)*

Here is the results table, and I would like you to look at the last column.

Pass A, Claude primary: five out of five completed, all five by Claude.

Pass B, **Groq** primary: five out of five completed. So the system worked.
But by the configured provider — **zero out of five**.

Pass C, Groq with Claude switched off: **zero out of five completed.**

So: ten analyses were produced successfully, and **every single one of them was
written by Claude**. The output itself is reasonable — a median of eight key
findings and nine research gaps per paper, taking about ninety-nine seconds.

But read those three rows together. **The system completed every paper it was
given, and it never once used the provider we had selected.**

Why did we add pass C? Because after pass B we realised something
uncomfortable: every Groq run had fallen back to Claude, which meant pass B was
not measuring Groq at all — it was measuring the fallback. The only way to
measure Groq was to take away its safety net. And we already had the mechanism:
the owner-controlled provider availability switch. So the experiment doubles as
proof that a disabled provider really is unreachable.

---

## Slide 10 — Why Groq Produced Nothing *(1:45)*

And with the fallback removed, Groq told us exactly what was wrong.

Groq's free tier allows **seven thousand input tokens per minute**. Look at what
our papers actually need: the smallest, a six-page paper, needs seven thousand
nine hundred and twenty. BERT needs eighteen and a half thousand. RAG needs
twenty thousand three hundred.

Every paper is over the limit. Between one point one and two point nine times
over.

The critical detail — and this is the bit that is easy to get wrong — is that
**this is not a pacing problem.** Normally a per-minute limit just means you
wait. But a *single* request of seven thousand nine hundred and twenty tokens
can never fit
inside a seven-thousand-per-minute budget, however long you wait. There is no
retry schedule that fixes it.

So the honest conclusion is: **at this account tier, Groq cannot read a research
paper.** Not a long one — *any* of them.

That is why the comparison we set out to make does not exist in our report. We
report it as a negative result, because the alternative was to quote pass B's
numbers as Groq's performance — and those numbers are Claude's.

---

## Slide 11 — The Finding *(1:45)*

Which brings me to what I think is the real contribution of this project.

**A redundancy mechanism hides the failure it compensates for.**

Think about what was true simultaneously. One of our two providers was
completely non-functional — not degraded, not slow, producing *nothing*. And
every analysis succeeded. The interface showed no error. A user would have
noticed absolutely nothing wrong. Our fallback worked *perfectly*, and in
working perfectly, it made a dead component invisible.

We only caught it because of two things.

One: every analysis records which provider **actually** produced it — not which
one was configured.

Two: when we aggregated the results, we grouped by that record.

And here is the part I would ask you to sit with. Grouping by **configured**
provider is the obvious choice. It is what the experiment was designed around.
If we had done the obvious thing, our report would have concluded, with a
straight face and a clean table, that **both providers perform identically** —
while actually measuring Claude twice.

So the lesson generalises beyond this project: if a system has automatic
fallback, it **must** record which path was actually taken, and any evaluation
of it must group by that record rather than by configuration. Otherwise
redundancy does not just mask failures from users — it masks them from the
people measuring the system.

---

## Slide 12 — Verification *(1:15)*

Two things we did verify properly.

Isolation: a live test with two real accounts against the production database.
**Twenty-six checks, zero failures.** A new user's library is empty. User B
cannot read, delete, or review User A's paper — and gets a 404, not a 403,
because a 403 would confirm the paper exists.

The check I am proudest of is the last one: we queried the database
**directly**, bypassing our API completely, using the same key that ships inside
the browser. It returns **zero rows**. That means isolation does not depend on
our code being correct — which matters, given that our code was previously
wrong.

And the cache: a first upload takes thirty-two seconds, a repeat takes three,
and a repeat **by a different user** takes under three. No model call either
time. The signal that proves it is that the reported processing time stays the
*original* run's figure — a merely fast response could not fake that.

---

## Slide 13 — Limitations *(1:00)*

I want to be direct about what we have not shown.

The biggest one: **we have no ground truth.** Every number in our evaluation
measures how much the system produced, not whether it was correct. A model that
invented nine plausible-sounding research gaps would score exactly the same as
one that found nine real ones. No domain expert graded our output.

Second: we are effectively **single-provider**. The architecture supports two;
in practice one of them cannot do the work.

Third — and this one bothers us — the **insufficient-evidence path was never
triggered.** Zero out of ten runs. That is the safeguard objective two rests on,
and our corpus did not test it, because well-structured papers always have
findings and limitations to report.

Five papers, one discipline, single runs, and evaluated by the people who built
it. Two of our six objectives are only partially achieved — and in both cases
that is because the evaluation *revealed* something, not because we ran out of
time.

---

## Slide 14 — Conclusion *(1:00)*

To close.

We delivered a deployed system that meets all five university requirements,
with grounding enforced structurally, isolation enforced by PostgreSQL rather
than by our own care, and provenance recorded for every analysis.

The most valuable next step by a wide margin is **ground-truth evaluation** —
expert-annotated papers — because that is the only thing that turns "the system
produced nine gaps" into "the system found the gaps that mattered". After that,
a second provider that can actually accept a full paper, and a deliberate test
of the insufficient-evidence path.

And the lesson we are taking from this: the most valuable results we got came
from checking what the system **actually did**, rather than trusting what the
code implied it would do. Policies that were correct but inert. A fallback so
effective it hid a dead provider. A cached result that would have been recorded
as a success for a provider that never ran.

Thank you — I am happy to take questions.

---

# Anticipated Questions

Answer briefly and concede real limits — the strongest position here is
accuracy, not defensiveness.

**"Isn't this just a wrapper around Claude?"**
The generation is inference against a hosted model, yes, and we say so plainly.
The engineering that makes it a system rather than a wrapper is the parts that
constrain it: schema-constrained generation with discard-on-mismatch, database-
enforced isolation, content-addressed caching, and per-analysis provenance. That
last one is what let us discover a dead provider that every other signal said
was fine.

**"Why is there no RAG? The scaffolding is in your repo."**
Because measurement said it was unnecessary. All five papers fitted in a single
context window with no truncation and no chunking. Adding retrieval would have
added failure modes — a bad retrieval silently drops the relevant section — to
solve a problem we did not have. The scaffolding is unused, and the report names
it as unused so it cannot be mistaken for a feature.

**"Why not just retry Groq, or send it smaller chunks?"**
Retrying does not help, because it is a single request that exceeds the budget,
not a rate we are exceeding. Chunking the paper to fit under seven thousand
tokens would work mechanically, but it would mean the two providers were doing
**different tasks** — Claude reading the whole paper, Groq reading fragments —
so the comparison would be meaningless. We chose to report the honest negative.

**"How do you know the summaries are any good?"**
We do not, and that is the single largest limitation of our evaluation. We
measured quantity, latency, and structural validity. Quality needs
expert-annotated ground truth, and it is our number one recommendation for
future work.

**"Isn't a five-second window after logout a security hole?"**
It is a real cost and we document it rather than hide it. We cache token
verifications for five seconds to avoid a round-trip to the auth service on
every request; we measured the actual window at about six seconds. If it is
judged unacceptable, the fix is a short-lived revocation list, which removes the
window without the per-request round-trip. Note the previous value was thirty
seconds — we reduced it after a live test showed logout appeared not to work.

**"Your isolation test failed on one check. Explain."**
It did, and the assertion was wrong rather than the system. It re-checked two
seconds after sign-out, when our verification cache is five seconds — so it was
asserting a guarantee we never made. We then measured the window directly, found
it bounded at about six seconds, and rewrote the test to assert the real
contract. We kept that in the report because correcting a test to match reality
is only legitimate if you show the measurement that justified it.

**"Why did two runs fail with 502 and then work later?"**
Transient provider unavailability. We re-ran both under the identical
configuration and both completed, in eighty and ninety-seven seconds. We report
that pass as five out of five and say explicitly that the earlier failures were
transient — rather than quietly dropping them.

**"What would you do differently?"**
Build the provenance recording first. Everything we learned from the evaluation
came from that one field, and if we had added it later we would have shipped a
report saying both providers worked.

**"Is this cheating — does it write students' literature reviews for them?"**
It can be misused, and no design prevents that. What the design does is tie
every claim to the source document and refuse to invent when evidence is
missing, which makes the output checkable against the paper. Our position is
that it is an assistant for reading, not a replacement for it.

---

## Demo Notes (if asked to show the live system)

Have these ready **before** you present:

1. Signed in, on `/dashboard`, with a paper already analysed — a live analysis
   takes about **100 seconds**, which is too long to do on stage.
2. A **second** paper ready to upload if they want to see it run. If you do it
   live, narrate the pipeline while it works.
3. Uploading a paper that is already cached returns in about **3 seconds** —
   that is the demo worth doing live, and it makes the caching point instantly.
4. `/papers/[id]` open in a tab to show a full analysis with gaps.
5. `/settings` to show the owner-only provider controls, if asked about
   objective three.

**Do not** switch providers live. The presentation configuration should stay as
it is, and a live Groq attempt will fail — which is a fine thing to *describe*
but a bad thing to stake a demo on.

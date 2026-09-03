import type { Metadata } from "next";
import Link from "next/link";

import {
  IconCheck,
  IconGap,
  IconReview,
  IconSpark,
  IconStack,
  IconUpload,
} from "@/components/Icons";
import HeroVisual from "@/components/HeroVisual";

/**
 * The public landing page.
 *
 * WHAT IT IS ALLOWED TO SAY
 * -------------------------
 * Only what the product does. ResearchForge extracts text from a PDF and makes
 * three grounded reasoning passes over it: a summary, a research-gap analysis,
 * and a literature review of the prior work the paper itself discusses. It
 * does NOT search external academic databases, and this page must never imply
 * that it does - a prospective reader who arrives expecting a search engine
 * has been misled, and in a graded university project an overstated capability
 * is worse than a modest one.
 *
 * Two claims are therefore deliberately absent, though both appear in the
 * design this page was modelled on:
 *
 *   "Your data is encrypted"   Not asserted. Supabase encrypts in transit and
 *                              at rest, but ResearchForge has not implemented
 *                              or verified any encryption of its own, and a
 *                              security claim it cannot substantiate is worse
 *                              than none. The privacy section says what IS
 *                              true: rows are readable only by their owner,
 *                              enforced by the database.
 *   "10x faster"               A measurement nobody has taken. The hero says
 *                              what the tool does instead.
 *
 * This is a server component - no "use client" - so the marketing page ships
 * as static HTML with no JavaScript needed to read it. That is also why it
 * carries its own metadata, which a client component could not export.
 */

export const metadata: Metadata = {
  title: "ResearchForge: Understand research faster with AI",
  description:
    "Upload an academic paper and get a grounded summary, the research gaps it " +
    "supports, and a literature review of the prior work it discusses. Compare " +
    "several saved papers in one cross-paper review.",
};

const FEATURES = [
  {
    icon: <IconUpload size={22} />,
    title: "Upload Research Papers",
    body:
      "Drop in a PDF and the text is extracted server side. A scanned paper " +
      "with no text layer is refused rather than guessed at.",
  },
  {
    icon: <IconSpark size={22} />,
    title: "AI Analysis",
    body:
      "Three separate reasoning passes over the paper's own text, each " +
      "constrained to a schema and validated before you see it.",
  },
  {
    icon: <IconGap size={22} />,
    title: "Discover Research Gaps",
    body:
      "Gaps the paper itself supports, each shown beside the evidence in the " +
      "text that points to it.",
  },
  {
    icon: <IconReview size={22} />,
    title: "Literature Reviews",
    body:
      "A review of the prior work discussed inside one paper, or a cross-paper " +
      "review across several papers you have saved.",
  },
];

const STEPS = [
  {
    n: "01",
    title: "Upload",
    body: "Upload an academic paper as a PDF.",
  },
  {
    n: "02",
    title: "Analyse",
    body: "ResearchForge reads the paper and analyses what it actually says.",
  },
  {
    n: "03",
    title: "Discover",
    body: "Review the summary, the key findings, and the research gaps.",
  },
  {
    n: "04",
    title: "Review",
    body: "Generate literature-review insights and compare saved papers.",
  },
];

/** Only claims that are true of what is built. See the module note above. */
const PRIVACY_POINTS = [
  "Every paper, analysis and review belongs to the account that created it.",
  "The database refuses to return one account's rows to another, so a guessed link reaches nothing.",
  "Your papers are never used to answer anybody else's question.",
];

export default function LandingPage() {
  return (
    <>
      {/* ---------------------------------------------------------------- */}
      {/* Hero                                                              */}
      {/* ---------------------------------------------------------------- */}
      <section className="lp-hero">
        <div className="lp-hero__grid">
          <div className="lp-hero__text">
            <p className="lp-eyebrow">
              <IconSpark size={15} />
              AI-Powered Research Assistant
            </p>
            <h1 className="lp-hero__title">
              Understand research{" "}
              <span className="lp-hero__accent">faster with AI</span>
            </h1>
            <p className="lp-hero__sub">
              Upload an academic paper and get a grounded summary, the research
              gaps it supports, and a review of the literature it discusses.
              Save papers to your own library and compare several at once.
            </p>

            <div className="lp-hero__actions">
              <Link href="/sign-up" className="btn btn--primary btn--lg">
                Get Started
              </Link>
              <a href="#how-it-works" className="btn btn--lg">
                See How It Works
              </a>
            </div>

            <ul className="lp-trust">
              <li>
                <IconCheck size={16} />
                <div>
                  <strong>Private to your account</strong>
                  <span>Only you can read your library.</span>
                </div>
              </li>
              <li>
                <IconCheck size={16} />
                <div>
                  <strong>Grounded in your paper</strong>
                  <span>No claim without the text behind it.</span>
                </div>
              </li>
              <li>
                <IconCheck size={16} />
                <div>
                  <strong>Says when it cannot tell</strong>
                  <span>Insufficient evidence, not invention.</span>
                </div>
              </li>
            </ul>
          </div>

          <HeroVisual />
        </div>
      </section>

      {/* ---------------------------------------------------------------- */}
      {/* Features                                                          */}
      {/* ---------------------------------------------------------------- */}
      <section className="lp-section" id="features">
        <div className="lp-sectionhead">
          <p className="pagehead__eyebrow">Features</p>
          <h2 className="lp-sectiontitle">What ResearchForge does</h2>
          <p className="lp-sectionsub">
            Four capabilities, each working on the paper you uploaded. There is
            no external database search: everything you read is drawn from your
            own documents.
          </p>
        </div>

        <div className="lp-features">
          {FEATURES.map(({ icon, title, body }) => (
            <article key={title} className="card lp-feature">
              <span className="lp-feature__icon" aria-hidden="true">
                {icon}
              </span>
              <h3 className="lp-feature__title">{title}</h3>
              <p className="lp-feature__body">{body}</p>
            </article>
          ))}
        </div>
      </section>

      {/* ---------------------------------------------------------------- */}
      {/* How it works                                                      */}
      {/* ---------------------------------------------------------------- */}
      <section className="lp-section" id="how-it-works">
        <div className="lp-sectionhead">
          <p className="pagehead__eyebrow">How It Works</p>
          <h2 className="lp-sectiontitle">From PDF to literature review</h2>
          <p className="lp-sectionsub">
            The same four steps every time, in the same words the application
            uses once you are inside it.
          </p>
        </div>

        <ol className="lp-steps">
          {STEPS.map(({ n, title, body }) => (
            <li key={n} className="lp-step">
              <span className="lp-step__n" aria-hidden="true">
                {n}
              </span>
              <h3 className="lp-step__title">{title}</h3>
              <p className="lp-step__body">{body}</p>
            </li>
          ))}
        </ol>
      </section>

      {/* ---------------------------------------------------------------- */}
      {/* Privacy                                                           */}
      {/* ---------------------------------------------------------------- */}
      <section className="lp-section" id="privacy">
        <div className="card lp-privacy">
          <div className="lp-privacy__text">
            <p className="pagehead__eyebrow">Your research library</p>
            <h2 className="lp-sectiontitle">
              Your research stays private to your account.
            </h2>
            <p className="lp-sectionsub">
              Signing in gives you a library nobody else can open. Ownership is
              enforced by the database itself, not only by the interface, so a
              paper belonging to another account is not merely hidden from you
              &mdash; it is unreadable.
            </p>
            <ul className="lp-privacy__list">
              {PRIVACY_POINTS.map((point) => (
                <li key={point}>
                  <IconCheck size={16} />
                  <span>{point}</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="lp-privacy__aside" aria-hidden="true">
            <span className="lp-privacy__seal">
              <IconStack size={30} />
            </span>
            <p className="lp-privacy__sealnote">
              One library per account.
              <br />
              Enforced in the database.
            </p>
          </div>
        </div>
      </section>

      {/* ---------------------------------------------------------------- */}
      {/* About                                                             */}
      {/* ---------------------------------------------------------------- */}
      <section className="lp-section" id="about">
        <div className="lp-sectionhead">
          <p className="pagehead__eyebrow">About</p>
          <h2 className="lp-sectiontitle">Built to be checkable</h2>
        </div>

        <div className="lp-about">
          <article className="card lp-about__card">
            <h3 className="lp-feature__title">Grounded, or silent</h3>
            <p className="lp-feature__body">
              Every section is produced from the uploaded paper&apos;s own text.
              Where the paper does not support a section, ResearchForge reports
              insufficient evidence instead of filling the space.
            </p>
          </article>
          <article className="card lp-about__card">
            <h3 className="lp-feature__title">Traceable output</h3>
            <p className="lp-feature__body">
              Each research gap is shown beside the evidence that points to it,
              and every saved analysis records the model that produced it, so a
              result can always be traced back to its source.
            </p>
          </article>
          <article className="card lp-about__card">
            <h3 className="lp-feature__title">Honest about limits</h3>
            <p className="lp-feature__body">
              A scanned PDF with no text layer is refused rather than guessed
              at, and a paper too long to read whole is marked as truncated
              rather than quietly shortened.
            </p>
          </article>
        </div>
      </section>

      {/* ---------------------------------------------------------------- */}
      {/* Closing call to action                                            */}
      {/* ---------------------------------------------------------------- */}
      <section className="lp-section">
        <div className="lp-cta">
          <h2 className="lp-cta__title">Start your research library</h2>
          <p className="lp-cta__sub">
            Create an account and upload your first paper. It takes a minute.
          </p>
          <div className="lp-hero__actions lp-cta__actions">
            <Link href="/sign-up" className="btn btn--primary btn--lg">
              Get Started
            </Link>
            <Link href="/sign-in" className="btn btn--lg">
              Sign In
            </Link>
          </div>
        </div>
      </section>
    </>
  );
}

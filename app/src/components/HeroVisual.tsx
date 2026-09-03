/**
 * The hero illustration: what ResearchForge produces, drawn rather than
 * screenshotted.
 *
 * WHY IT SHOWS NO NUMBERS AND NO SENTENCES
 * ----------------------------------------
 * A marketing mockup normally invents its content - "12 Papers Uploaded",
 * "This paper presents a federated approach to…". Both would be fabricated:
 * numbers nobody measured, and an analysis of a paper nobody uploaded. This is
 * a graded academic project whose whole selling point is that its output is
 * grounded and checkable, so inventing a screenshot of the product would
 * contradict the thing being sold on the same screen.
 *
 * Instead this shows the SHAPE of a real result: the three sections an analysis
 * always produces, in the order the application produces them, with the text
 * drawn as neutral rules. It is honest, it reads instantly, and there is
 * nothing in it that could turn out to be untrue.
 *
 * Built from divs and the project's own colour tokens rather than an exported
 * image, so it stays crisp at every size, follows the light/dark theme with no
 * second asset, and costs no download.
 *
 * A server component: it holds no state and needs no JavaScript to render.
 */

import { IconFile, IconGap, IconReview, IconSpark } from "@/components/Icons";

/** One block of "text", drawn as rules of varying length. */
function Lines({ widths }: { widths: number[] }) {
  return (
    <div className="hv-lines" aria-hidden="true">
      {widths.map((width, i) => (
        <span key={i} className="hv-line" style={{ width: `${width}%` }} />
      ))}
    </div>
  );
}

export default function HeroVisual() {
  return (
    <div className="hv" aria-hidden="true">
      {/* The document going in. */}
      <div className="hv-source">
        <span className="hv-source__icon">
          <IconFile size={18} />
        </span>
        <div className="hv-source__meta">
          <span className="hv-source__label">PDF</span>
          <span className="hv-source__note">your paper</span>
        </div>
      </div>

      {/* The analysis coming out. */}
      <div className="hv-panel">
        <div className="hv-panel__bar">
          <span className="hv-dot" />
          <span className="hv-dot" />
          <span className="hv-dot" />
          <span className="hv-panel__title">Analysis</span>
        </div>

        <div className="hv-panel__body">
          <section className="hv-block">
            <header className="hv-block__head">
              <span className="hv-block__icon hv-block__icon--summary">
                <IconSpark size={14} />
              </span>
              <span className="hv-block__label">Summary</span>
            </header>
            <Lines widths={[100, 88, 94, 62]} />
          </section>

          <section className="hv-block">
            <header className="hv-block__head">
              <span className="hv-block__icon hv-block__icon--gaps">
                <IconGap size={14} />
              </span>
              <span className="hv-block__label">Research gaps</span>
            </header>
            {/* Two gap cards, each with the evidence line the real interface
                shows beneath every gap. */}
            <div className="hv-gap">
              <Lines widths={[92, 70]} />
              <span className="hv-evidence" />
            </div>
            <div className="hv-gap">
              <Lines widths={[84, 58]} />
              <span className="hv-evidence" />
            </div>
          </section>

          <section className="hv-block">
            <header className="hv-block__head">
              <span className="hv-block__icon hv-block__icon--review">
                <IconReview size={14} />
              </span>
              <span className="hv-block__label">Literature review</span>
            </header>
            <Lines widths={[96, 82, 90]} />
          </section>
        </div>
      </div>
    </div>
  );
}

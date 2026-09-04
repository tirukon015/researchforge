/**
 * The decorative background layer. Purely visual, and behind everything.
 *
 * WHAT IT IS FOR
 * --------------
 * ResearchForge is a research tool, and the page should feel like one before a
 * word is read: books, documents, a search, a few citation links. The brief is
 * an academic workspace, not an AI wallpaper - so there are no glowing orbs, no
 * neural nets, no circuitry, and nothing animated.
 *
 * HOW IT STAYS OUT OF THE WAY
 * ---------------------------
 *   position: fixed          it never participates in layout, so it cannot
 *                            change a single dimension or create a scrollbar
 *   inset: 0 + overflow      artwork is clipped at the viewport edge rather
 *                            than extending the page
 *   pointer-events: none     nothing here is clickable, hoverable or
 *                            focusable; it cannot intercept a click meant for
 *                            the interface
 *   z-index: 0, content 1    strictly behind every card, control and letter
 *   aria-hidden              invisible to a screen reader, because it says
 *                            nothing a reader needs
 *
 * The centre band is deliberately EMPTY. Every element sits in the outer
 * thirds, because the dashboard's cards and text live in the middle and
 * readability there beats decoration everywhere.
 *
 * WHY SVG AND CSS RATHER THAN AN IMAGE
 * ------------------------------------
 * It stays crisp at any size, weighs a couple of kilobytes, needs no second
 * asset for dark mode, and follows the theme's own colour tokens - so it can
 * never drift away from the palette the rest of the interface uses. Opacity is
 * lowered further in dark mode, where the same values read far louder.
 */

export default function ResearchBackdrop() {
  return (
    <div className="rbg" aria-hidden="true">
      {/* Soft corner wash. Two very wide, very faint radials - the only
          "atmosphere" in the whole layer, and both are far off-centre. */}
      <div className="rbg__wash" />

      {/* ---------------- LEFT: the reading side ---------------- */}
      <svg
        className="rbg__art rbg__art--left"
        viewBox="0 0 320 900"
        fill="none"
        preserveAspectRatio="xMinYMax meet"
        focusable="false"
      >
        {/* A stack of books, lower left. Flat editorial blocks with a spine
            rule and a title - no gloss, no perspective tricks. Bottom-most
            and widest first. */}
        <g className="rbg-book">
          <rect x="28" y="742" width="214" height="34" rx="3" />
          <line x1="44" y1="742" x2="44" y2="776" />
          <text x="62" y="764">Research Methods</text>
        </g>
        <g className="rbg-book">
          <rect x="38" y="704" width="188" height="32" rx="3" />
          <line x1="54" y1="704" x2="54" y2="736" />
          <text x="72" y="725">Literature Review</text>
        </g>
        <g className="rbg-book">
          <rect x="32" y="668" width="204" height="30" rx="3" />
          <line x1="48" y1="668" x2="48" y2="698" />
          <text x="66" y="688">Artificial Intelligence</text>
        </g>
        <g className="rbg-book">
          <rect x="46" y="634" width="170" height="28" rx="3" />
          <line x1="62" y1="634" x2="62" y2="662" />
          <text x="80" y="653">Scientific Writing</text>
        </g>
        {/* one leaning against the stack */}
        <g className="rbg-book rbg-book--tilt">
          <rect x="196" y="646" width="26" height="130" rx="3" />
          <line x1="196" y1="662" x2="222" y2="662" />
          <line x1="196" y1="760" x2="222" y2="760" />
        </g>

        {/* An open page above the stack: two columns of text rules. */}
        <g className="rbg-page">
          <rect x="56" y="470" width="176" height="130" rx="4" />
          <line x1="72" y1="496" x2="134" y2="496" />
          <line x1="72" y1="510" x2="140" y2="510" />
          <line x1="72" y1="524" x2="128" y2="524" />
          <line x1="72" y1="538" x2="138" y2="538" />
          <line x1="154" y1="496" x2="216" y2="496" />
          <line x1="154" y1="510" x2="210" y2="510" />
          <line x1="154" y1="524" x2="218" y2="524" />
          <line x1="154" y1="538" x2="204" y2="538" />
          {/* a marked passage - the "evidence" motif */}
          <rect className="rbg-mark" x="70" y="556" width="74" height="9" rx="2" />
          <line x1="154" y1="560" x2="212" y2="560" />
        </g>

        {/* A small citation graph: papers linked to one another. Thin lines,
            small nodes - a reference network, not a neural one. */}
        <g className="rbg-link">
          <line x1="96" y1="300" x2="176" y2="252" />
          <line x1="176" y1="252" x2="238" y2="316" />
          <line x1="96" y1="300" x2="150" y2="372" />
          <line x1="150" y1="372" x2="238" y2="316" />
        </g>
        {/* The nodes are tiny PAGES, not dots: a citation graph links
            papers, and a rectangle says that where a circle does not. */}
        <g className="rbg-node">
          <rect x="91" y="294" width="10" height="12" rx="1" />
          <rect x="171" y="246" width="10" height="12" rx="1" />
          <rect x="233" y="310" width="10" height="12" rx="1" />
          <rect x="145" y="366" width="10" height="12" rx="1" />
        </g>
      </svg>

      {/* ---------------- RIGHT: the searching side ---------------- */}
      <svg
        className="rbg__art rbg__art--right"
        viewBox="0 0 320 900"
        fill="none"
        preserveAspectRatio="xMaxYMin meet"
        focusable="false"
      >
        {/* A search field over a document, with a magnifier. The one place
            the layer names what the product does. */}
        <g className="rbg-panel">
          <rect x="60" y="118" width="216" height="34" rx="17" />
          <circle className="rbg-glass" cx="86" cy="135" r="7.5" />
          <line className="rbg-glass" x1="91.5" y1="140.5" x2="97" y2="146" />
          <line x1="106" y1="135" x2="196" y2="135" />
        </g>

        {/* Result rows: a title rule, a snippet rule, and a highlighted term. */}
        <g className="rbg-result">
          <line x1="66" y1="184" x2="188" y2="184" />
          <rect className="rbg-mark" x="196" y="178" width="52" height="9" rx="2" />
          <line x1="66" y1="200" x2="256" y2="200" />
        </g>
        <g className="rbg-result">
          <line x1="66" y1="232" x2="164" y2="232" />
          <rect className="rbg-mark" x="172" y="226" width="44" height="9" rx="2" />
          <line x1="66" y1="248" x2="248" y2="248" />
        </g>

        {/* Faint section labels, in the product's own vocabulary. */}
        <text className="rbg-label" x="66" y="300">Relevant Literature</text>
        <text className="rbg-label" x="66" y="326">Research Gaps</text>
        <text className="rbg-label" x="66" y="352">Recent Findings</text>

        {/* A small analysis chart: axes, a trend, a few plotted points. */}
        <g className="rbg-chart">
          <line x1="70" y1="470" x2="70" y2="576" />
          <line x1="70" y1="576" x2="262" y2="576" />
          <polyline points="70,552 112,530 154,540 196,494 238,478" />
          {/* Plotted points as small ticks rather than dots. */}
          <line x1="112" y1="526" x2="112" y2="534" />
          <line x1="154" y1="536" x2="154" y2="544" />
          <line x1="196" y1="490" x2="196" y2="498" />
          <line x1="238" y1="474" x2="238" y2="482" />
        </g>

        {/* An annotated document, lower right, with a margin note. */}
        <g className="rbg-page">
          <rect x="96" y="656" width="150" height="182" rx="4" />
          <line x1="112" y1="686" x2="216" y2="686" />
          <line x1="112" y1="702" x2="230" y2="702" />
          <line x1="112" y1="718" x2="206" y2="718" />
          <line x1="112" y1="742" x2="228" y2="742" />
          <line x1="112" y1="758" x2="198" y2="758" />
          <rect className="rbg-mark" x="112" y="776" width="66" height="9" rx="2" />
          <line x1="112" y1="800" x2="222" y2="800" />
        </g>
        {/* A margin note tethered to the annotated passage. */}
        <g className="rbg-link">
          <line x1="246" y1="780" x2="282" y2="750" />
        </g>
        <g className="rbg-node">
          <rect x="280" y="742" width="9" height="11" rx="1" />
        </g>
      </svg>
    </div>
  );
}

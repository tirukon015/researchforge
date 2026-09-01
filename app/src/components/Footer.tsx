/**
 * A quiet footer carrying the brand line and the honest scope statement.
 *
 * Kept small on purpose. It repeats the tagline from the official logo rather
 * than inventing new marketing copy, and it states the grounding rule, which
 * is the one thing a reader of an AI-produced analysis most needs to know.
 */

import Link from "next/link";

export default function Footer() {
  return (
    <footer className="sitefooter">
      <div className="sitefooter__inner">
        <div>
          <p className="sitefooter__name">ResearchForge</p>
          <p className="sitefooter__tagline">Explore, Analyze, Innovate</p>
        </div>
        <p className="sitefooter__note">
          Analysis is grounded in the uploaded paper only. Where a paper does
          not support a section, ResearchForge says so rather than inventing
          content.
        </p>
        <nav className="sitefooter__links" aria-label="Footer">
          <Link href="/papers">My Papers</Link>
          <Link href="/literature-review">Literature Review</Link>
          <Link href="/settings">Settings</Link>
        </nav>
      </div>
    </footer>
  );
}

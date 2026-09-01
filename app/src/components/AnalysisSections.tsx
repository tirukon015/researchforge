/**
 * The renderers for one analysis, shared by the dashboard workspace and the
 * Literature Review page so the same result never renders two different ways.
 *
 * The governing rule is the project's: nothing is invented. Where the backend
 * reports insufficient evidence, that is stated plainly rather than rendering
 * an empty section that reads either as a bug or, worse, as an answer. A block
 * with nothing behind it renders nothing at all.
 */

import CopyButton from "@/components/CopyButton";
import { IconAlert, IconInfo } from "@/components/Icons";
import type {
  AnalysisResponse,
  LiteratureReview,
  ResearchGaps,
  Summary,
} from "@/lib/api";

/* ------------------------------------------------------------------ *
 * Primitives
 * ------------------------------------------------------------------ */

export function Field({
  title,
  value,
  copyable = false,
}: {
  title: string;
  value: string;
  copyable?: boolean;
}) {
  if (!value) return null;
  return (
    <div className="block">
      <div className="block__head">
        <h4>{title}</h4>
        {copyable && <CopyButton text={value} />}
      </div>
      <p>{value}</p>
    </div>
  );
}

export function ListBlock({ title, items }: { title: string; items: string[] }) {
  if (!items || items.length === 0) return null;
  return (
    <div className="block">
      <div className="block__head">
        <h4>
          {title} <span className="faint">({items.length})</span>
        </h4>
        <CopyButton text={items.map((i) => `• ${i}`).join("\n")} />
      </div>
      <ul>
        {items.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

/** Key findings earn discrete cards: they are the most-scanned part. */
export function FindingsBlock({ items }: { items: string[] }) {
  if (!items || items.length === 0) return null;
  return (
    <div className="block">
      <div className="block__head">
        <h4>
          Key findings <span className="faint">({items.length})</span>
        </h4>
        <CopyButton text={items.map((f, i) => `${i + 1}. ${f}`).join("\n")} />
      </div>
      <ol className="findings">
        {items.map((item, i) => (
          <li key={i}>
            <span className="findings__n">{i + 1}</span>
            <span>{item}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

export function EvidenceNotice({ children }: { children: React.ReactNode }) {
  return (
    <div className="notice notice--warn">
      <IconAlert size={16} />
      <div>
        <p>
          <strong>Insufficient evidence.</strong> {children}
        </p>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * Sections
 * ------------------------------------------------------------------ */

export function SummarySection({ summary }: { summary: Summary }) {
  const full = [
    summary.research_problem && `RESEARCH PROBLEM\n${summary.research_problem}`,
    summary.methodology && `METHODOLOGY\n${summary.methodology}`,
    summary.key_findings.length > 0 &&
      `KEY FINDINGS\n${summary.key_findings.map((f, i) => `${i + 1}. ${f}`).join("\n")}`,
    summary.conclusion && `CONCLUSION\n${summary.conclusion}`,
  ]
    .filter(Boolean)
    .join("\n\n");

  return (
    <>
      <div className="btnrow" style={{ justifyContent: "flex-end", marginBottom: ".6rem" }}>
        <CopyButton text={full} label="Copy summary" />
      </div>
      <Field title="Overview — research problem and background" value={summary.research_problem} />
      <FindingsBlock items={summary.key_findings} />
      <Field title="Methodology" value={summary.methodology} />
      <Field title="Conclusion" value={summary.conclusion} />
      {summary.insufficient_evidence.length > 0 && (
        <EvidenceNotice>
          The paper did not contain enough information for:{" "}
          {summary.insufficient_evidence.join(", ")}.
        </EvidenceNotice>
      )}
    </>
  );
}

export function GapsSection({ gaps }: { gaps: ResearchGaps }) {
  if (gaps.insufficient_evidence) {
    return (
      <EvidenceNotice>
        {gaps.evidence_note ||
          "This paper does not contain enough material to support a gap analysis."}
      </EvidenceNotice>
    );
  }

  return (
    <>
      <ListBlock title="Limitations stated by the authors" items={gaps.stated_limitations} />

      {gaps.identified_gaps.length > 0 ? (
        <div className="block">
          <div className="block__head">
            <h4>
              Identified research gaps{" "}
              <span className="faint">({gaps.identified_gaps.length})</span>
            </h4>
            <CopyButton
              text={gaps.identified_gaps
                .map(
                  (g, i) =>
                    `GAP ${i + 1}: ${g.gap}\nWhy it matters: ${g.why_it_matters}\nEvidence: ${g.evidence}`,
                )
                .join("\n\n")}
            />
          </div>

          {gaps.identified_gaps.map((g, i) => (
            <article className="gap" key={i}>
              <div className="gap__head">
                <span className="gap__n">GAP {i + 1}</span>
                <h5 className="gap__title">{g.gap}</h5>
              </div>
              <p className="gap__why">
                <span className="gap__label">Why it matters</span>
                {g.why_it_matters}
              </p>
              {/* Evidence is what separates an identified gap from an invented
                  one, so it is always shown, never collapsed away. */}
              <blockquote className="gap__evidence">
                <span className="gap__label">Evidence from the paper</span>
                {g.evidence}
              </blockquote>
            </article>
          ))}
        </div>
      ) : (
        <p className="muted">
          The analysis reported no research gaps for this paper.
        </p>
      )}
    </>
  );
}

export function ReviewSection({ review }: { review: LiteratureReview }) {
  return (
    <>
      {review.scope_note && (
        <div className="notice notice--info" style={{ marginBottom: "1.3rem" }}>
          <IconInfo size={16} />
          <div>
            <p>
              <strong>Scope.</strong> {review.scope_note}
            </p>
          </div>
        </div>
      )}

      {review.insufficient_evidence ? (
        <EvidenceNotice>
          This paper discusses too little prior work to review.
        </EvidenceNotice>
      ) : (
        <>
          <ListBlock title="Major themes" items={review.major_themes} />
          <ListBlock title="Relevant findings" items={review.relevant_findings} />
          <ListBlock title="Comparisons between studies" items={review.comparisons} />
          <ListBlock title="Research trends" items={review.research_trends} />
          <ListBlock title="Limitations of prior work" items={review.limitations} />
          <ListBlock title="Possible research directions" items={review.future_directions} />
        </>
      )}
    </>
  );
}

export function PaperInfoSection({ data }: { data: AnalysisResponse }) {
  const doc = data.document;
  return (
    <>
      <div className="block">
        <div className="block__head">
          <h4>Document</h4>
        </div>
        <dl className="dl">
          <div>
            <dt>Filename</dt>
            <dd>{doc.filename}</dd>
          </div>
          <div>
            <dt>Pages</dt>
            <dd>{doc.page_count.toLocaleString()}</dd>
          </div>
          <div>
            <dt>Characters extracted</dt>
            <dd>{doc.extracted_characters.toLocaleString()}</dd>
          </div>
          <div>
            <dt>Analysed as</dt>
            <dd>
              {doc.chunk_count === 1
                ? "A single document"
                : `${doc.chunk_count} sections`}
            </dd>
          </div>
          <div>
            <dt>Model</dt>
            <dd>{data.model_used}</dd>
          </div>
          <div>
            <dt>Content truncated</dt>
            <dd>{doc.truncated ? "Yes" : "No"}</dd>
          </div>
        </dl>
      </div>

      {doc.truncated && (
        <div className="notice notice--warn" style={{ marginBottom: "1.5rem" }}>
          <IconAlert size={16} />
          <div>
            <p>
              <strong>Some content was dropped.</strong> This paper was longer
              than the analysis window, so parts of it were not read. Treat the
              result as covering the extracted portion only.
            </p>
          </div>
        </div>
      )}

      {/* Keywords are listed in the product brief but are NOT part of the
          backend's response schema (src/schemas/analysis.py). Rendering a
          guessed set here would be fabrication, so the section states its own
          absence and names what would fill it. */}
      <div className="block">
        <div className="block__head">
          <h4>Keywords</h4>
        </div>
        <p className="muted">
          Keyword extraction is not part of the current analysis. The backend
          returns a summary, research gaps, and a literature review; adding
          keywords means adding a field to the analysis schema, so none are
          shown rather than guessed from the text.
        </p>
      </div>
    </>
  );
}

"use client";

/**
 * Settings / About.
 *
 * Read-only by design: everything that configures ResearchForge is a
 * server-side environment variable, and the browser must never be able to see
 * or change it. Nothing here renders a key, a token, or a variable's value -
 * only the provider's NAME, which is public information.
 *
 * The version and environment shown come from the live /health response, so
 * this page reports the deployment that is actually answering rather than a
 * constant compiled into the bundle.
 */

import Image from "next/image";

import BackendStatus from "@/components/BackendStatus";
import { IconInfo } from "@/components/Icons";
import { API_BASE_LABEL } from "@/lib/api";
import { useSession } from "@/lib/session";

export default function SettingsPage() {
  const { health } = useSession();

  const version = health.kind === "ok" ? health.data.version : "—";
  const environment = health.kind === "ok" ? health.data.environment : "—";
  const appName = health.kind === "ok" ? health.data.app_name : "ResearchForge";

  return (
    <>
      <header className="pagehead">
        <div>
          <h1 className="pagehead__title">Settings</h1>
          <p className="pagehead__sub">
            Application and service information. ResearchForge is configured
            entirely server-side; there is nothing to change from the browser.
          </p>
        </div>
        <BackendStatus />
      </header>

      <section className="section" aria-labelledby="about-heading">
        <div className="section__head">
          <h2 className="section__title" id="about-heading">
            About
          </h2>
        </div>
        <div className="card">
          <div className="card__body brandpanel">
            {/* The full lockup — mark, wordmark, and tagline — belongs on an
                identity surface like this one, not repeated through the app. */}
            <Image
              src="/brand/researchforge-full.png"
              alt="ResearchForge — Explore, Analyze, Innovate"
              width={380}
              height={380}
              className="brandpanel__logo"
              style={{ width: 190, height: "auto" }}
            />
            <div style={{ flex: 1, minWidth: "16rem" }}>
              <h3 style={{ margin: "0 0 .35rem", fontSize: "1.1rem" }}>
                ResearchForge
              </h3>
              <p className="muted" style={{ margin: "0 0 .75rem" }}>
                AI Research Assistant. Upload a research paper to generate a
                summary, identify research gaps, and produce a literature
                review — each grounded in the paper you provide.
              </p>
              <div className="tagrow">
                <span className="badge badge--accent">Explore</span>
                <span className="badge badge--accent">Analyze</span>
                <span className="badge badge--accent">Innovate</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="section" aria-labelledby="app-heading">
        <div className="section__head">
          <h2 className="section__title" id="app-heading">
            Application
          </h2>
        </div>
        <div className="card">
          <div className="card__body">
            <dl className="kv">
              <div>
                <dt>Application</dt>
                <dd>{appName}</dd>
              </div>
              <div>
                <dt>Description</dt>
                <dd>AI Research Assistant</dd>
              </div>
              <div>
                <dt>Backend version</dt>
                <dd>{version}</dd>
              </div>
              <div>
                <dt>Environment</dt>
                <dd>{environment}</dd>
              </div>
              <div>
                <dt>API location</dt>
                <dd>{API_BASE_LABEL}</dd>
              </div>
            </dl>
          </div>
        </div>
      </section>

      <section className="section" aria-labelledby="ai-heading">
        <div className="section__head">
          <h2 className="section__title" id="ai-heading">
            AI
          </h2>
        </div>
        <div className="card">
          <div className="card__body">
            <dl className="kv">
              <div>
                <dt>AI provider</dt>
                <dd>Gemini</dd>
              </div>
              <div>
                <dt>Analysis passes</dt>
                <dd>3 — summary, research gaps, literature review</dd>
              </div>
              <div>
                <dt>Grounding</dt>
                <dd>The uploaded paper only</dd>
              </div>
            </dl>

            {/* Deliberately no key, no masked key, and no variable values.
                A masked key still confirms which key is configured; the
                provider's name is the most the browser has any business
                knowing. */}
            <div className="notice notice--info" style={{ marginTop: "1.1rem" }}>
              <IconInfo size={16} />
              <div>
                <p>
                  <strong>Credentials are server-side only.</strong> API keys
                  are read by the FastAPI backend from its environment and are
                  never sent to the browser — not in full, and not masked.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="section" aria-labelledby="scope-heading">
        <div className="section__head">
          <h2 className="section__title" id="scope-heading">
            Current scope
          </h2>
        </div>
        <div className="card">
          <div className="card__body">
            <p className="muted" style={{ marginTop: 0 }}>
              <strong style={{ color: "var(--text)" }}>Built.</strong> PDF
              upload, text extraction, long-paper chunking, and three grounded
              analysis passes. Where a paper does not support a section,
              ResearchForge says so rather than inventing content.
            </p>
            <p className="muted" style={{ marginBottom: 0 }}>
              <strong style={{ color: "var(--text)" }}>Not built.</strong>{" "}
              Saved libraries, accounts, and cross-paper literature review.
              These need the database and retrieval milestones; analysis is
              stateless until then.
            </p>
          </div>
        </div>
      </section>
    </>
  );
}

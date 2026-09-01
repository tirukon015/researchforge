"use client";

/**
 * Settings and About.
 *
 * Appearance is the only thing that can be changed here, because everything
 * else that configures ResearchForge is a server-side environment variable and
 * the browser must not be able to see or alter it.
 *
 * Nothing on this page renders a key, a token, or a variable's value. Only the
 * provider's NAME, which is public information. A masked key is not a safe
 * compromise: it still confirms which key is configured.
 */

import Image from "next/image";

import BackendStatus from "@/components/BackendStatus";
import { IconInfo } from "@/components/Icons";
import ThemeToggle from "@/components/ThemeToggle";
import { API_BASE_LABEL } from "@/lib/api";
import { useSession } from "@/lib/session";
import { useTheme } from "@/lib/theme";

export default function SettingsPage() {
  const { health } = useSession();
  const { choice, resolved } = useTheme();

  const ok = health.kind === "ok";
  const version = ok ? health.data.version : "Not available";
  const environment = ok ? health.data.environment : "Not available";
  const appName = ok ? health.data.app_name : "ResearchForge";
  const libraryConnected = ok ? Boolean(health.data.library) : false;

  return (
    <>
      <header className="pagehead">
        <div>
          <h1 className="pagehead__title">Settings</h1>
          <p className="pagehead__sub">
            Appearance and application information. Everything else is
            configured on the server.
          </p>
        </div>
        <BackendStatus />
      </header>

      <section className="section" aria-labelledby="appearance-heading">
        <div className="section__head">
          <h2 className="section__title" id="appearance-heading">
            Appearance
          </h2>
        </div>
        <div className="card">
          <div className="card__body">
            <div className="settingrow">
              <div>
                <p className="settingrow__label">Colour theme</p>
                <p className="settingrow__hint">
                  Light is the default. System follows your operating system and
                  keeps following it if that changes.
                </p>
              </div>
              <div className="settingrow__control">
                <ThemeToggle full />
              </div>
            </div>
            <p className="card__hint" style={{ marginTop: ".9rem" }}>
              Currently showing the {resolved} theme
              {choice === "system" ? ", following your system setting." : "."}
            </p>
          </div>
        </div>
      </section>

      <section className="section" aria-labelledby="about-heading">
        <div className="section__head">
          <h2 className="section__title" id="about-heading">
            About
          </h2>
        </div>
        <div className="card">
          <div className="card__body brandpanel">
            {/* The full lockup belongs on an identity surface like this one,
                not repeated through the application. */}
            <Image
              src="/brand/researchforge-full.png"
              alt="ResearchForge. Explore, Analyze, Innovate"
              width={380}
              height={380}
              className="brandpanel__logo"
              style={{ width: 180, height: "auto" }}
            />
            <div style={{ flex: 1, minWidth: "16rem" }}>
              <h3 style={{ margin: "0 0 .35rem", fontSize: "1.1rem" }}>
                ResearchForge
              </h3>
              <p className="muted" style={{ margin: "0 0 .75rem" }}>
                AI Research Assistant. Upload academic papers, analyse them,
                identify research gaps, and build literature-review insights.
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
              <div>
                <dt>Research library</dt>
                <dd>{libraryConnected ? "Connected" : "Not connected"}</dd>
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
                <dd>3: summary, research gaps, literature review</dd>
              </div>
              <div>
                <dt>Grounding</dt>
                <dd>The uploaded paper only</dd>
              </div>
            </dl>

            <div className="notice notice--info" style={{ marginTop: "1.1rem" }}>
              <IconInfo size={16} />
              <div>
                <p>
                  <strong>Credentials are server-side only.</strong> API keys
                  are read by the backend from its environment and are never
                  sent to the browser, not in full and not masked.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>
    </>
  );
}

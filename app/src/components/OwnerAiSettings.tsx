"use client";

/**
 * Owner-only: which AI provider is primary for the whole application.
 *
 * WHO SEES THIS
 * -------------
 * Only the owner. `/api/owner/status` answers a plain boolean for every
 * signed-in user, and this component renders nothing at all when it is false -
 * no greyed-out controls, no "you do not have permission" panel. An ordinary
 * user has no business knowing the setting exists, and a disabled control is
 * an invitation to try.
 *
 * ⚠️ HIDING IS NOT THE BOUNDARY. Anyone can edit the bundle and call the API
 * directly; what stops them is `require_owner` in src/api/owner.py, and
 * underneath that the Row Level Security policies from migration 004 which
 * refuse a non-owner's write to `system_settings` outright. This component is
 * the courtesy, not the control.
 *
 * WHY THERE IS NO "AUTO"
 * ----------------------
 * The fallback is not a third choice - it is whichever provider was not
 * chosen. Offering "auto" would imply a mode where the application picks, and
 * the application does not: the owner picks, and the other one stands by.
 */

import { useCallback, useEffect, useState } from "react";

import { IconAlert, IconCheck, IconInfo } from "@/components/Icons";
import { ApiError, getAiConfig, getOwnerStatus, setAiConfig, type AiConfig } from "@/lib/api";

type State =
  | { kind: "checking" }
  /** Not the owner, or the deployment has no library. Render nothing. */
  | { kind: "hidden" }
  | { kind: "ready"; config: AiConfig }
  | { kind: "failed"; message: string };

export default function OwnerAiSettings() {
  const [state, setState] = useState<State>({ kind: "checking" });
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    void (async () => {
      try {
        const { is_owner } = await getOwnerStatus();
        if (cancelled) return;
        if (!is_owner) {
          setState({ kind: "hidden" });
          return;
        }
        const config = await getAiConfig();
        if (!cancelled) setState({ kind: "ready", config });
      } catch (caught) {
        if (cancelled) return;
        // A deployment with no database cannot answer this, and that is not an
        // error worth showing on a Settings page - the library panel above
        // already says the library is not connected.
        if (caught instanceof ApiError && caught.kind === "unavailable") {
          setState({ kind: "hidden" });
          return;
        }
        setState({
          kind: "failed",
          message:
            caught instanceof Error
              ? caught.message
              : "The AI configuration could not be loaded.",
        });
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  /** One place for both controls: they hit the same endpoint. */
  const apply = useCallback(
    async (update: { provider?: string; enabled?: string[] }) => {
      setSaving(true);
      setError(null);
      setSaved(false);
      try {
        const config = await setAiConfig(update);
        setState({ kind: "ready", config });
        setSaved(true);
      } catch (caught) {
        // The server's refusal is already written for a person - it names the
        // provider and the fix - so it is shown as-is rather than replaced
        // with something vaguer.
        setError(
          caught instanceof Error
            ? caught.message
            : "The AI configuration could not be changed. Please try again.",
        );
      } finally {
        setSaving(false);
      }
    },
    [],
  );

  const choose = useCallback(
    (provider: string) => {
      if (state.kind !== "ready" || provider === state.config.active_provider) return;
      void apply({ provider });
    },
    [state, apply],
  );

  const toggle = useCallback(
    (key: string, enabled: boolean) => {
      if (state.kind !== "ready") return;
      const next = enabled
        ? [...new Set([...state.config.enabled_providers, key])]
        : state.config.enabled_providers.filter((p) => p !== key);
      void apply({ enabled: next });
    },
    [state, apply],
  );

  // Nothing at all for a normal user. See the note at the top of the file.
  if (state.kind === "hidden" || state.kind === "checking") return null;

  if (state.kind === "failed") {
    return (
      <section className="section" aria-labelledby="owner-ai-heading">
        <div className="section__head">
          <h2 className="section__title" id="owner-ai-heading">
            Owner AI configuration
          </h2>
        </div>
        <div className="notice notice--error" role="alert">
          <IconAlert size={16} />
          <p>{state.message}</p>
        </div>
      </section>
    );
  }

  const { config } = state;
  // The fallback provider exists but the owner has switched it off - a
  // different situation from having no API key, and it needs different words.
  const fallbackDisabled = !config.enabled_providers.includes(config.fallback_provider);

  return (
    <section className="section" aria-labelledby="owner-ai-heading">
      <div className="section__head">
        <h2 className="section__title" id="owner-ai-heading">
          Owner AI configuration
        </h2>
        <span className="badge badge--accent">Owner only</span>
      </div>

      <div className="card">
        <div className="card__body">
          <div className="settingrow">
            <div className="settingrow__label">
              <strong>Primary AI model</strong>
              <p className="settingrow__hint">
                Used for every new analysis. Papers already analysed keep the
                model that produced them.
              </p>
            </div>
            <div className="settingrow__control">
              <select
                className="ownerselect"
                value={config.active_provider}
                onChange={(e) => choose(e.target.value)}
                disabled={saving}
                aria-label="Primary AI model"
              >
                {config.available_providers.map((key) => (
                  <option key={key} value={key}>
                    {key === config.active_provider
                      ? config.active_provider_label
                      : config.fallback_provider_label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="settingrow">
            <div className="settingrow__label">
              <strong>Fallback</strong>
              <p className="settingrow__hint">
                Automatic. Whichever provider is not primary takes over if the
                primary is rate limited or temporarily unavailable, once per
                analysis. It is not used for invalid files or configuration
                errors, which would fail the same way on either provider
                {fallbackDisabled
                  ? ", and it is switched off below, so an analysis that fails on the primary now fails rather than moving."
                  : "."}
              </p>
            </div>
            <div className="settingrow__control">
              <p className="ownerfallback">
                <strong>{config.fallback_provider_label}</strong>
                <span className="faint">
                  {" "}
                  {config.fallback_available ? "(automatic)" : "(not in use)"}
                </span>
              </p>
              {!config.fallback_available && (
                <p className="authfield__problem">
                  {fallbackDisabled
                    ? "This provider is switched off, so nothing will fall back to it."
                    : "No API key is configured for this provider, so no fallback is currently available."}
                </p>
              )}
            </div>
          </div>

          {/* ---- availability ---- */}
          <hr className="accountrule" />

          <div className="settingrow">
            <div className="settingrow__label">
              <strong>AI provider availability</strong>
              <p className="settingrow__hint">
                A switched-off provider is not used for new analyses or as a
                fallback. At least one must stay on, and the primary cannot be
                switched off - make the other one primary first. Analyses
                already saved keep the model that produced them.
              </p>
            </div>
            <div className="settingrow__control">
              <ul className="ownerproviders">
                {config.providers.map((p) => (
                  <li key={p.key} className="ownerprovider">
                    <div className="ownerprovider__id">
                      <strong>{p.label}</strong>
                      <span className="ownerprovider__model">{p.model}</span>
                      {p.is_primary && <span className="badge badge--accent">Primary</span>}
                    </div>

                    <label className="ownerprovider__switch">
                      <input
                        type="checkbox"
                        checked={p.enabled}
                        disabled={saving}
                        onChange={(e) => toggle(p.key, e.target.checked)}
                        aria-label={`${p.label} enabled`}
                      />
                      <span>{p.enabled ? "Enabled" : "Disabled"}</span>
                    </label>

                    {p.enabled && !p.has_credentials && (
                      <p className="authfield__problem ownerprovider__note">
                        Enabled, but the server has no API key for it, so it
                        cannot actually run.
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {saving && (
            <p className="settingrow__hint" role="status">
              Saving…
            </p>
          )}
          {saved && !saving && !error && (
            <div className="notice notice--spaced authnotice--ok" role="status">
              <IconCheck size={16} />
              <p>
                New analyses will use <strong>{config.active_provider_label}</strong>
                {config.fallback_available
                  ? `, falling back to ${config.fallback_provider_label}.`
                  : ", with no fallback."}
              </p>
            </div>
          )}
          {error && (
            <div className="notice notice--error notice--spaced" role="alert">
              <IconAlert size={16} />
              <p>{error}</p>
            </div>
          )}

          <div className="notice notice--info notice--spaced">
            <IconInfo size={16} />
            <p>
              API keys are never stored here. They live in the server
              environment and are never sent to the browser.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

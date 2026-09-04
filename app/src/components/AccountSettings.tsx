"use client";

/**
 * Account settings, for every signed-in user.
 *
 * Three things, in the order someone looks for them: who you are, your
 * password, and the way out.
 *
 * WHOSE ACCOUNT THIS EDITS
 * ------------------------
 * Always and only the signed-in one. Neither call takes a user id, and there
 * is deliberately nowhere to put one: `supabase.auth.updateUser` acts on
 * whoever the access token belongs to, so the identity comes from the token
 * rather than from anything the page could send. There is no code path here
 * that could address another account, correctly or otherwise.
 *
 * THE GOOGLE CASE
 * ---------------
 * An account created through Google has no password. Offering to change one
 * would fail with "that is not your current password", which is both wrong and
 * alarming. `hasPassword` comes from the account's identities, and the section
 * says what is actually true instead.
 */

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { Field, FormError } from "@/components/AuthCard";
import { IconCheck, IconInfo } from "@/components/Icons";
import {
  MIN_PASSWORD_LENGTH,
  passwordProblem,
  useAuth,
} from "@/lib/auth";

function Saved({ children }: { children: React.ReactNode }) {
  return (
    <div className="notice notice--spaced authnotice--ok" role="status">
      <IconCheck size={16} />
      <p>{children}</p>
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * Name
 * ------------------------------------------------------------------ */

function NameSetting() {
  const { displayName, updateFullName } = useAuth();
  const [name, setName] = useState(displayName);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  // Keep the field in step with the account when it loads or changes
  // elsewhere - but never while the user is mid-edit, which would wipe what
  // they were typing.
  useEffect(() => {
    if (!busy) setName(displayName);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [displayName]);

  const dirty = name.trim() !== displayName.trim();

  const submit = useCallback(
    async (event: React.FormEvent) => {
      event.preventDefault();
      setError(null);
      setSaved(false);
      setBusy(true);
      try {
        await updateFullName(name);
        setSaved(true);
      } catch (caught) {
        setError(
          caught instanceof Error ? caught.message : "Your name could not be updated.",
        );
      } finally {
        setBusy(false);
      }
    },
    [name, updateFullName],
  );

  return (
    <form onSubmit={submit} noValidate>
      <FormError message={error} />
      {saved && !error && <Saved>Your name has been updated.</Saved>}

      <Field
        label="Full name"
        value={name}
        onChange={(v) => {
          setName(v);
          setSaved(false);
        }}
        placeholder="Your name"
        autoComplete="name"
        hint="Shown in the header and on your account menu."
      />

      <button
        type="submit"
        className="btn btn--primary"
        disabled={busy || !dirty || !name.trim()}
      >
        {busy ? "Saving…" : "Save name"}
      </button>
    </form>
  );
}

/* ------------------------------------------------------------------ *
 * Password
 * ------------------------------------------------------------------ */

function PasswordSetting() {
  const { hasPassword, signInMethods, changePassword } = useAuth();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  // An account with no password cannot have one changed. Say so accurately
  // rather than presenting a form that cannot succeed.
  if (!hasPassword) {
    const provider = signInMethods.find((m) => m !== "email") ?? "an external provider";
    const label = provider === "google" ? "Google" : provider;
    return (
      <div className="notice notice--info">
        <IconInfo size={16} />
        <div>
          <p>
            <strong>You sign in with {label}.</strong> This account has no
            ResearchForge password, so there is nothing to change here.
          </p>
          <p style={{ marginBottom: 0 }}>
            Your password is managed by {label}, not by ResearchForge.
          </p>
        </div>
      </div>
    );
  }

  const mismatch =
    confirm.length > 0 && confirm !== next ? "Those passwords do not match." : null;

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    setSaved(false);

    if (!current) {
      setError("Please enter your current password.");
      return;
    }
    const weak = passwordProblem(next);
    if (weak) {
      setError(weak);
      return;
    }
    if (next !== confirm) {
      setError("Those passwords do not match. Please retype them.");
      return;
    }
    if (next === current) {
      setError("That is the password you already have. Please choose a different one.");
      return;
    }

    setBusy(true);
    try {
      await changePassword(current, next);
      setSaved(true);
      // Cleared on success only. After a failure the new password is kept so
      // a mistyped CURRENT password does not cost the user all three fields.
      setCurrent("");
      setNext("");
      setConfirm("");
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Your password could not be updated.",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} noValidate>
      <FormError message={error} />
      {saved && !error && (
        <Saved>
          Your password has been changed. Use the new one next time you sign in.
        </Saved>
      )}

      <Field
        label="Current password"
        type="password"
        value={current}
        onChange={setCurrent}
        placeholder="Your current password"
        autoComplete="current-password"
        hint="Checked before anything is changed, so a signed-in browser left unattended is not enough to take the account over."
      />
      <Field
        label="New password"
        type="password"
        value={next}
        onChange={setNext}
        placeholder="Choose a new password"
        autoComplete="new-password"
        hint={`At least ${MIN_PASSWORD_LENGTH} characters.`}
      />
      <Field
        label="Confirm new password"
        type="password"
        value={confirm}
        onChange={setConfirm}
        placeholder="Type it again"
        autoComplete="new-password"
        problem={mismatch}
      />

      <button type="submit" className="btn btn--primary" disabled={busy}>
        {busy ? "Updating…" : "Update password"}
      </button>
    </form>
  );
}

/* ------------------------------------------------------------------ *
 * The section
 * ------------------------------------------------------------------ */

export default function AccountSettings() {
  const { isAuthenticated, email, signOut } = useAuth();
  const router = useRouter();
  const [signingOut, setSigningOut] = useState(false);

  const leave = useCallback(async () => {
    setSigningOut(true);
    await signOut();
    // `replace`, not `push`: Back must not return to a page that is now behind
    // a sign-in redirect.
    router.replace("/");
  }, [signOut, router]);

  if (!isAuthenticated) return null;

  return (
    <section className="section" aria-labelledby="account-heading">
      <div className="section__head">
        <h2 className="section__title" id="account-heading">
          Account
        </h2>
      </div>

      <div className="card">
        <div className="card__body">
          <NameSetting />

          <hr className="accountrule" />

          <div className="settingrow">
            <div className="settingrow__label">
              <strong>Email address</strong>
              <p className="settingrow__hint">
                {/* Read-only, deliberately. Changing an email address safely
                    needs confirmation at BOTH addresses, or it becomes a way
                    to take an account over. That flow is not built, so this
                    does not pretend to offer it. */}
                Used to sign in and to reach you about your account. Changing it
                is not available yet.
              </p>
            </div>
            <div className="settingrow__control">
              <input
                className="authfield__input accountreadonly"
                value={email}
                readOnly
                aria-readonly="true"
                aria-label="Email address, read only"
              />
            </div>
          </div>
        </div>
      </div>

      <div className="section__head" style={{ marginTop: "1.5rem" }}>
        <h2 className="section__title" id="security-heading">
          Security
        </h2>
      </div>
      <div className="card" aria-labelledby="security-heading">
        <div className="card__body">
          <PasswordSetting />
        </div>
      </div>

      <div className="section__head" style={{ marginTop: "1.5rem" }}>
        <h2 className="section__title" id="session-heading">
          Session
        </h2>
      </div>
      <div className="card" aria-labelledby="session-heading">
        <div className="card__body">
          <div className="settingrow">
            <div className="settingrow__label">
              <strong>Sign out</strong>
              <p className="settingrow__hint">
                Ends this session on this device. Your papers and analyses stay
                in your library.
              </p>
            </div>
            <div className="settingrow__control">
              <button
                className="btn btn--danger"
                onClick={leave}
                disabled={signingOut}
              >
                {signingOut ? "Signing out…" : "Sign out"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

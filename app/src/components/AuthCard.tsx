"use client";

/**
 * The shared frame and form controls for the four account screens.
 *
 * One place for the card, the brand line, the field markup, the error banner
 * and the submit button, so sign-in, sign-up, forgot-password and
 * reset-password cannot drift into four slightly different designs.
 *
 * Everything here is built from the application's existing tokens and classes -
 * `card`, `btn btn--primary`, `notice notice--error`, the same radii and
 * shadows - so the account screens read as the same product as the dashboard
 * rather than as a bolted-on login.
 */

import Image from "next/image";
import Link from "next/link";
import { useId, useState } from "react";

import { IconAlert, IconCheck, IconInfo } from "@/components/Icons";
import { isAuthConfigured } from "@/lib/supabase";

/* ------------------------------------------------------------------ *
 * Frame
 * ------------------------------------------------------------------ */

export function AuthCard({
  title,
  subtitle,
  children,
  footer,
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
}) {
  return (
    <div className="authpage">
      <header className="authpage__head">
        <Link href="/" className="authpage__brand" aria-label="ResearchForge home">
          <Image
            src="/brand/researchforge-mark-192.png"
            alt=""
            width={38}
            height={30}
            className="brandmark"
            priority
          />
          <span className="authpage__brandname">ResearchForge</span>
        </Link>
        {footer}
      </header>

      <main className="authpage__body">
        <div className="card authpage__card">
          <h1 className="authpage__title">{title}</h1>
          <p className="authpage__sub">{subtitle}</p>

          {/* Said once, at the top, on every account screen. Without it a
              deployment with no Supabase settings presents a working-looking
              form whose every submission fails in a way that reads like a
              wrong password. */}
          {!isAuthConfigured && (
            <div className="notice notice--warn notice--spaced">
              <IconInfo size={16} />
              <p>
                <strong>Accounts are not set up on this deployment.</strong> The
                form below cannot succeed until the server is configured.
              </p>
            </div>
          )}

          {children}
        </div>

        <p className="authpage__foot">
          Your research library is private to your account.
        </p>
      </main>
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * Messages
 * ------------------------------------------------------------------ */

/**
 * A failure, written for the reader.
 *
 * `role="alert"` so a screen reader announces it the moment it appears -
 * otherwise a blind user submits the form, hears nothing, and has no way to
 * know why nothing happened.
 */
export function FormError({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <div className="notice notice--error notice--spaced" role="alert">
      <IconAlert size={16} />
      <p>{message}</p>
    </div>
  );
}

export function FormSuccess({ children }: { children: React.ReactNode }) {
  return (
    <div className="notice notice--spaced authnotice--ok" role="status">
      <IconCheck size={16} />
      <div>{children}</div>
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * Fields
 * ------------------------------------------------------------------ */

interface FieldProps {
  label: string;
  type?: "text" | "email" | "password";
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  autoComplete?: string;
  /** A per-field message shown beneath the input, in the error colour. */
  problem?: string | null;
  hint?: string;
  autoFocus?: boolean;
  required?: boolean;
}

export function Field({
  label,
  type = "text",
  value,
  onChange,
  placeholder,
  autoComplete,
  problem,
  hint,
  autoFocus,
  required = true,
}: FieldProps) {
  const id = useId();
  const describedBy = problem ? `${id}-problem` : hint ? `${id}-hint` : undefined;
  const [revealed, setRevealed] = useState(false);

  // A password field that can be shown. Typing a long passphrase blind is the
  // main reason people fall back to a short one they can retype confidently.
  const isPassword = type === "password";
  const inputType = isPassword && revealed ? "text" : type;

  return (
    <div className="authfield">
      <label className="authfield__label" htmlFor={id}>
        {label}
      </label>
      <div className={`authfield__wrap${problem ? " authfield__wrap--bad" : ""}`}>
        <input
          id={id}
          className="authfield__input"
          type={inputType}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          autoComplete={autoComplete}
          autoFocus={autoFocus}
          required={required}
          aria-invalid={problem ? true : undefined}
          aria-describedby={describedBy}
        />
        {isPassword && (
          <button
            type="button"
            className="authfield__reveal"
            onClick={() => setRevealed((v) => !v)}
            aria-label={revealed ? "Hide password" : "Show password"}
            // Excluded from the tab order: it sits between the password field
            // and the submit button, and tabbing into it on the way to
            // submitting is a small irritation on every single sign-in.
            tabIndex={-1}
          >
            {revealed ? "Hide" : "Show"}
          </button>
        )}
      </div>
      {problem ? (
        <p className="authfield__problem" id={`${id}-problem`}>
          {problem}
        </p>
      ) : hint ? (
        <p className="authfield__hint" id={`${id}-hint`}>
          {hint}
        </p>
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * Submit
 * ------------------------------------------------------------------ */

export function SubmitButton({
  busy,
  busyLabel,
  children,
}: {
  busy: boolean;
  busyLabel: string;
  children: React.ReactNode;
}) {
  return (
    <button
      type="submit"
      className="btn btn--primary btn--lg authsubmit"
      disabled={busy}
    >
      {busy ? (
        <>
          <span className="authsubmit__spinner" aria-hidden="true" />
          {busyLabel}
        </>
      ) : (
        children
      )}
    </button>
  );
}

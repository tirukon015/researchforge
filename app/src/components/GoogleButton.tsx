"use client";

/**
 * "Continue with Google", plus the divider that separates it from the form.
 *
 * One component used by both sign-in and sign-up, so the two screens cannot
 * drift apart - the commonest way an OAuth button ends up saying "Sign in with
 * Google" on one page and "Sign up with Google" on the other, implying they do
 * different things. They do not: Google sign-in creates the account if it does
 * not exist and signs in if it does, so the label is the same on both.
 *
 * DESIGN
 * ------
 * Built from the project's existing `btn` class and colour tokens, so it sits
 * in the same visual system as everything else. The only thing it adds is
 * Google's own mark, which is required: Google's branding guidelines do not
 * permit recolouring the G or substituting a generic icon, so the four brand
 * colours are hard-coded in the SVG rather than inheriting `currentColor` the
 * way the project's own icons do.
 */

import { useCallback, useState } from "react";

import { useAuth } from "@/lib/auth";

/** Google's "G", official four-colour mark. Not themed - see the note above. */
function GoogleMark() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true" focusable="false">
      <path
        fill="#4285F4"
        d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92c1.7-1.57 2.68-3.88 2.68-6.62z"
      />
      <path
        fill="#34A853"
        d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.81.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.03-3.7H.96v2.33A9 9 0 0 0 9 18z"
      />
      <path
        fill="#FBBC05"
        d="M3.97 10.72a5.4 5.4 0 0 1 0-3.44V4.95H.96a9 9 0 0 0 0 8.1l3.01-2.33z"
      />
      <path
        fill="#EA4335"
        d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.58C13.46.89 11.43 0 9 0A9 9 0 0 0 .96 4.95l3.01 2.33C4.68 5.16 6.66 3.58 9 3.58z"
      />
    </svg>
  );
}

export default function GoogleButton({
  /** Where to return after the round trip. Defaults to the dashboard. */
  next,
  /** Surfaced to the parent so the page shows it in its own error banner. */
  onError,
  disabled,
}: {
  next?: string;
  onError?: (message: string) => void;
  disabled?: boolean;
}) {
  const { signInWithGoogle } = useAuth();
  const [busy, setBusy] = useState(false);

  const start = useCallback(async () => {
    setBusy(true);
    onError?.("");
    try {
      await signInWithGoogle(next);
      // On success the browser is already navigating to Google, so `busy`
      // deliberately stays true: re-enabling the button would invite a second
      // click that starts a competing OAuth flow and invalidates the first.
    } catch (caught) {
      setBusy(false);
      onError?.(
        caught instanceof Error
          ? caught.message
          : "Could not start sign-in with Google. Please try again.",
      );
    }
  }, [signInWithGoogle, next, onError]);

  return (
    <>
      <div className="authdivider">
        <span>or continue with</span>
      </div>

      <button
        type="button"
        className="btn btn--lg authsubmit authgoogle"
        onClick={start}
        disabled={busy || disabled}
      >
        {busy ? (
          <>
            <span className="authsubmit__spinner authsubmit__spinner--dark" aria-hidden="true" />
            Redirecting to Google…
          </>
        ) : (
          <>
            <GoogleMark />
            Continue with Google
          </>
        )}
      </button>
    </>
  );
}

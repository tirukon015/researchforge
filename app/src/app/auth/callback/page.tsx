"use client";

/**
 * Where Google (and every other Supabase redirect flow) comes back to.
 *
 * THE FLOW
 * --------
 *   1. The user presses "Continue with Google".
 *   2. `signInWithOAuth` sends them to Google via Supabase.
 *   3. Google returns them to Supabase, which returns them HERE with a
 *      one-time `?code=` on the URL.
 *   4. The Supabase client is created with `detectSessionInUrl: true`, so it
 *      spots that code as it initialises and exchanges it for a session.
 *   5. `onAuthStateChange` fires, `AuthProvider` picks the session up, and
 *      this page forwards to the dashboard.
 *
 * WHY THIS PAGE WAITS INSTEAD OF EXCHANGING THE CODE ITSELF
 * ---------------------------------------------------------
 * The obvious implementation calls `exchangeCodeForSession(code)` here. That
 * is a bug: `detectSessionInUrl` has already consumed the code by the time
 * this component mounts, and a one-time code cannot be redeemed twice, so the
 * explicit call fails and this page would report a failure on a sign-in that
 * actually succeeded. Waiting for the session is the correct shape.
 *
 * WHY THE ROUTE IS ALSO USED BY EMAIL CONFIRMATION
 * ------------------------------------------------
 * A Supabase confirmation link lands the same way, with a token in the URL. So
 * this page is written around "wait for a session to appear, then move on"
 * rather than around Google specifically, and the copy stays neutral.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { AuthCard, FormError } from "@/components/AuthCard";
import { humanError, takeDestination, useAuth } from "@/lib/auth";
import { getSupabase } from "@/lib/supabase";

/**
 * How long to wait for the session before giving up.
 *
 * Generous, because this covers a code exchange that makes its own network
 * call to Supabase on a connection we know nothing about. Too short and a slow
 * link reports a failure that never happened; too long and a genuinely broken
 * callback leaves the reader watching a spinner with no way forward.
 */
const TIMEOUT_MS = 20_000;

type Phase =
  | { kind: "working" }
  | { kind: "failed"; message: string };

/**
 * Providers report failures as URL parameters, not as thrown errors, and they
 * are inconsistent about WHERE: OAuth puts them in the query string, the
 * implicit token flow puts them in the hash fragment. Both are checked.
 */
function readUrlError(): string | null {
  if (typeof window === "undefined") return null;

  const query = new URLSearchParams(window.location.search);
  const hash = new URLSearchParams(window.location.hash.replace(/^#/, ""));

  for (const params of [query, hash]) {
    const code = params.get("error") ?? params.get("error_code");
    if (!code) continue;
    // `error_description` is the human-ish one; `error` is the machine code.
    // Both are fed to humanError, which matches on the codes and falls back to
    // a plain sentence rather than showing a raw provider string.
    const described = params.get("error_description") ?? "";
    return humanError(
      new Error(`${code} ${described}`),
      "Sign-in could not be completed. Please try again.",
    );
  }
  return null;
}

export default function AuthCallbackPage() {
  const { state } = useAuth();
  const router = useRouter();
  const [phase, setPhase] = useState<Phase>({ kind: "working" });

  // Guards against forwarding twice - `onAuthStateChange` and the poll below
  // can both resolve in the same tick, and two router.replace calls race.
  const done = useRef(false);

  const finish = useCallback(() => {
    if (done.current) return;
    done.current = true;
    // `replace`, never `push`: the callback URL carried a one-time code that
    // is now spent, so Back must not return to it.
    router.replace(takeDestination("/dashboard"));
  }, [router]);

  useEffect(() => {
    const urlError = readUrlError();
    if (urlError) {
      setPhase({ kind: "failed", message: urlError });
      return;
    }

    const supabase = getSupabase();
    if (!supabase) {
      setPhase({
        kind: "failed",
        message:
          "Accounts are not set up on this deployment, so sign-in cannot be completed.",
      });
      return;
    }

    let cancelled = false;

    // Three ways the session can arrive, all wired up because which one fires
    // depends on whether the client had already finished initialising before
    // this component mounted.
    const { data: sub } = supabase.auth.onAuthStateChange((_event, session) => {
      if (!cancelled && session) finish();
    });

    void supabase.auth.getSession().then(({ data }) => {
      if (!cancelled && data.session) finish();
    });

    const timer = setTimeout(() => {
      if (cancelled || done.current) return;
      void supabase.auth.getSession().then(({ data }) => {
        if (cancelled || done.current) return;
        if (data.session) {
          finish();
        } else {
          setPhase({
            kind: "failed",
            message:
              "Sign-in did not complete. The link may have expired or already been used.",
          });
        }
      });
    }, TIMEOUT_MS);

    return () => {
      cancelled = true;
      clearTimeout(timer);
      sub.subscription.unsubscribe();
    };
  }, [finish]);

  // Covers the case where AuthProvider resolved the session before this
  // effect ran at all.
  useEffect(() => {
    if (state.kind === "authenticated") finish();
  }, [state.kind, finish]);

  if (phase.kind === "failed") {
    return (
      <AuthCard
        title="Sign-in could not be completed"
        subtitle="Nothing has been changed on your account."
        footer={
          <p className="authpage__switch">
            <Link href="/sign-in">Back to sign in</Link>
          </p>
        }
      >
        <FormError message={phase.message} />
        <Link href="/sign-in" className="btn btn--primary btn--lg authsubmit">
          Try signing in again
        </Link>
        <p className="authpage__alt">
          You can also <Link href="/sign-up">create an account</Link> with an
          email address and password.
        </p>
      </AuthCard>
    );
  }

  return (
    <AuthCard title="Signing you in" subtitle="Completing your sign-in, one moment.">
      <div className="authgate" role="status" aria-live="polite">
        <span className="authgate__spinner" aria-hidden="true" />
        <p className="authgate__text">Finishing up…</p>
      </div>
    </AuthCard>
  );
}

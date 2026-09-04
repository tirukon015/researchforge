"use client";

/**
 * The signed-in account, shared across every route.
 *
 * WHAT THIS OWNS
 * --------------
 * Who is signed in, whether we have finished finding out, and the five things
 * a person can do about it: create an account, sign in, sign out, ask for a
 * password reset, and set a new password.
 *
 * It also owns the ACCESS TOKEN, which is the thing the rest of the app
 * actually needs. `src/lib/api.ts` reads it through `setTokenReader` below and
 * puts it on every backend request; the backend hands it to Postgres, and Row
 * Level Security uses it to decide which rows exist. That chain is the whole
 * reason one researcher cannot see another's papers.
 *
 * WHY ERRORS ARE TRANSLATED HERE
 * ------------------------------
 * Supabase returns messages written for developers: "Invalid login
 * credentials", "AuthApiError", "For security purposes, you can only request
 * this after 47 seconds". Showing those to a researcher is both unhelpful and
 * a small information leak - "user not found" tells a stranger which email
 * addresses have accounts. `humanError` maps them onto sentences written for
 * the person reading them, and deliberately gives the same answer for a wrong
 * password as for an unknown account.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import type { Session, User } from "@supabase/supabase-js";

import { setTokenReader } from "@/lib/api";
import {
  authRedirectUrl,
  getSupabase,
  isAuthConfigured,
  isSafeReturnPath,
} from "@/lib/supabase";

/** What we know about the account, and whether we have finished asking. */
export type AuthState =
  /** Still restoring a stored session. Render nothing decisive yet. */
  | { kind: "loading" }
  /** No account. Public pages only. */
  | { kind: "anonymous" }
  /** Signed in. */
  | { kind: "authenticated"; user: User; session: Session }
  /** Supabase is not configured in this build; accounts cannot work at all. */
  | { kind: "unconfigured" };

export interface AuthValue {
  state: AuthState;
  /** Convenience: the user, or null. */
  user: User | null;
  /** Convenience: true only once we KNOW there is a session. */
  isAuthenticated: boolean;
  /** Convenience: true while we still do not know either way. */
  isLoading: boolean;
  /** The best available human name for the signed-in account. */
  displayName: string;
  email: string;

  signUp: (input: SignUpInput) => Promise<SignUpResult>;
  signIn: (email: string, password: string) => Promise<void>;
  /**
   * Hand off to Google. Resolves only if the redirect FAILED to start - on
   * success the browser has already left this page, so there is nothing to
   * return to.
   */
  signInWithGoogle: (next?: string) => Promise<void>;
  signOut: () => Promise<void>;
  requestPasswordReset: (email: string) => Promise<void>;
  updatePassword: (password: string) => Promise<void>;
}

export interface SignUpInput {
  fullName: string;
  email: string;
  password: string;
}

export interface SignUpResult {
  /**
   * True when Supabase created the account but has not started a session,
   * which is what "confirm your email" looks like from here. The sign-up page
   * shows a "check your inbox" screen instead of navigating into the app.
   *
   * Derived from the response rather than from a setting we would have to keep
   * in step with the Supabase dashboard by hand.
   */
  needsEmailConfirmation: boolean;
}

/**
 * An error already written for the person who will read it.
 *
 * A distinct class so a form can tell "we translated this" from a genuine
 * crash, and never print a raw exception into the interface.
 */
export class AuthError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "AuthError";
  }
}

/**
 * Where to send the user after an OAuth round trip.
 *
 * Kept in sessionStorage rather than in the `redirectTo` query string, on
 * purpose. Supabase validates `redirectTo` against the project's redirect
 * allow-list, and a URL carrying a `?next=` the operator did not anticipate is
 * an easy way to have sign-in silently fall back to the Site URL. Keeping the
 * destination on this origin means ONE plain URL needs allow-listing, and it
 * cannot be tampered with by whoever crafted the link either.
 *
 * sessionStorage, not localStorage: it belongs to this tab and this attempt.
 */
const NEXT_KEY = "researchforge.auth.next";

export function rememberDestination(next: string | null | undefined): void {
  try {
    if (isSafeReturnPath(next)) {
      sessionStorage.setItem(NEXT_KEY, next as string);
    } else {
      sessionStorage.removeItem(NEXT_KEY);
    }
  } catch {
    /* storage blocked; the caller falls back to the default destination */
  }
}

export function takeDestination(fallback = "/dashboard"): string {
  try {
    const stored = sessionStorage.getItem(NEXT_KEY);
    sessionStorage.removeItem(NEXT_KEY);
    // Re-checked on the way OUT as well as in. Storage is writable by any
    // script on this origin, and an absolute URL here would turn the callback
    // into an open redirect.
    if (isSafeReturnPath(stored)) {
      return stored as string;
    }
  } catch {
    /* storage blocked */
  }
  return fallback;
}

const NOT_CONFIGURED =
  "Accounts are not set up on this deployment yet, so signing in is not " +
  "possible. Everything else on this site still works.";

/**
 * Supabase's message -> a sentence for a researcher.
 *
 * Matched on substrings because Supabase does not give these stable codes, and
 * the wording has changed between versions. An unrecognised message falls back
 * to something honest and non-technical rather than being shown verbatim.
 */
export function humanError(raw: unknown, fallback: string): string {
  const message = raw instanceof Error ? raw.message : String(raw ?? "");
  const text = message.toLowerCase();

  // Deliberately identical for "wrong password" and "no such account".
  // Distinguishing them turns the sign-in form into a way to discover which
  // email addresses are registered here.
  if (
    text.includes("invalid login credentials") ||
    text.includes("invalid credentials") ||
    text.includes("user not found")
  ) {
    return "That email address and password do not match an account. Please check both and try again.";
  }
  if (text.includes("email not confirmed")) {
    return "Please confirm your email address first. Open the link in the message we sent you, then sign in.";
  }
  if (
    text.includes("already registered") ||
    text.includes("already exists") ||
    text.includes("user already")
  ) {
    return "An account already exists for that email address. Try signing in instead, or reset your password.";
  }
  if (text.includes("password should be") || text.includes("password is too short")) {
    return "That password is too short. Please use at least 8 characters.";
  }
  if (text.includes("weak password") || text.includes("password is known")) {
    return "That password is too easy to guess. Please choose a longer or less common one.";
  }
  if (text.includes("unable to validate email") || text.includes("invalid email")) {
    return "That does not look like a valid email address.";
  }
  // Supabase rate-limits reset emails and sign-up attempts. It states the
  // delay in seconds, which is worth keeping - it turns "try later" into
  // something the reader can act on.
  if (text.includes("for security purposes") || text.includes("rate limit") || text.includes("too many requests")) {
    const seconds = message.match(/(\d+)\s*seconds?/i)?.[1];
    return seconds
      ? `Too many attempts. Please wait ${seconds} seconds and try again.`
      : "Too many attempts in a short time. Please wait a moment and try again.";
  }
  if (text.includes("same as the old password") || text.includes("should be different")) {
    return "That is the password you already have. Please choose a different one.";
  }
  if (text.includes("token has expired") || text.includes("expired") || text.includes("invalid token")) {
    return "That link has expired. Please request a new password reset email.";
  }
  if (text.includes("session") && text.includes("missing")) {
    return "This password reset link is no longer valid. Please request a new one.";
  }
  if (text.includes("failed to fetch") || text.includes("network") || text.includes("load failed")) {
    return "Could not reach the sign-in service. Check your connection and try again.";
  }

  // --- OAuth. These arrive as `error` / `error_description` on the callback
  // URL rather than as a thrown SDK error, so they are matched on the codes
  // Google and Supabase actually send.
  if (text.includes("access_denied") || text.includes("user_denied")) {
    return "Sign-in with Google was cancelled. You can try again, or use your email and password.";
  }
  if (text.includes("provider is not enabled") || text.includes("unsupported provider")) {
    return "Google sign-in is not enabled for this deployment. Please use your email and password.";
  }
  if (text.includes("bad_oauth_state") || text.includes("invalid state")) {
    return "That Google sign-in attempt could not be completed - it may have expired or been started in another tab. Please try again.";
  }
  if (text.includes("redirect_uri_mismatch") || text.includes("bad_redirect_uri")) {
    return "Google sign-in is not configured for this address. Please use your email and password, or contact the site owner.";
  }
  if (text.includes("server_error") || text.includes("temporarily_unavailable")) {
    return "Google could not complete sign-in just now. Please try again in a moment.";
  }
  if (
    text.includes("email address is already registered") ||
    text.includes("identity_already_exists")
  ) {
    return "An account already exists for that email address with a different sign-in method. Sign in the way you did originally.";
  }

  return fallback;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>(
    isAuthConfigured ? { kind: "loading" } : { kind: "unconfigured" },
  );

  // The live access token, kept in a ref so `api.ts` can read the CURRENT one
  // at request time. Closing over a state value instead would send whichever
  // token existed when the function was created, which after a silent refresh
  // is the expired one.
  const tokenRef = useRef<string | null>(null);

  useEffect(() => {
    setTokenReader(() => tokenRef.current);
    return () => setTokenReader(null);
  }, []);

  useEffect(() => {
    const supabase = getSupabase();
    if (!supabase) {
      setState({ kind: "unconfigured" });
      return;
    }

    let active = true;

    const apply = (session: Session | null) => {
      if (!active) return;
      tokenRef.current = session?.access_token ?? null;
      setState(
        session?.user
          ? { kind: "authenticated", user: session.user, session }
          : { kind: "anonymous" },
      );
    };

    // Restore whatever session is already in storage before the first paint
    // decides anything. Until this resolves the state stays "loading", which
    // is why the route guard must not redirect on "not authenticated" alone -
    // it would bounce a signed-in reader to the sign-in page on every reload.
    void supabase.auth
      .getSession()
      .then(({ data }) => apply(data.session))
      .catch(() => {
        if (active) setState({ kind: "anonymous" });
      });

    // Covers sign-in, sign-out, silent token refresh, and the session that
    // appears from the URL after a password-reset link.
    const { data: subscription } = supabase.auth.onAuthStateChange(
      (_event, session) => apply(session),
    );

    return () => {
      active = false;
      subscription.subscription.unsubscribe();
    };
  }, []);

  const requireClient = useCallback(() => {
    const supabase = getSupabase();
    if (!supabase) throw new AuthError(NOT_CONFIGURED);
    return supabase;
  }, []);

  const signUp = useCallback(
    async ({ fullName, email, password }: SignUpInput): Promise<SignUpResult> => {
      const supabase = requireClient();
      const { data, error } = await supabase.auth.signUp({
        email: email.trim(),
        password,
        options: {
          // Stored on the account, not in our database. The backend reads it
          // back from the token holder, so a name never needs a table of its
          // own - and never needs to be kept in step with one.
          data: { full_name: fullName.trim() },
          // Where the confirmation link returns to.
          //
          // /auth/callback, NOT /dashboard. The confirmation link establishes
          // the session as it lands, and /dashboard is behind the route guard:
          // arriving there a moment before the session settles bounces the
          // user to sign-in, which is a confusing end to having just confirmed
          // their email. The callback exists to wait for exactly that.
          //
          // It also means signup confirmation and Google sign-in share ONE
          // allow-listed URL instead of needing two.
          emailRedirectTo: authRedirectUrl("/auth/callback"),
        },
      });
      if (error) {
        throw new AuthError(
          humanError(error, "Your account could not be created. Please try again."),
        );
      }
      // A user with no session means Supabase is waiting for the email to be
      // confirmed. Reading it from the response keeps this correct whether or
      // not confirmation is switched on in the project.
      return { needsEmailConfirmation: data.session === null };
    },
    [requireClient],
  );

  const signIn = useCallback(
    async (email: string, password: string) => {
      const supabase = requireClient();
      const { error } = await supabase.auth.signInWithPassword({
        email: email.trim(),
        password,
      });
      if (error) {
        throw new AuthError(
          humanError(
            error,
            "Could not sign you in just now. Please try again in a moment.",
          ),
        );
      }
    },
    [requireClient],
  );

  const signInWithGoogle = useCallback(
    async (next?: string) => {
      const supabase = requireClient();
      rememberDestination(next);

      const { error } = await supabase.auth.signInWithOAuth({
        provider: "google",
        options: {
          // ONE fixed path on the origin actually being used, so it is right
          // on localhost, on every preview URL, and on the custom domain with
          // nothing to remember to change.
          //
          // ⚠️ This exact URL MUST be in the Supabase redirect allow-list.
          // Supabase does not refuse an unlisted redirect when the flow
          // starts - it accepts it and then substitutes the project's Site URL
          // on the way back, landing the user on that site's ROOT instead.
          // That is precisely the "/?access_token=..." on the wrong host that
          // this project shipped with.
          redirectTo: authRedirectUrl("/auth/callback"),
        },
      });

      if (error) {
        // Only reached when the redirect could not be STARTED. Once the
        // browser navigates to Google, this function never returns.
        rememberDestination(null);
        throw new AuthError(
          humanError(error, "Could not start sign-in with Google. Please try again."),
        );
      }
    },
    [requireClient],
  );

  const signOut = useCallback(async () => {
    const supabase = getSupabase();
    // Clear locally first. If the network call fails, the person still ends up
    // signed out on this device, which is what they asked for and the safer of
    // the two outcomes.
    tokenRef.current = null;
    setState({ kind: "anonymous" });
    if (supabase) {
      try {
        await supabase.auth.signOut();
      } catch {
        /* already signed out locally; nothing useful to say */
      }
    }
  }, []);

  const requestPasswordReset = useCallback(
    async (email: string) => {
      const supabase = requireClient();
      const { error } = await supabase.auth.resetPasswordForEmail(email.trim(), {
        // Its own path, unlike the other two flows. A reset link is opened
        // from an email, potentially in a different browser, so nothing this
        // tab stored is available to tell /auth/callback where to send them.
        // The destination therefore has to be the URL itself.
        redirectTo: authRedirectUrl("/reset-password"),
      });
      if (error) {
        throw new AuthError(
          humanError(error, "Could not send the reset email. Please try again."),
        );
      }
    },
    [requireClient],
  );

  const updatePassword = useCallback(
    async (password: string) => {
      const supabase = requireClient();
      const { error } = await supabase.auth.updateUser({ password });
      if (error) {
        throw new AuthError(
          humanError(error, "Your password could not be updated. Please try again."),
        );
      }
    },
    [requireClient],
  );

  const user = state.kind === "authenticated" ? state.user : null;

  const value = useMemo<AuthValue>(() => {
    const metadata = (user?.user_metadata ?? {}) as Record<string, unknown>;
    const named = [metadata.full_name, metadata.name].find(
      (v): v is string => typeof v === "string" && v.trim() !== "",
    );
    return {
      state,
      user,
      isAuthenticated: state.kind === "authenticated",
      isLoading: state.kind === "loading",
      displayName: named?.trim() || user?.email || "",
      email: user?.email ?? "",
      signUp,
      signIn,
      signInWithGoogle,
      signOut,
      requestPasswordReset,
      updatePassword,
    };
  }, [
    state,
    user,
    signUp,
    signIn,
    signInWithGoogle,
    signOut,
    requestPasswordReset,
    updatePassword,
  ]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>.");
  return ctx;
}

/* ------------------------------------------------------------------ *
 * Form validation
 * ------------------------------------------------------------------ *
 * Checked in the browser so the reader is told about a typo immediately
 * rather than after a round trip. It is NOT a security boundary: Supabase
 * enforces its own rules, and the backend trusts neither.
 */

/** A deliberately permissive shape check. Only delivery proves an address. */
export function isValidEmail(value: string): boolean {
  const trimmed = value.trim();
  return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(trimmed);
}

/** Supabase's own default minimum. Stated here so the form can say it first. */
export const MIN_PASSWORD_LENGTH = 8;

/**
 * Why a password is unacceptable, or null when it is fine.
 *
 * Length only. A rule demanding one of each character class pushes people
 * towards `Password1!` and away from a long passphrase, which is the weaker of
 * the two - so the form asks for length and says so plainly.
 */
export function passwordProblem(password: string): string | null {
  if (password.length === 0) return "Please choose a password.";
  if (password.length < MIN_PASSWORD_LENGTH) {
    return `Please use at least ${MIN_PASSWORD_LENGTH} characters.`;
  }
  return null;
}

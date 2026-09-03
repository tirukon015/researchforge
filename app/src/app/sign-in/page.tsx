"use client";

/**
 * Sign in with email and password.
 *
 * Deliberately NOT one-time codes. An OTP flow puts the user's inbox in the
 * path of every single sign-in, which is slower, fails when mail is delayed,
 * and is impossible to demonstrate offline - all three matter for a project
 * that gets shown live.
 */

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import {
  AuthCard,
  Field,
  FormError,
  SubmitButton,
} from "@/components/AuthCard";
import { isValidEmail, useAuth } from "@/lib/auth";

/** Where to go after signing in. */
const DEFAULT_DESTINATION = "/dashboard";

/**
 * Only same-site paths are honoured.
 *
 * `?next=` comes from the URL, so it is under the visitor's control. Following
 * it blindly would make this page an open redirect: a link to
 * `/sign-in?next=https://example.invalid` would sign someone in and then hand
 * them to somebody else's site, still trusting the ResearchForge domain they
 * started on. A value that is not a plain in-app path is discarded.
 */
function safeDestination(raw: string | null): string {
  if (!raw) return DEFAULT_DESTINATION;
  // Must start with a single "/" - "//host" and "/\host" are both protocol-
  // relative and would leave the site.
  if (!raw.startsWith("/") || raw.startsWith("//") || raw.startsWith("/\\")) {
    return DEFAULT_DESTINATION;
  }
  // Never bounce back to an account screen; that would be a loop.
  if (raw === "/" || raw.startsWith("/sign-in") || raw.startsWith("/sign-up")) {
    return DEFAULT_DESTINATION;
  }
  return raw;
}

function SignInForm() {
  const { signIn, isAuthenticated, isLoading } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const destination = safeDestination(params.get("next"));

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Someone who is already signed in has no business on this page - most often
  // they arrived by pressing Back after signing in.
  useEffect(() => {
    if (!isLoading && isAuthenticated) router.replace(destination);
  }, [isLoading, isAuthenticated, destination, router]);

  const onSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);

    // Checked here so an obvious typo is caught instantly instead of after a
    // round trip that comes back as "invalid credentials" and sends the reader
    // looking at their password.
    if (!isValidEmail(email)) {
      setError("Please enter a valid email address.");
      return;
    }
    if (password.length === 0) {
      setError("Please enter your password.");
      return;
    }

    setBusy(true);
    try {
      await signIn(email, password);
      router.replace(destination);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Could not sign you in. Please try again.",
      );
      // Left busy=false so the form is usable again immediately. The password
      // is deliberately NOT cleared: the usual cause is a typo, and wiping the
      // field forces a full retype of something they nearly had right.
      setBusy(false);
    }
  };

  return (
    <AuthCard
      title="Welcome back"
      subtitle="Sign in to continue to your ResearchForge account."
      footer={
        <p className="authpage__switch">
          Don&apos;t have an account? <Link href="/sign-up">Create one</Link>
        </p>
      }
    >
      <form onSubmit={onSubmit} noValidate>
        <FormError message={error} />

        <Field
          label="Email address"
          type="email"
          value={email}
          onChange={setEmail}
          placeholder="you@university.edu"
          autoComplete="email"
          autoFocus
        />

        <Field
          label="Password"
          type="password"
          value={password}
          onChange={setPassword}
          placeholder="Enter your password"
          autoComplete="current-password"
        />

        <p className="authpage__forgot">
          <Link href="/forgot-password">Forgot password?</Link>
        </p>

        <SubmitButton busy={busy} busyLabel="Signing in…">
          Sign In
        </SubmitButton>
      </form>

      <p className="authpage__alt">
        New to ResearchForge? <Link href="/sign-up">Create an account</Link>
      </p>
    </AuthCard>
  );
}

export default function SignInPage() {
  // `useSearchParams` requires a Suspense boundary, or the whole route is
  // forced into client-side rendering at build time.
  return (
    <Suspense fallback={<div className="authpage" />}>
      <SignInForm />
    </Suspense>
  );
}

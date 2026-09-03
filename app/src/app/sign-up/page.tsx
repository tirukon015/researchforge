"use client";

/**
 * Create an account.
 *
 * The password is handled by Supabase Auth and never reaches the ResearchForge
 * database. There is no `users` table here, no password column, and nothing to
 * hash - which is exactly the point: the safest way to store a password is to
 * not be the thing storing it.
 *
 * The full name is kept on the Supabase account as user metadata rather than in
 * a profile table. It is one string, it is read back with the account on every
 * request anyway, and a table for it would be a second copy that can fall out
 * of step with the first.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  AuthCard,
  Field,
  FormError,
  FormSuccess,
  SubmitButton,
} from "@/components/AuthCard";
import {
  MIN_PASSWORD_LENGTH,
  isValidEmail,
  passwordProblem,
  useAuth,
} from "@/lib/auth";

export default function SignUpPage() {
  const { signUp, isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [awaitingConfirmation, setAwaitingConfirmation] = useState(false);

  useEffect(() => {
    if (!isLoading && isAuthenticated) router.replace("/dashboard");
  }, [isLoading, isAuthenticated, router]);

  // Live, but only once the reader has actually typed something in the second
  // box. Showing "passwords do not match" against an empty field would scold
  // them for not having finished yet.
  const mismatch =
    confirm.length > 0 && confirm !== password
      ? "Those passwords do not match."
      : null;

  const onSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);

    if (fullName.trim().length === 0) {
      setError("Please enter your name.");
      return;
    }
    if (!isValidEmail(email)) {
      setError("Please enter a valid email address.");
      return;
    }
    const weak = passwordProblem(password);
    if (weak) {
      setError(weak);
      return;
    }
    if (password !== confirm) {
      setError("Those passwords do not match. Please retype them.");
      return;
    }

    setBusy(true);
    try {
      const { needsEmailConfirmation } = await signUp({
        fullName,
        email,
        password,
      });
      if (needsEmailConfirmation) {
        // The account exists but has no session. Sending them to the dashboard
        // would bounce straight back to sign-in with no explanation of why.
        setAwaitingConfirmation(true);
        setBusy(false);
        return;
      }
      router.replace("/dashboard");
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Your account could not be created. Please try again.",
      );
      setBusy(false);
    }
  };

  if (awaitingConfirmation) {
    return (
      <AuthCard
        title="Check your inbox"
        subtitle="Your account has been created, and needs one more step."
        footer={
          <p className="authpage__switch">
            Already confirmed? <Link href="/sign-in">Sign in</Link>
          </p>
        }
      >
        <FormSuccess>
          <p>
            We sent a confirmation link to <strong>{email.trim()}</strong>. Open
            it to activate your account, then sign in.
          </p>
        </FormSuccess>
        <p className="authpage__alt">
          The message can take a minute to arrive, and sometimes lands in spam.
        </p>
        <Link href="/sign-in" className="btn btn--lg authsubmit">
          Go to sign in
        </Link>
      </AuthCard>
    );
  }

  return (
    <AuthCard
      title="Create your account"
      subtitle="Start building a research library that is private to you."
      footer={
        <p className="authpage__switch">
          Already have an account? <Link href="/sign-in">Sign in</Link>
        </p>
      }
    >
      <form onSubmit={onSubmit} noValidate>
        <FormError message={error} />

        <Field
          label="Full name"
          value={fullName}
          onChange={setFullName}
          placeholder="Enter your full name"
          autoComplete="name"
          autoFocus
        />

        <Field
          label="Email address"
          type="email"
          value={email}
          onChange={setEmail}
          placeholder="you@university.edu"
          autoComplete="email"
        />

        <Field
          label="Password"
          type="password"
          value={password}
          onChange={setPassword}
          placeholder="Create a password"
          autoComplete="new-password"
          hint={`At least ${MIN_PASSWORD_LENGTH} characters. A long phrase is stronger than a short, complicated one.`}
        />

        <Field
          label="Confirm password"
          type="password"
          value={confirm}
          onChange={setConfirm}
          placeholder="Type it again"
          autoComplete="new-password"
          problem={mismatch}
        />

        <SubmitButton busy={busy} busyLabel="Creating your account…">
          Create Account
        </SubmitButton>
      </form>

      <p className="authpage__alt">
        Already have an account? <Link href="/sign-in">Sign in</Link>
      </p>
    </AuthCard>
  );
}

"use client";

/**
 * Step one of the password reset: ask Supabase to send the email.
 *
 * WHY THE CONFIRMATION IS THE SAME WHETHER OR NOT THE ACCOUNT EXISTS
 * ------------------------------------------------------------------
 * "No account with that email" would turn this form into a way for anyone to
 * discover which addresses are registered, one guess at a time. So the screen
 * says "if an account exists, we have sent a link" either way. It is slightly
 * less helpful to someone who mistyped their own address, and considerably
 * less helpful to someone enumerating other people's.
 */

import Link from "next/link";
import { useState } from "react";

import {
  AuthCard,
  Field,
  FormError,
  FormSuccess,
  SubmitButton,
} from "@/components/AuthCard";
import { isValidEmail, useAuth } from "@/lib/auth";

export default function ForgotPasswordPage() {
  const { requestPasswordReset } = useAuth();

  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);

  const onSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);

    if (!isValidEmail(email)) {
      setError("Please enter a valid email address.");
      return;
    }

    setBusy(true);
    try {
      await requestPasswordReset(email);
      setSent(true);
    } catch (caught) {
      // A rate limit is worth surfacing - it names a number of seconds the
      // reader can actually wait. Anything else is reported without saying
      // whether the address matched an account.
      setError(
        caught instanceof Error
          ? caught.message
          : "Could not send the reset email. Please try again.",
      );
    } finally {
      setBusy(false);
    }
  };

  if (sent) {
    return (
      <AuthCard
        title="Check your inbox"
        subtitle="If that address has an account, a reset link is on its way."
        footer={
          <p className="authpage__switch">
            Remembered it? <Link href="/sign-in">Sign in</Link>
          </p>
        }
      >
        <FormSuccess>
          <p>
            We sent a password reset link to <strong>{email.trim()}</strong> if
            an account exists for it. The link opens a page where you can set a
            new password.
          </p>
        </FormSuccess>
        <p className="authpage__alt">
          The message can take a minute to arrive, and sometimes lands in spam.
          The link expires, so use it soon.
        </p>
        <button
          type="button"
          className="btn btn--lg authsubmit"
          onClick={() => {
            setSent(false);
            setError(null);
          }}
        >
          Use a different email address
        </button>
      </AuthCard>
    );
  }

  return (
    <AuthCard
      title="Reset your password"
      subtitle="Enter your email address and we will send you a link to set a new one."
      footer={
        <p className="authpage__switch">
          Remembered it? <Link href="/sign-in">Sign in</Link>
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

        <SubmitButton busy={busy} busyLabel="Sending…">
          Send reset link
        </SubmitButton>
      </form>

      <p className="authpage__alt">
        <Link href="/sign-in">Back to sign in</Link>
      </p>
    </AuthCard>
  );
}

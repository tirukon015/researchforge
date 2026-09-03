"use client";

/**
 * Step two of the password reset: set the new password.
 *
 * HOW THIS PAGE KNOWS WHO IT IS TALKING TO
 * ----------------------------------------
 * The link in the reset email carries a token. The Supabase client is
 * configured with `detectSessionInUrl`, so on arrival it reads that token and
 * starts a temporary session for the account. From this page's point of view
 * the person is briefly signed in, and `updateUser({ password })` therefore
 * changes THEIR password and nobody else's.
 *
 * That is also why the three states below matter. Reading the token from the
 * URL is asynchronous, so for a moment after load the honest answer is "we do
 * not know yet". Treating that as "no session" would show "this link is
 * invalid" to someone whose link is perfectly good - the single most confusing
 * way this screen can fail.
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
import { MIN_PASSWORD_LENGTH, passwordProblem, useAuth } from "@/lib/auth";

export default function ResetPasswordPage() {
  const { state, updatePassword, signOut } = useAuth();
  const router = useRouter();

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  // After a successful change, send them to sign in with the new password
  // rather than straight into the app. Signing in once is what proves the new
  // password actually works, which is the whole thing they came here to fix.
  useEffect(() => {
    if (!done) return;
    const timer = setTimeout(() => {
      void signOut().then(() => router.replace("/sign-in"));
    }, 2500);
    return () => clearTimeout(timer);
  }, [done, signOut, router]);

  const mismatch =
    confirm.length > 0 && confirm !== password
      ? "Those passwords do not match."
      : null;

  const onSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);

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
      await updatePassword(password);
      setDone(true);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Your password could not be updated. Please try again.",
      );
    } finally {
      setBusy(false);
    }
  };

  if (state.kind === "loading") {
    return (
      <AuthCard title="Reset your password" subtitle="Checking your reset link…">
        <div className="authgate" role="status" aria-live="polite">
          <span className="authgate__spinner" aria-hidden="true" />
        </div>
      </AuthCard>
    );
  }

  if (state.kind === "anonymous" || state.kind === "unconfigured") {
    // No session came out of the URL: the link was already used, has expired,
    // or was opened without its token (some mail clients strip the fragment).
    return (
      <AuthCard
        title="This link is no longer valid"
        subtitle="Reset links can only be used once, and they expire."
        footer={
          <p className="authpage__switch">
            <Link href="/sign-in">Back to sign in</Link>
          </p>
        }
      >
        <FormError message="Please request a new password reset email and open the link from that message." />
        <Link href="/forgot-password" className="btn btn--primary btn--lg authsubmit">
          Request a new link
        </Link>
      </AuthCard>
    );
  }

  if (done) {
    return (
      <AuthCard
        title="Password updated"
        subtitle="Your new password is ready to use."
      >
        <FormSuccess>
          <p>
            Your password has been changed. Taking you to sign in so you can use
            it&hellip;
          </p>
        </FormSuccess>
        <Link href="/sign-in" className="btn btn--lg authsubmit">
          Go to sign in now
        </Link>
      </AuthCard>
    );
  }

  return (
    <AuthCard
      title="Set a new password"
      subtitle={`Choose a new password for ${state.user.email ?? "your account"}.`}
      footer={
        <p className="authpage__switch">
          <Link href="/sign-in">Back to sign in</Link>
        </p>
      }
    >
      <form onSubmit={onSubmit} noValidate>
        <FormError message={error} />

        <Field
          label="New password"
          type="password"
          value={password}
          onChange={setPassword}
          placeholder="Create a new password"
          autoComplete="new-password"
          hint={`At least ${MIN_PASSWORD_LENGTH} characters.`}
          autoFocus
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

        <SubmitButton busy={busy} busyLabel="Updating…">
          Update Password
        </SubmitButton>
      </form>
    </AuthCard>
  );
}

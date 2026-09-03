"use client";

/**
 * Keeps the private interface out of a signed-out visitor's way.
 *
 * ⚠️ THIS IS NOT THE SECURITY BOUNDARY. Anyone can disable JavaScript or edit
 * the client bundle, so a redirect written here protects nothing. The data is
 * protected twice over on the server: the API answers 401 without a valid
 * token, and Postgres Row Level Security means even a valid token only ever
 * sees its own rows. This component exists so a visitor who is not signed in
 * lands on the sign-in page instead of an application frame that renders four
 * "not signed in" errors at them.
 *
 * THE THREE STATES, AND WHY THE FIRST ONE MATTERS
 * -----------------------------------------------
 * Restoring a stored session is asynchronous. For a moment after every page
 * load the honest answer is "we do not know yet", and treating that as "not
 * signed in" would redirect a signed-in researcher to the sign-in page on every
 * single reload - the bug that makes an app feel like it logs you out at
 * random. So `loading` gets its own branch and shows a quiet placeholder.
 */

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/lib/auth";

export default function AuthGate({ children }: { children: React.ReactNode }) {
  const { state } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (state.kind !== "anonymous") return;
    // `next` carries where they were heading, so signing in returns them there
    // rather than dumping everyone on the dashboard. A bookmarked paper stays
    // a working link through a sign-in.
    const next = encodeURIComponent(pathname);
    router.replace(`/sign-in?next=${next}`);
  }, [state.kind, pathname, router]);

  if (state.kind === "loading") {
    return (
      <div className="authgate" role="status" aria-live="polite">
        <span className="authgate__spinner" aria-hidden="true" />
        <p className="authgate__text">Checking your session…</p>
      </div>
    );
  }

  if (state.kind === "unconfigured") {
    // A deployment with no Supabase settings. Redirecting to a sign-in page
    // that also cannot work would be a loop, so it stops here and says what is
    // actually wrong.
    return (
      <div className="authgate">
        <div className="notice notice--warn">
          <p>
            <strong>Accounts are not set up on this deployment.</strong> The
            research library needs sign-in, and sign-in needs Supabase settings
            the server does not have.
          </p>
        </div>
        <p className="authgate__text">
          <Link href="/">Return to the home page</Link>
        </p>
      </div>
    );
  }

  if (state.kind === "anonymous") {
    // The redirect above is already in flight. Rendering the app for one frame
    // would flash private-looking chrome at someone who is not signed in.
    return (
      <div className="authgate" role="status" aria-live="polite">
        <span className="authgate__spinner" aria-hidden="true" />
        <p className="authgate__text">Taking you to sign in…</p>
      </div>
    );
  }

  return <>{children}</>;
}

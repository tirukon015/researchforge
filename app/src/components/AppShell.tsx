"use client";

/**
 * The page frame, and the boundary between the public site and the private app.
 *
 * There are three kinds of route now, and this decides which frame each gets:
 *
 *   PUBLIC MARKETING  "/"          the landing page. Its own header and
 *                                  footer, because a visitor with no account
 *                                  must not be shown app navigation that
 *                                  every link of would bounce them to sign in.
 *   PUBLIC AUTH       "/sign-in"   the four account screens. No chrome at all;
 *                     "/sign-up"   they are single-purpose pages and a nav bar
 *                     "/forgot-password"   beside a password field is noise.
 *                     "/reset-password"
 *   PRIVATE APP       everything   the existing shell - TopNav, content,
 *                     else        Footer - wrapped in `AuthGate`.
 *
 * WHY THIS IS A LIST RATHER THAN A DIRECTORY MOVE
 * -----------------------------------------------
 * Next.js route groups would express this more idiomatically, and would mean
 * moving every existing page into a new folder. The pages themselves are
 * working, tested, and unrelated to this change; a list of four public paths is
 * a much smaller thing to get wrong than a relocation of the whole app.
 *
 * SECURITY NOTE - READ BEFORE RELYING ON `AuthGate`
 * -------------------------------------------------
 * `AuthGate` hides the private INTERFACE. It is not what protects the DATA:
 * anybody can bypass a client-side redirect. The data is protected by the API
 * refusing an unauthenticated request (401) and, underneath that, by Row Level
 * Security in Postgres, which is what makes a stolen paper id useless. The gate
 * exists so a signed-out visitor sees the sign-in page instead of an app frame
 * full of errors - it is a courtesy, and it is documented as one here so nobody
 * later mistakes it for the boundary.
 */

import { usePathname } from "next/navigation";

import AuthGate from "@/components/AuthGate";
import Footer from "@/components/Footer";
import MarketingShell from "@/components/MarketingShell";
import TopNav from "@/components/TopNav";

/** Reachable with no account. Everything not listed here is private. */
const AUTH_ROUTES = [
  "/sign-in",
  "/sign-up",
  "/forgot-password",
  "/reset-password",
] as const;

export function isAuthRoute(pathname: string): boolean {
  return AUTH_ROUTES.some((route) => pathname === route || pathname.startsWith(`${route}/`));
}

export function isPublicRoute(pathname: string): boolean {
  return pathname === "/" || isAuthRoute(pathname);
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  // The account screens: no navigation, no footer. Each is a single decision.
  if (isAuthRoute(pathname)) {
    return <div className="authshell">{children}</div>;
  }

  // The landing page brings its own header and footer.
  if (pathname === "/") {
    return <MarketingShell>{children}</MarketingShell>;
  }

  return (
    <div className="shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <TopNav />
      <main id="main" className="page">
        <AuthGate>{children}</AuthGate>
      </main>
      <Footer />
    </div>
  );
}

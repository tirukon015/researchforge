/**
 * Redirect construction and return-path validation.
 *
 * WHY THESE TWO FUNCTIONS HAVE TESTS AND MOST OF THE FRONTEND DOES NOT
 * --------------------------------------------------------------------
 * They are small, pure, and each has a failure mode that already happened or
 * would be serious:
 *
 *   `authRedirectUrl`     got production sign-in wrong. A deployed sign-in
 *                         pointed at http://localhost:3000, which is not
 *                         running for anybody but a developer, so Google
 *                         sign-in dead-ended on "Unable to connect".
 *
 *   `isSafeReturnPath`    is the only thing standing between `?next=` and an
 *                         open redirect. It is guarded on the way IN to
 *                         storage and again on the way OUT, and both callers
 *                         rely on this one function being right.
 *
 * NO NETWORK, NO BROWSER. `window` is faked per test, because that is the
 * entire input to the origin-derivation logic.
 */

import { afterEach, describe, expect, it, vi } from "vitest";

import { authRedirectUrl, isSafeReturnPath } from "./supabase";

/** Pretend the page is being served from `origin`. */
function servedFrom(origin: string) {
  vi.stubGlobal("window", { location: { origin } });
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  delete process.env.NEXT_PUBLIC_SITE_URL;
});

describe("authRedirectUrl", () => {
  it("uses the production origin when served from production", () => {
    // THE regression. This returning a localhost URL is what broke Google
    // sign-in in production.
    servedFrom("https://researchforge.rukon.dev");
    expect(authRedirectUrl("/auth/callback")).toBe(
      "https://researchforge.rukon.dev/auth/callback",
    );
  });

  it("uses localhost when served from a dev server", () => {
    servedFrom("http://localhost:3000");
    expect(authRedirectUrl("/auth/callback")).toBe("http://localhost:3000/auth/callback");
  });

  it("never returns a localhost URL from a production origin", () => {
    servedFrom("https://researchforge.rukon.dev");
    for (const path of ["/auth/callback", "/reset-password", "/dashboard"]) {
      expect(authRedirectUrl(path)).not.toContain("localhost");
      expect(authRedirectUrl(path)).not.toContain("127.0.0.1");
    }
  });

  it("works on a preview deployment with no configuration at all", () => {
    // The reason the origin is derived rather than configured: nobody sets a
    // variable for a URL that is generated per deployment.
    servedFrom("https://researchforge-abc123-rpoms.vercel.app");
    expect(authRedirectUrl("/auth/callback")).toBe(
      "https://researchforge-abc123-rpoms.vercel.app/auth/callback",
    );
  });

  it("builds the password-reset URL on the same origin", () => {
    servedFrom("https://researchforge.rukon.dev");
    expect(authRedirectUrl("/reset-password")).toBe(
      "https://researchforge.rukon.dev/reset-password",
    );
  });

  it("lets NEXT_PUBLIC_SITE_URL override the origin", () => {
    // For a deployment behind a proxy whose public hostname differs from what
    // the browser reports.
    servedFrom("http://internal-host:8080");
    vi.stubEnv("NEXT_PUBLIC_SITE_URL", "https://researchforge.rukon.dev");
    expect(authRedirectUrl("/auth/callback")).toBe(
      "https://researchforge.rukon.dev/auth/callback",
    );
  });

  it("ignores an empty override rather than producing a relative URL", () => {
    servedFrom("https://researchforge.rukon.dev");
    vi.stubEnv("NEXT_PUBLIC_SITE_URL", "   ");
    expect(authRedirectUrl("/auth/callback")).toBe(
      "https://researchforge.rukon.dev/auth/callback",
    );
  });

  it("does not double the slash when the origin has a trailing one", () => {
    // "//auth/callback" would not match an allow-list entry, and Supabase
    // would silently fall back to the Site URL - the failure this whole file
    // exists to prevent.
    vi.stubEnv("NEXT_PUBLIC_SITE_URL", "https://researchforge.rukon.dev/");
    servedFrom("https://researchforge.rukon.dev");
    expect(authRedirectUrl("/auth/callback")).toBe(
      "https://researchforge.rukon.dev/auth/callback",
    );
  });

  it("tolerates a path given without a leading slash", () => {
    servedFrom("https://researchforge.rukon.dev");
    expect(authRedirectUrl("auth/callback")).toBe(
      "https://researchforge.rukon.dev/auth/callback",
    );
  });
});

describe("isSafeReturnPath", () => {
  it("accepts ordinary in-app paths", () => {
    for (const path of [
      "/dashboard",
      "/papers",
      "/papers/abc-123",
      "/literature-review",
      "/settings",
      "/workspace?tab=summary",
    ]) {
      expect(isSafeReturnPath(path)).toBe(true);
    }
  });

  it("rejects another origin outright", () => {
    expect(isSafeReturnPath("https://evil.example/steal")).toBe(false);
    expect(isSafeReturnPath("http://evil.example")).toBe(false);
  });

  it("rejects a protocol-relative URL", () => {
    // "//evil.example" LOOKS like a path and is read by browsers as a HOST.
    // This is the classic open-redirect bypass.
    expect(isSafeReturnPath("//evil.example")).toBe(false);
    expect(isSafeReturnPath("//evil.example/dashboard")).toBe(false);
  });

  it("rejects the backslash variant some browsers normalise", () => {
    expect(isSafeReturnPath("/\\evil.example")).toBe(false);
  });

  it("rejects a scheme that is not a navigation", () => {
    expect(isSafeReturnPath("javascript:alert(1)")).toBe(false);
    expect(isSafeReturnPath("data:text/html,x")).toBe(false);
  });

  it("rejects nothing at all", () => {
    expect(isSafeReturnPath(null)).toBe(false);
    expect(isSafeReturnPath(undefined)).toBe(false);
    expect(isSafeReturnPath("")).toBe(false);
  });

  it("rejects a bare relative path", () => {
    // Not dangerous, but not something to navigate to either: it would resolve
    // against whatever page happens to be current.
    expect(isSafeReturnPath("dashboard")).toBe(false);
  });
});

/**
 * The Supabase browser client. Authentication only.
 *
 * WHAT THIS IS USED FOR, AND WHAT IT IS NOT
 * -----------------------------------------
 * This client signs people in, signs them out, and keeps the session fresh.
 * It NEVER reads or writes research data. Papers, analyses and literature
 * reviews go through the FastAPI backend, exactly as they did before accounts
 * existed, so all the validation, error vocabulary and grounding rules stay in
 * one place instead of being reimplemented in the browser.
 *
 * What the browser does carry is the access token the backend needs to know
 * who is asking. `src/lib/api.ts` reads it from here and puts it on every
 * request.
 *
 * WHY THESE KEYS ARE SAFE TO PUBLISH
 * ----------------------------------
 * Both values below are NEXT_PUBLIC_, which means they are compiled into the
 * JavaScript bundle and visible to anyone who opens the page. That is correct
 * for these two and only these two:
 *
 *   NEXT_PUBLIC_SUPABASE_URL       the address of the project. Public.
 *   NEXT_PUBLIC_SUPABASE_ANON_KEY  the *publishable* key. It grants nothing on
 *                                  its own: every table has Row Level Security
 *                                  enabled, so a request carrying only this key
 *                                  reads zero rows.
 *
 * The service-role key, which DOES bypass Row Level Security, must never
 * appear in this file, in any NEXT_PUBLIC_ variable, or anywhere else the
 * browser can reach. It lives on the server and nowhere else.
 *
 * WHICH OAUTH FLOW, AND WHY IT IS SET EXPLICITLY
 * ----------------------------------------------
 * `flowType` is pinned to `pkce`. It matters, and the default is the other one.
 *
 * Plain `@supabase/supabase-js` defaults to `implicit`, which returns the
 * session by putting the **access token and refresh token in the URL** of the
 * page the provider redirects back to. That is how a sign-in ends up looking
 * like `/?access_token=eyJ...`. Tokens in a URL are written to browser
 * history, can be sent in a `Referer` header to any third-party asset the
 * landing page loads, and are visible to anyone glancing at the address bar.
 *
 * PKCE returns a single-use `?code=` instead, which is worthless without the
 * verifier held in this browser's own storage. Nothing secret is ever in a URL.
 *
 * (`@supabase/ssr` defaults to pkce; `supabase-js` does not. Relying on the
 * default here would silently depend on which package a future refactor uses.)
 *
 * WHY THE CLIENT IS BUILT LAZILY
 * ------------------------------
 * Calling createClient at module scope would run during the production build,
 * where the variables may legitimately be absent, and crash the build of a
 * public landing page that does not need Supabase at all. Building on first
 * use means a misconfigured deployment still serves the marketing pages and
 * says something honest on the sign-in page, instead of serving nothing.
 */

import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL?.trim() ?? "";
const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY?.trim() ?? "";

/**
 * Whether accounts can work in this build.
 *
 * Read by the sign-in and sign-up pages so they can say "accounts are not
 * configured on this deployment" rather than presenting a form whose every
 * submission fails with something that reads like a wrong password.
 */
export const isAuthConfigured = Boolean(url && anonKey);

let client: SupabaseClient | null = null;

/**
 * The shared client, or `null` when the deployment has no Supabase settings.
 *
 * Returning null rather than throwing is deliberate: the caller has to decide
 * what to show, and every caller here has a sensible answer. A throw would take
 * down whichever page happened to touch it first.
 */
export function getSupabase(): SupabaseClient | null {
  if (!isAuthConfigured) return null;
  if (client === null) {
    client = createClient(url, anonKey, {
      auth: {
        // See the note above. NEVER rely on the default here.
        flowType: "pkce",
        // Keep the session in browser storage and refresh it before it
        // expires, so a researcher part-way through reading an analysis is not
        // signed out mid-sentence.
        persistSession: true,
        autoRefreshToken: true,
        // Read the tokens Supabase appends to the URL after a password-reset
        // or confirmation link. Without this the reset page would load with no
        // session and every new password would be refused.
        detectSessionInUrl: true,
      },
    });
  }
  return client;
}

/* ------------------------------------------------------------------ *
 * Where Supabase should send people back to
 * ------------------------------------------------------------------ */

/**
 * Absolute URL for an auth redirect, on the origin actually being used.
 *
 * WHY IT IS DERIVED FROM THE RUNNING ORIGIN
 * -----------------------------------------
 * `window.location.origin` is `http://localhost:3000` in development and
 * `https://researchforge.rukon.dev` in production, with no variable anyone has
 * to remember to change and nothing to get wrong on a preview URL. Hard-coding
 * production here would break local development; hard-coding localhost is how
 * a deployed sign-in ends up pointing at a machine that is not running.
 *
 * `NEXT_PUBLIC_SITE_URL` overrides it, for the one case the origin cannot
 * cover: a deployment behind a proxy that serves a different public hostname
 * than the browser sees. It is deliberately unset by default.
 *
 * ⚠️ WHATEVER THIS RETURNS MUST BE IN THE SUPABASE REDIRECT ALLOW-LIST.
 * Supabase does not reject an unlisted redirect when the flow starts - it
 * accepts it, and then silently substitutes the project's **Site URL** on the
 * way back. The visible symptom is landing on the Site URL's ROOT rather than
 * the path that was asked for, which is exactly what a missing allow-list
 * entry looks like from the outside.
 */
export function authRedirectUrl(path: string): string {
  const configured = process.env.NEXT_PUBLIC_SITE_URL?.trim();
  const base = (
    configured || (typeof window !== "undefined" ? window.location.origin : "")
  ).replace(/\/+$/, "");
  return `${base}${path.startsWith("/") ? path : `/${path}`}`;
}

/**
 * Whether `path` is safe to send somebody to after signing in.
 *
 * Only a same-site absolute path qualifies. This is what stops
 * `/sign-in?next=https://evil.example` from turning the sign-in page into an
 * open redirect that lends the ResearchForge domain's credibility to somebody
 * else's site.
 *
 * Rejected, and each for its own reason:
 *   ""                 nothing to go to
 *   "https://x/"       another origin outright
 *   "//evil.example"   protocol-relative: a browser reads this as a HOST
 *   "/\evil.example"   some browsers normalise the backslashes to "//"
 *   "javascript:..."   not a navigation at all
 */
export function isSafeReturnPath(path: string | null | undefined): boolean {
  if (!path || typeof path !== "string") return false;
  if (!path.startsWith("/")) return false;
  if (path.startsWith("//")) return false;
  if (path.startsWith("/\\")) return false;
  return true;
}

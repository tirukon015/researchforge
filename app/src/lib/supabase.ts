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

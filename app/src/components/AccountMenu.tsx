"use client";

/**
 * Who is signed in, and the way out.
 *
 * Sits in the existing header beside the theme toggle, in the space that was
 * already there for controls - deliberately, so adding accounts did not mean
 * redesigning a working navigation bar.
 *
 * A disclosure button rather than a hover menu: hover menus are unreachable by
 * touch and awkward by keyboard, and this one contains the only irreversible
 * action in the header.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/lib/auth";

/** First letters of the name, for the avatar circle. */
function initials(name: string, email: string): string {
  const source = name.trim() || email.trim();
  if (!source) return "?";
  const words = source.split(/[\s@._-]+/).filter(Boolean);
  if (words.length === 0) return source[0]!.toUpperCase();
  if (words.length === 1) return words[0]!.slice(0, 2).toUpperCase();
  return (words[0]![0]! + words[1]![0]!).toUpperCase();
}

export default function AccountMenu() {
  const { isAuthenticated, displayName, email, signOut } = useAuth();
  const [open, setOpen] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const holder = useRef<HTMLDivElement>(null);
  const router = useRouter();

  const close = useCallback(() => setOpen(false), []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    const onClick = (e: MouseEvent) => {
      if (!holder.current?.contains(e.target as Node)) close();
    };
    window.addEventListener("keydown", onKey);
    // `mousedown`, not `click`: a click that starts inside and ends outside
    // would otherwise close the panel underneath the pointer.
    window.addEventListener("mousedown", onClick);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("mousedown", onClick);
    };
  }, [open, close]);

  const handleSignOut = useCallback(async () => {
    setSigningOut(true);
    await signOut();
    // `replace`, not `push`: the browser Back button must not return to a page
    // that is now behind a sign-in redirect.
    router.replace("/");
  }, [signOut, router]);

  // Nothing to show when nobody is signed in. The route guard will already be
  // sending them to the sign-in page.
  if (!isAuthenticated) return null;

  return (
    <div className="account" ref={holder}>
      <button
        className="account__trigger"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls="account-panel"
        aria-label={`Account: ${displayName || email}`}
      >
        <span className="account__avatar" aria-hidden="true">
          {initials(displayName, email)}
        </span>
        {/* Hidden below the breakpoint by CSS; the avatar carries it there. */}
        <span className="account__name">{displayName || email}</span>
      </button>

      <div id="account-panel" className="account__panel" hidden={!open}>
        <div className="account__identity">
          <p className="account__identityname">{displayName || "Signed in"}</p>
          {/* The email is shown in full and allowed to wrap. Truncating the
              one field that identifies which account you are in defeats the
              purpose of showing it. */}
          <p className="account__identitymail">{email}</p>
        </div>
        <button
          className="btn btn--danger account__signout"
          onClick={handleSignOut}
          disabled={signingOut}
        >
          {signingOut ? "Signing out…" : "Sign out"}
        </button>
      </div>
    </div>
  );
}

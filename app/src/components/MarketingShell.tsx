"use client";

/**
 * Header and footer for the public landing page.
 *
 * Separate from `TopNav` because the two navigate different things. TopNav
 * lists the five places a signed-in researcher moves between; this lists the
 * sections of one marketing page plus the two ways in. Showing a visitor
 * "My Papers" would be an invitation to a sign-in redirect.
 *
 * It uses the SAME brand mark, type scale, colour tokens and button classes as
 * the application, so a person arriving from the landing page recognises the
 * dashboard as the same product rather than a different one.
 *
 * A signed-in reader gets "Go to dashboard" instead of the sign-in pair. They
 * already have an account; offering to create one would be noise, and the one
 * thing they want from this page is the way back in.
 */

import Image from "next/image";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { IconClose, IconMenu } from "@/components/Icons";
import ThemeToggle from "@/components/ThemeToggle";
import { useAuth } from "@/lib/auth";

/** In-page sections, in the order the page presents them. */
const SECTIONS = [
  { href: "#features", label: "Features" },
  { href: "#how-it-works", label: "How It Works" },
  { href: "#about", label: "About" },
] as const;

export default function MarketingShell({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  const [open, setOpen] = useState(false);
  const close = useCallback(() => setOpen(false), []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, close]);

  // Rendered as a shared fragment so the desktop bar and the mobile panel can
  // never drift apart - the commonest way a responsive header ends up offering
  // two different sets of actions.
  const actions = isLoading ? (
    // A placeholder, not a guess. Rendering "Sign In" while we are still
    // restoring the session would flash the wrong action at someone who is
    // already signed in.
    <span className="marketingnav__placeholder" aria-hidden="true" />
  ) : isAuthenticated ? (
    <Link href="/dashboard" className="btn btn--primary">
      Go to dashboard
    </Link>
  ) : (
    <>
      <Link href="/sign-in" className="btn">
        Sign In
      </Link>
      <Link href="/sign-up" className="btn btn--primary">
        Get Started
      </Link>
    </>
  );

  return (
    <div className="shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>

      <header className="topnav marketingnav">
        <div className="topnav__inner">
          <Link href="/" className="topnav__brand" aria-label="ResearchForge home">
            {/* The same mark, at the same ratio, as the application header. */}
            <Image
              src="/brand/researchforge-mark-192.png"
              alt=""
              width={38}
              height={30}
              className="brandmark"
              priority
            />
            <span className="topnav__wordmark">
              <span className="topnav__name">ResearchForge</span>
              <span className="topnav__tagline">AI Research Assistant</span>
            </span>
          </Link>

          <nav className="topnav__links" aria-label="Sections">
            {SECTIONS.map(({ href, label }) => (
              <a key={href} href={href} className="navlink">
                {label}
              </a>
            ))}
          </nav>

          <div className="topnav__actions">
            <ThemeToggle />
            <div className="marketingnav__cta">{actions}</div>
            <button
              className="iconbtn topnav__menu"
              onClick={() => setOpen((v) => !v)}
              aria-expanded={open}
              aria-controls="marketing-nav"
              aria-label={open ? "Close menu" : "Open menu"}
            >
              {open ? <IconClose /> : <IconMenu />}
            </button>
          </div>
        </div>

        {/* Hidden with the `hidden` attribute rather than unmounted, so the
            disclosure relationship stays valid for assistive technology. */}
        <nav
          id="marketing-nav"
          className="topnav__mobile"
          aria-label="Sections, compact"
          hidden={!open}
        >
          {SECTIONS.map(({ href, label }) => (
            <a key={href} href={href} className="navlink navlink--block" onClick={close}>
              {label}
            </a>
          ))}
          <div className="marketingnav__mobilecta">{actions}</div>
        </nav>
      </header>

      <main id="main" className="marketingmain">
        {children}
      </main>

      <footer className="sitefooter">
        <div className="sitefooter__inner">
          <div>
            <p className="sitefooter__name">ResearchForge</p>
            <p className="sitefooter__tagline">Explore, Analyze, Innovate</p>
          </div>
          <p className="sitefooter__note">
            Analysis is grounded in the uploaded paper only. Where a paper does
            not support a section, ResearchForge says so rather than inventing
            content.
          </p>
          <nav className="sitefooter__links" aria-label="Footer">
            <a href="#features">Features</a>
            <a href="#how-it-works">How It Works</a>
            <Link href="/sign-in">Sign In</Link>
          </nav>
        </div>
      </footer>
    </div>
  );
}

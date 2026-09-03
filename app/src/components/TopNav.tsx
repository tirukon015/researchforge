"use client";

/**
 * Top navigation. There is no sidebar at any width.
 *
 * A horizontal header is the right shape for this product: the five
 * destinations are peers a researcher moves between, not steps in a wizard,
 * and a header gives the full page width back to what people came to read,
 * which is dense academic text.
 *
 * The header is sticky because the theme control and the route switcher are
 * wanted from anywhere in a long analysis, and it is thin enough that keeping
 * it costs little.
 *
 * Below 900px the links collapse into a disclosure panel under the header. It
 * pushes content down rather than sliding over it: an overlay drawer is a
 * sidebar wearing a different hat, and this product does not want one.
 */

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import AccountMenu from "@/components/AccountMenu";
import ThemeToggle from "@/components/ThemeToggle";
import { IconClose, IconMenu } from "@/components/Icons";

const NAV = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/papers", label: "My Papers" },
  { href: "/literature-review", label: "Literature Review" },
  { href: "/workspace", label: "Workspace" },
  { href: "/settings", label: "Settings" },
] as const;

function isActive(pathname: string, href: string): boolean {
  // Every destination matches its subtree, so /papers/abc keeps "My Papers"
  // marked. No exact-match special case is needed now that the dashboard lives
  // at /dashboard rather than at "/" - "/" is the public landing page, and this
  // header is never rendered there.
  return pathname === href || pathname.startsWith(`${href}/`);
}

export default function TopNav() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  const close = useCallback(() => setOpen(false), []);

  // Navigating on a small screen must dismiss the panel, or the new page
  // opens with the menu still covering it.
  useEffect(() => close(), [pathname, close]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, close]);

  return (
    <header className="topnav">
      <div className="topnav__inner">
        <Link href="/dashboard" className="topnav__brand" aria-label="ResearchForge dashboard">
          {/* The official transparent mark, pre-sized. width and height carry
              the source's real 1420:1108 ratio rather than a square guess, so
              the browser reserves exactly the right box and the artwork is
              never stretched to fit it. */}
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

        <nav className="topnav__links" aria-label="Main">
          {NAV.map(({ href, label }) => {
            const active = isActive(pathname, href);
            return (
              <Link
                key={href}
                href={href}
                className={`navlink${active ? " navlink--active" : ""}`}
                aria-current={active ? "page" : undefined}
              >
                {label}
              </Link>
            );
          })}
        </nav>

        <div className="topnav__actions">
          <ThemeToggle />
          <AccountMenu />
          <button
            className="iconbtn topnav__menu"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            aria-controls="mobile-nav"
            aria-label={open ? "Close menu" : "Open menu"}
          >
            {open ? <IconClose /> : <IconMenu />}
          </button>
        </div>
      </div>

      {/* Rendered always, hidden with the `hidden` attribute rather than
          unmounted, so the disclosure relationship stays valid for assistive
          technology and the panel is not re-created on every toggle. */}
      <nav
        id="mobile-nav"
        className="topnav__mobile"
        aria-label="Main, compact"
        hidden={!open}
      >
        {NAV.map(({ href, label }) => {
          const active = isActive(pathname, href);
          return (
            <Link
              key={href}
              href={href}
              className={`navlink navlink--block${active ? " navlink--active" : ""}`}
              aria-current={active ? "page" : undefined}
            >
              {label}
            </Link>
          );
        })}
      </nav>
    </header>
  );
}

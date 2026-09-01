"use client";

/**
 * Persistent navigation shell.
 *
 * Desktop keeps the sidebar in view because the four areas are peers a
 * researcher moves between, not a wizard. Below 900px it becomes an off-canvas
 * drawer behind a menu button: on a tablet a fixed 248px rail would eat a
 * quarter of the reading width, which is the opposite of useful on the one
 * screen size where reading room is scarce.
 *
 * The active item is marked by fill, left rule, and weight together, so it
 * reads without relying on colour alone.
 */

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import {
  IconClose,
  IconDashboard,
  IconMenu,
  IconPapers,
  IconReview,
  IconSettings,
} from "@/components/Icons";

const NAV = [
  { href: "/", label: "Dashboard", Icon: IconDashboard },
  { href: "/papers", label: "My Papers", Icon: IconPapers },
  { href: "/literature-review", label: "Literature Review", Icon: IconReview },
  { href: "/settings", label: "Settings", Icon: IconSettings },
] as const;

function isActive(pathname: string, href: string): boolean {
  // "/" must match exactly, or it would light up on every route.
  return href === "/" ? pathname === "/" : pathname.startsWith(href);
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  const close = useCallback(() => setOpen(false), []);

  // Navigating on mobile must dismiss the drawer, or the new page opens
  // hidden behind it.
  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const currentLabel =
    NAV.find((item) => isActive(pathname, item.href))?.label ?? "ResearchForge";

  return (
    <div className="shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>

      {/* Mobile bar. Hidden at desktop widths by CSS, not by a JS breakpoint,
          so the first paint is already correct. */}
      <header className="topbar">
        <button
          className="iconbtn"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          aria-controls="app-sidebar"
          aria-label={open ? "Close navigation" : "Open navigation"}
        >
          {open ? <IconClose /> : <IconMenu />}
        </button>
        <Image
          src="/brand/researchforge-mark.png"
          alt=""
          width={28}
          height={28}
          className="brandmark"
          style={{ width: 28, height: 28 }}
        />
        <span className="topbar__title">{currentLabel}</span>
      </header>

      <button
        className={`scrim${open ? " scrim--on" : ""}`}
        onClick={close}
        aria-label="Close navigation"
        tabIndex={open ? 0 : -1}
      />

      <nav
        id="app-sidebar"
        className={`sidebar${open ? " sidebar--open" : ""}`}
        aria-label="Main"
      >
        <Link href="/" className="sidebar__brand">
          {/* The transparent mark sits on the navy rail; object-fit keeps its
              aspect ratio at any box size rather than stretching it. */}
          <Image
            src="/brand/researchforge-mark.png"
            alt="ResearchForge"
            width={34}
            height={34}
            className="brandmark"
            priority
            style={{ width: 34, height: 34 }}
          />
          <span>
            <span className="sidebar__name">ResearchForge</span>
            <span className="sidebar__sub">AI Research Assistant</span>
          </span>
        </Link>

        <div className="sidebar__nav">
          <span className="sidebar__label">Workspace</span>
          {NAV.map(({ href, label, Icon }) => {
            const active = isActive(pathname, href);
            return (
              <Link
                key={href}
                href={href}
                className={`navlink${active ? " navlink--active" : ""}`}
                aria-current={active ? "page" : undefined}
              >
                <Icon size={17} />
                {label}
              </Link>
            );
          })}
        </div>

        <div className="sidebar__foot">
          Grounded in the uploaded paper only.
        </div>
      </nav>

      <div className="workspace">
        <main id="main" className="page">
          {children}
        </main>
      </div>
    </div>
  );
}

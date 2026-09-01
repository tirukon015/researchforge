import type { Metadata, Viewport } from "next";

import AppShell from "@/components/AppShell";
import { SessionProvider } from "@/lib/session";

import "./globals.css";

export const metadata: Metadata = {
  // The template gives every route its own title without repeating the brand
  // by hand on each page.
  title: {
    default: "ResearchForge: AI Research Assistant",
    template: "%s · ResearchForge",
  },
  description:
    "AI Research Assistant. Upload papers, generate summaries, " +
    "identify research gaps, and produce literature reviews.",
  applicationName: "ResearchForge",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        {/* The session holder wraps the shell so a result survives navigation
            between Dashboard and Literature Review. It is in-memory only -
            see src/lib/session.tsx for why it is deliberately not persisted. */}
        <SessionProvider>
          <AppShell>{children}</AppShell>
        </SessionProvider>
      </body>
    </html>
  );
}

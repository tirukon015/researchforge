import type { Metadata, Viewport } from "next";

import AppShell from "@/components/AppShell";
import { SelectionProvider } from "@/lib/library";
import { SessionProvider } from "@/lib/session";
import { THEME_INIT_SCRIPT, ThemeProvider } from "@/lib/theme";

import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "ResearchForge: AI Research Assistant",
    template: "%s · ResearchForge",
  },
  description:
    "Upload academic papers, analyse them, identify research gaps, and build " +
    "literature-review insights.",
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
    <html lang="en" data-theme="light" suppressHydrationWarning>
      <head>
        {/* Applies the stored theme before first paint. Without it a dark-mode
            reader sees a white flash on every navigation. It is inert if
            storage is blocked, and the markup ships with the light default so
            the server and client agree. */}
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body>
        <ThemeProvider>
          {/* Holds the analysis being worked on, so it survives navigation
              between routes. Saved papers come from the backend, not here. */}
          <SessionProvider>
            {/* Which papers are ticked for a cross-paper review. Selection
                happens on Workspace and My Papers, generating happens on
                Literature Review, so it is shared rather than local. */}
            <SelectionProvider>
              <AppShell>{children}</AppShell>
            </SelectionProvider>
          </SessionProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}

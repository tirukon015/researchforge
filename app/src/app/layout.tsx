import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ResearchForge",
  description:
    "AI Research Paper Assistant — upload papers, generate summaries, " +
    "identify research gaps, and produce literature reviews.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

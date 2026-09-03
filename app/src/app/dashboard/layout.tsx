import type { Metadata } from "next";

// The page itself is a client component (it reads the session), and a client
// component cannot export metadata - so the segment layout carries the title,
// the same way every other route in this app does.
export const metadata: Metadata = {
  title: "Dashboard",
  description:
    "Upload a research paper, analyse it, and see what is in your ResearchForge library.",
};

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return children;
}

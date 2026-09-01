import type { Metadata } from "next";

// The page is a client component, and a client component cannot export
// metadata, so the segment layout carries the title. The paper's own title is
// not known at build time, so a generic name is used rather than pretending to
// know which paper is open.
export const metadata: Metadata = {
  title: "Paper",
  description:
    "A saved paper with its summary, research gaps and literature review.",
};

export default function PaperLayout({ children }: { children: React.ReactNode }) {
  return children;
}

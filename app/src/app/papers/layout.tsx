import type { Metadata } from "next";

// The page itself is a client component (it reads the session), and a client
// component cannot export metadata - so the segment layout carries the title.
export const metadata: Metadata = {
  title: "My Papers",
  description:
    "Papers you have analysed with ResearchForge. Saving them between visits requires persistent storage.",
};

export default function PapersLayout({ children }: { children: React.ReactNode }) {
  return children;
}

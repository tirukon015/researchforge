import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Workspace",
  description: "Select saved papers to compare and review together.",
};

export default function WorkspaceLayout({ children }: { children: React.ReactNode }) {
  return children;
}

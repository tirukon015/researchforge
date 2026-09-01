import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Settings",
  description: "ResearchForge application and service information.",
};

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  return children;
}

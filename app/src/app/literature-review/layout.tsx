import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Literature Review",
  description:
    "A literature review generated from the prior work discussed within the paper you analysed.",
};

export default function LiteratureReviewLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}

import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Vanadium · Analyze",
  description:
    "Paste two video URLs and get a full AI-powered breakdown — metadata, transcripts, visual analysis, and evidence-backed chat.",
};

export default function AnalyzeLayout({ children }: { children: React.ReactNode }) {
  return children;
}

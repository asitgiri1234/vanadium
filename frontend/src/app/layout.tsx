import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Vanadium · AI Content Intelligence",
  description:
    "Compare two social videos and understand why one outperforms the other — with evidence-backed AI analysis.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}

import type { Metadata } from "next";
import { JetBrains_Mono, Space_Grotesk } from "next/font/google";
import { ClientShell } from "@/components/client-shell";
import "./globals.css";

const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-space",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

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
      <body
        className={`${spaceGrotesk.variable} ${jetbrainsMono.variable} min-h-screen font-sans antialiased`}
      >
        <div className="ambient-grid" aria-hidden />
        <div className="scanline" aria-hidden />
        <ClientShell />
        <div className="relative z-10">{children}</div>
      </body>
    </html>
  );
}

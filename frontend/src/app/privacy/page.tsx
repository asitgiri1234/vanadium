import Link from "next/link";
import { SiteFooter, SiteHeader } from "@/components/landing";

export const metadata = {
  title: "Privacy Policy — Vanadium",
  description: "How Vanadium collects, uses, and stores your data.",
};

export default function PrivacyPage() {
  return (
    <>
      <SiteHeader />

      <main className="mx-auto max-w-3xl px-4 py-14 md:px-6 md:py-20">
        <p className="sci-fi-label mb-3">Legal</p>
        <h1 className="text-3xl font-bold tracking-tight md:text-4xl">Privacy Policy</h1>
        <p className="mt-4 text-sm text-muted-foreground">
          Last updated: May 2026
        </p>

        <div className="prose prose-invert mt-10 max-w-none space-y-8 text-sm leading-relaxed text-muted-foreground">
          <section className="glass-panel rounded-xl p-6">
            <h2 className="mb-3 text-lg font-semibold text-foreground">What we collect</h2>
            <p>
              When you use Vanadium, you provide public video URLs (YouTube or Instagram Reels).
              We process metadata from those videos (views, likes, titles, creator names),
              transcripts, and visual frame analysis derived from the content you submit.
            </p>
          </section>

          <section className="glass-panel rounded-xl p-6">
            <h2 className="mb-3 text-lg font-semibold text-foreground">How we use it</h2>
            <p>
              Your video URLs and extracted content are used to generate comparisons, insights,
              and chat responses within the Vanadium workspace. Analyses may be stored server-side
              so your session persists across page refreshes.
            </p>
          </section>

          <section className="glass-panel rounded-xl p-6">
            <h2 className="mb-3 text-lg font-semibold text-foreground">Third-party sharing</h2>
            <p>
              Transcripts and analysis context are sent to our configured LLM provider
              (Groq or OpenAI) solely to generate comparisons and chat answers. We do not sell
              your data to third parties or use it for advertising.
            </p>
          </section>

          <section className="glass-panel rounded-xl p-6">
            <h2 className="mb-3 text-lg font-semibold text-foreground">Your rights</h2>
            <p>
              If you have questions about your data or want an analysis removed, contact us at{" "}
              <a href="mailto:hello@vanadium.app" className="text-primary hover:underline">
                hello@vanadium.app
              </a>
              .
            </p>
          </section>
        </div>

        <div className="mt-10">
          <Link
            href="/"
            className="text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            ← Back to home
          </Link>
        </div>
      </main>

      <SiteFooter />
    </>
  );
}

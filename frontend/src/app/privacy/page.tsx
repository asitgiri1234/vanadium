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
        <h1 className="text-3xl font-bold tracking-tight md:text-4xl">Privacy Policy</h1>

        <div className="glass-panel mt-10 rounded-xl p-6 text-sm leading-relaxed text-muted-foreground">
          <p>
            Vanadium processes video URLs you submit. Transcripts and metadata are sent to
            Groq or OpenAI to generate comparisons. No data is sold or shared with third
            parties. Analyses are stored server-side to persist your session.
          </p>
        </div>
      </main>

      <SiteFooter />
    </>
  );
}

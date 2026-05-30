"use client";

import { useState } from "react";
import { Atom } from "lucide-react";
import { UrlForm } from "@/components/url-form";
import { VideoCard } from "@/components/video-card";
import { TranscriptPanel } from "@/components/transcript-panel";
import { ingest } from "@/lib/api";
import type { AnalysisSnapshot } from "@/lib/types";

export default function Home() {
  const [snapshot, setSnapshot] = useState<AnalysisSnapshot | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleAnalyze = async (a: string, b: string) => {
    setLoading(true);
    setError(null);
    setSnapshot(null);
    try {
      const result = await ingest(a, b);
      setSnapshot(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ingestion failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      <header className="mb-8 flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/15">
          <Atom className="h-6 w-6 text-primary" />
        </div>
        <div>
          <h1 className="text-xl font-bold tracking-tight">Vanadium</h1>
          <p className="text-xs text-muted-foreground">
            AI content intelligence for creators
          </p>
        </div>
      </header>

      <div className="space-y-6">
        <UrlForm onAnalyze={handleAnalyze} loading={loading} error={error} />

        {snapshot && (
          <>
            <section className="grid gap-6 md:grid-cols-2">
              <VideoCard video={snapshot.videos.A} />
              <VideoCard video={snapshot.videos.B} />
            </section>
            <TranscriptPanel analysisId={snapshot.analysis_id} />
          </>
        )}

        {!snapshot && !loading && (
          <div className="rounded-lg border border-dashed border-border py-16 text-center text-muted-foreground">
            <p className="text-sm">
              Paste two video URLs above and hit{" "}
              <span className="text-foreground">Analyze</span> to fetch their metadata.
            </p>
          </div>
        )}
      </div>
    </main>
  );
}

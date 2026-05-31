"use client";

import { useState } from "react";
import Link from "next/link";
import { Activity, ArrowLeft, Zap } from "lucide-react";
import { UrlForm } from "@/components/url-form";
import { VideoCard } from "@/components/video-card";
import { TranscriptPanel } from "@/components/transcript-panel";
import { VisualPanel } from "@/components/visual-panel";
import { ComparisonBar } from "@/components/comparison-bar";
import { ChatPanel } from "@/components/chat-panel";
import { SectionLabel, SiteFooter, ToolHeader } from "@/components/landing";
import { ingest } from "@/lib/api";
import type { AnalysisSnapshot } from "@/lib/types";

export default function AnalyzePage() {
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
    <>
      <ToolHeader />

      <main className="mx-auto max-w-6xl px-4 py-10 md:px-6">
        <div className="mb-8">
          <Link
            href="/"
            className="inline-flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to home
          </Link>
          <div className="mt-6 text-center md:text-left">
            <p className="sci-fi-label mb-2">Analysis Workspace</p>
            <h1 className="text-2xl font-bold tracking-tight md:text-3xl">
              Paste two videos. Get the full breakdown.
            </h1>
            <p className="mt-2 max-w-xl text-sm text-muted-foreground">
              Drop a YouTube link and an Instagram Reel — Vanadium ingests both, runs the
              comparison, and unlocks evidence-backed chat.
            </p>
          </div>
        </div>

        <UrlForm onAnalyze={handleAnalyze} loading={loading} error={error} />

        {snapshot && (
          <div className="mt-10 space-y-8">
            <SectionLabel icon={Zap} label="Video Intelligence" />
            <section className="grid gap-6 md:grid-cols-2">
              <VideoCard video={snapshot.videos.A} />
              <VideoCard video={snapshot.videos.B} />
            </section>

            <SectionLabel icon={Activity} label="Performance Analysis" />
            <ComparisonBar
              analysisId={snapshot.analysis_id}
              videoA={snapshot.videos.A}
              videoB={snapshot.videos.B}
              comparison={snapshot.comparison}
            />

            <SectionLabel icon={Activity} label="Evidence Layers" />
            <TranscriptPanel analysisId={snapshot.analysis_id} />
            <VisualPanel analysisId={snapshot.analysis_id} />
            <ChatPanel
              key={snapshot.analysis_id}
              analysisId={snapshot.analysis_id}
              videoA={snapshot.videos.A}
              videoB={snapshot.videos.B}
            />
          </div>
        )}

        {!snapshot && !loading && (
          <div className="empty-state-panel mt-10">
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full border border-primary/30 bg-primary/10 shadow-glow-sm">
              <Zap className="h-6 w-6 text-primary" />
            </div>
            <p className="sci-fi-label mb-2">Awaiting Input</p>
            <p className="text-sm text-muted-foreground">
              Enter two video URLs above and hit{" "}
              <span className="text-gradient font-semibold">Analyze</span> to begin.
            </p>
          </div>
        )}
      </main>

      <SiteFooter />
    </>
  );
}

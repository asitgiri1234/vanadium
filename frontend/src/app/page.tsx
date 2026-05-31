"use client";

import { useState } from "react";
import Image from "next/image";
import { Activity, Zap } from "lucide-react";
import { UrlForm } from "@/components/url-form";
import { VideoCard } from "@/components/video-card";
import { TranscriptPanel } from "@/components/transcript-panel";
import { VisualPanel } from "@/components/visual-panel";
import { ComparisonBar } from "@/components/comparison-bar";
import { ChatPanel } from "@/components/chat-panel";
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
    <main className="mx-auto max-w-6xl px-4 py-10 md:px-6">
      <header className="mb-12 flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-5">
          <div className="relative">
            <div className="absolute -inset-2 rounded-2xl bg-gradient-to-br from-primary/30 to-accent/20 blur-xl animate-pulse-glow" />
            <Image
              src="/logo.png"
              alt="Vanadium"
              width={64}
              height={64}
              priority
              className="relative rounded-2xl shadow-glow ring-1 ring-white/10"
            />
          </div>
          <div>
            <p className="sci-fi-label mb-1">Content Intelligence System</p>
            <h1 className="text-gradient text-3xl font-bold tracking-tight md:text-4xl">
              Vanadium
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              AI-powered video comparison for creators
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3 self-start rounded-full border border-border/60 bg-card/50 px-4 py-2 backdrop-blur-md sm:self-auto">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-60" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-accent shadow-glow-cyan" />
          </span>
          <span className="font-mono text-xs text-muted-foreground">
            NEURAL ENGINE <span className="text-accent">ONLINE</span>
          </span>
        </div>
      </header>

      <div className="space-y-8">
        <UrlForm onAnalyze={handleAnalyze} loading={loading} error={error} />

        {snapshot && (
          <>
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
            <ChatPanel key={snapshot.analysis_id} analysisId={snapshot.analysis_id} />
          </>
        )}

        {!snapshot && !loading && (
          <div className="empty-state-panel">
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full border border-primary/30 bg-primary/10 shadow-glow-sm">
              <Zap className="h-6 w-6 text-primary" />
            </div>
            <p className="sci-fi-label mb-2">Awaiting Input</p>
            <p className="text-sm text-muted-foreground">
              Paste two video URLs above and initiate{" "}
              <span className="text-gradient font-semibold">Analyze</span> to begin
              deep content intelligence.
            </p>
          </div>
        )}
      </div>
    </main>
  );
}

function SectionLabel({
  icon: Icon,
  label,
}: {
  icon: React.ElementType;
  label: string;
}) {
  return (
    <div className="flex items-center gap-3">
      <div className="flex h-7 w-7 items-center justify-center rounded-md border border-border/60 bg-muted/30">
        <Icon className="h-3.5 w-3.5 text-accent" />
      </div>
      <span className="sci-fi-label">{label}</span>
      <div className="h-px flex-1 bg-gradient-to-r from-border/80 to-transparent" />
    </div>
  );
}

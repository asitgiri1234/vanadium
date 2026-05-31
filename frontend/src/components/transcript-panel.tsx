"use client";

import { useEffect, useState } from "react";
import { FileText, Loader2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getTranscript } from "@/lib/api";
import type { TranscriptResponse, VideoSlot } from "@/lib/types";
import { cn } from "@/lib/utils";

export function TranscriptPanel({ analysisId }: { analysisId: string }) {
  const [data, setData] = useState<TranscriptResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [active, setActive] = useState<VideoSlot>("A");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setData(null);
    setActive("A");
    getTranscript(analysisId)
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load transcript.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [analysisId]);

  const current = data?.transcripts[active];

  return (
    <Card>
      <CardHeader className="border-b border-border/50 pb-4">
        <div className="flex items-center justify-between gap-4">
          <CardTitle className="flex items-center gap-2 text-base">
            <FileText className="h-4 w-4 text-primary" />
            Transcripts
          </CardTitle>
          <div className="flex gap-1 rounded-lg border border-border/50 bg-muted/30 p-1 backdrop-blur-sm">
            {(["A", "B"] as VideoSlot[]).map((slot) => (
              <button
                key={slot}
                onClick={() => setActive(slot)}
                className={cn(
                  "rounded-md px-3 py-1 font-mono text-xs font-semibold transition-all duration-300",
                  active === slot
                    ? "nav-pill-active"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                VID_{slot}
              </button>
            ))}
          </div>
        </div>
      </CardHeader>

      <CardContent className="pt-5">
        {loading && (
          <div className="flex items-center justify-center gap-2 py-12 font-mono text-xs text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin text-accent" /> LOADING_TRANSCRIPT…
          </div>
        )}

        {error && !loading && (
          <p className="py-8 text-center text-sm text-red-400">{error}</p>
        )}

        {!loading && !error && current && (
          <TranscriptBody transcript={current} whisperEnabled={!!data?.whisper_enabled} />
        )}
      </CardContent>
    </Card>
  );
}

function TranscriptBody({
  transcript,
  whisperEnabled,
}: {
  transcript: NonNullable<TranscriptResponse["transcripts"][VideoSlot]>;
  whisperEnabled: boolean;
}) {
  if (!transcript.available || transcript.segments.length === 0) {
    const isInstagram = transcript.platform === "instagram";
    let note: string | null = null;
    if (isInstagram && !whisperEnabled) {
      note = "Enable Whisper (ENABLE_WHISPER=true) to transcribe Instagram reels.";
    } else if (isInstagram && whisperEnabled) {
      note =
        "No speech detected — this reel may be music-only or have no voiceover.";
    } else {
      note = "No captions/transcript are available for this video.";
    }
    return (
      <div className="py-10 text-center text-sm text-muted-foreground">
        <p className="sci-fi-label mb-2">No Signal</p>
        <p>No transcript available for this video.</p>
        <p className="mt-2 font-mono text-[10px] text-[hsl(var(--warning))]">{note}</p>
      </div>
    );
  }

  return (
    <div className="scroll-thin max-h-[420px] space-y-1 overflow-y-auto pr-2">
      {transcript.segments.map((line, i) => (
        <div
          key={i}
          className="group flex gap-4 rounded-lg px-2 py-2 text-sm leading-relaxed transition-colors hover:bg-muted/25"
        >
          <span className="shrink-0 select-none font-mono text-[11px] font-medium text-accent/90">
            [{line.timestamp}]
          </span>
          <span className="text-foreground/90 selection:bg-accent/25">{line.text}</span>
        </div>
      ))}
    </div>
  );
}

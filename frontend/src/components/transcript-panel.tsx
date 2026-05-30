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
      <CardHeader className="border-b border-border pb-4">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-base">
            <FileText className="h-4 w-4 text-primary" />
            Transcripts
          </CardTitle>
          <div className="flex gap-1 rounded-md bg-muted/50 p-1">
            {(["A", "B"] as VideoSlot[]).map((slot) => (
              <button
                key={slot}
                onClick={() => setActive(slot)}
                className={cn(
                  "rounded px-3 py-1 text-sm font-medium transition-colors",
                  active === slot
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                Video {slot}
              </button>
            ))}
          </div>
        </div>
      </CardHeader>

      <CardContent className="pt-4">
        {loading && (
          <div className="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading transcripts…
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
        <p>No transcript available for this video.</p>
        <p className="mt-1 text-xs text-[hsl(var(--warning))]">{note}</p>
      </div>
    );
  }

  return (
    <div className="scroll-thin max-h-[420px] space-y-2 overflow-y-auto pr-2">
      {transcript.segments.map((line, i) => (
        <div key={i} className="flex gap-3 text-sm leading-relaxed">
          <span className="shrink-0 select-none font-mono text-xs text-primary/80">
            {line.timestamp}
          </span>
          <span className="text-foreground/90">{line.text}</span>
        </div>
      ))}
    </div>
  );
}

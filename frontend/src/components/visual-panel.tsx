"use client";

import { useEffect, useState } from "react";
import { Eye, Loader2, ScanText, Sparkles } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getVisual } from "@/lib/api";
import type { VideoVisual, VisualResponse, VideoSlot } from "@/lib/types";
import { cn } from "@/lib/utils";

export function VisualPanel({ analysisId }: { analysisId: string }) {
  const [data, setData] = useState<VisualResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [active, setActive] = useState<VideoSlot>("A");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setData(null);
    setActive("A");
    getVisual(analysisId)
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch((e) => {
        if (!cancelled)
          setError(e instanceof Error ? e.message : "Failed to load visual analysis.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [analysisId]);

  const current = data?.visuals[active];

  return (
    <Card>
      <CardHeader className="border-b border-border/50 pb-4">
        <div className="flex items-center justify-between gap-4">
          <CardTitle className="flex items-center gap-2 text-base">
            <Eye className="h-4 w-4 text-primary" />
            Visual Analysis
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
        <p className="mt-2 font-mono text-[10px] leading-relaxed text-muted-foreground/80">
          Vision AI · scene description + on-screen text extraction
        </p>
      </CardHeader>

      <CardContent className="pt-5">
        {loading && (
          <div className="flex items-center justify-center gap-2 py-12 font-mono text-xs text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin text-accent" /> LOADING_VISUAL…
          </div>
        )}

        {error && !loading && (
          <p className="py-8 text-center text-sm text-red-400">{error}</p>
        )}

        {!loading && !error && data && current && (
          <VisualBody
            visual={current}
            enabled={data.enabled}
            visionEnabled={data.vision_enabled}
          />
        )}
      </CardContent>
    </Card>
  );
}

function VisualBody({
  visual,
  enabled,
  visionEnabled,
}: {
  visual: VideoVisual;
  enabled: boolean;
  visionEnabled: boolean;
}) {
  if (!enabled) {
    return (
      <div className="py-10 text-center text-sm text-muted-foreground">
        <p className="sci-fi-label mb-2">Module Offline</p>
        <p>Visual analysis is turned off.</p>
        <p className="mt-2 font-mono text-[10px] text-[hsl(var(--warning))]">
          Set ENABLE_VISUAL=true in backend/.env
        </p>
      </div>
    );
  }

  if (!visionEnabled) {
    return (
      <div className="py-10 text-center text-sm text-muted-foreground">
        <p className="sci-fi-label mb-2">Vision Unavailable</p>
        <p>LLM not configured for vision.</p>
        <p className="mt-2 font-mono text-[10px] text-[hsl(var(--warning))]">
          Set GROQ_API_KEY or OPENAI_API_KEY in backend/.env
        </p>
      </div>
    );
  }

  if (!visual.available) {
    return (
      <div className="py-10 text-center text-sm text-muted-foreground">
        <p className="sci-fi-label mb-2">No Visual Data</p>
        <p>No visual analysis could be extracted for this video.</p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div>
        <div className="mb-2 flex items-center gap-2 sci-fi-label">
          <Sparkles className="h-3.5 w-3.5 text-primary" />
          Scene Description
        </div>
        {visual.visual_summary ? (
          <p className="rounded-xl border border-border/50 bg-muted/20 p-4 text-sm leading-relaxed text-foreground/90 backdrop-blur-sm selection:bg-accent/25">
            {visual.visual_summary}
          </p>
        ) : (
          <p className="font-mono text-xs text-muted-foreground">NULL_RETURN</p>
        )}
      </div>

      {visual.on_screen_text && (
        <div>
          <div className="mb-2 flex items-center gap-2 sci-fi-label">
            <ScanText className="h-3.5 w-3.5 text-accent" />
            On-Screen Text
          </div>
          <p className="rounded-xl border border-accent/20 bg-accent/5 p-4 font-mono text-sm leading-relaxed text-foreground/90 selection:bg-accent/30">
            {visual.on_screen_text}
          </p>
        </div>
      )}
    </div>
  );
}

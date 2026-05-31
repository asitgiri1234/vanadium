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
      <CardHeader className="border-b border-border pb-4">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-base">
            <Eye className="h-4 w-4 text-primary" />
            Visual analysis
          </CardTitle>
          <div className="flex gap-1 rounded-md bg-muted/50 p-1">
            {(["A", "B"] as VideoSlot[]).map((slot) => (
              <button
                key={slot}
                onClick={() => setActive(slot)}
                className={cn(
                  "rounded px-3 py-1 text-sm font-medium transition-colors",
                  active === slot
                    ? "gradient-bg text-white"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                Video {slot}
              </button>
            ))}
          </div>
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          AI vision describes the scene and reads on-screen text — useful when
          there&apos;s little or no speech.
        </p>
      </CardHeader>

      <CardContent className="pt-4">
        {loading && (
          <div className="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading visual analysis…
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
        <p>Visual analysis is turned off.</p>
        <p className="mt-1 text-xs text-[hsl(var(--warning))]">
          Set ENABLE_VISUAL=true in the backend. YouTube videos with captions skip
          this step automatically.
        </p>
      </div>
    );
  }

  if (!visual.available) {
    return (
      <div className="py-10 text-center text-sm text-muted-foreground">
        <p>No visual analysis for this video.</p>
        <p className="mt-1 text-xs text-muted-foreground">
          YouTube videos with captions use the transcript instead.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div>
        <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          <Sparkles className="h-3.5 w-3.5 text-primary" />
          Scene description
        </div>
        {visual.visual_summary ? (
          <p className="rounded-lg border border-border bg-muted/30 p-3 text-sm leading-relaxed text-foreground/90">
            {visual.visual_summary}
          </p>
        ) : (
          <p className="text-xs text-muted-foreground">No scene description available.</p>
        )}
      </div>

      {(visual.on_screen_text || visual.frames.length > 0) && (
        <div>
          <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            <ScanText className="h-3.5 w-3.5 text-primary" />
            On-screen text
          </div>
          {visual.on_screen_text ? (
            <p className="rounded-lg border border-border bg-muted/30 p-3 text-sm leading-relaxed text-foreground/90">
              {visual.on_screen_text}
            </p>
          ) : (
            <div className="scroll-thin max-h-[240px] space-y-2 overflow-y-auto pr-2">
              {visual.frames.map((frame, i) => (
                <div key={i} className="flex gap-3 text-sm leading-relaxed">
                  <span className="shrink-0 select-none font-mono text-xs text-primary/80">
                    {frame.timestamp}
                  </span>
                  <span className="text-foreground/90">{frame.ocr_text}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {!visionEnabled && !visual.on_screen_text && visual.frames.length === 0 && (
        <p className="text-xs text-[hsl(var(--warning))]">
          Add an OpenAI API key for accurate scene and text analysis.
        </p>
      )}
    </div>
  );
}

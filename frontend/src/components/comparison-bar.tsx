"use client";

import { useEffect, useState } from "react";
import { Lightbulb, Loader2, Sparkles, Trophy } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { getAnalysis } from "@/lib/api";
import type { ComparisonInsights, VideoMetadata } from "@/lib/types";
import { cn } from "@/lib/utils";
import { determinePerformanceWinner, performanceLeadLabel } from "@/lib/chat-suggestions";

export function ComparisonBar({
  analysisId,
  videoA,
  videoB,
  comparison: initialComparison,
}: {
  analysisId: string;
  videoA: VideoMetadata;
  videoB: VideoMetadata;
  comparison: ComparisonInsights;
}) {
  const [comparison, setComparison] = useState(initialComparison);

  useEffect(() => {
    setComparison(initialComparison);
  }, [initialComparison]);

  useEffect(() => {
    if (!comparison.ai_pending) return;

    let cancelled = false;
    const poll = async () => {
      try {
        const snap = await getAnalysis(analysisId);
        if (!cancelled) setComparison(snap.comparison);
      } catch {
        /* keep polling */
      }
    };

    poll();
    const id = setInterval(poll, 2000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [analysisId, comparison.ai_pending]);

  // Use absolute percentage scale (0-100), not winner-normalized width.
  const widthA = `${Math.max(0, Math.min(100, videoA.engagement_rate))}%`;
  const widthB = `${Math.max(0, Math.min(100, videoB.engagement_rate))}%`;
  const performanceWinner = determinePerformanceWinner(videoA, videoB);

  return (
    <Card>
      <CardHeader className="border-b border-border/50 pb-4">
        <CardTitle className="flex flex-wrap items-center gap-2 text-base">
          <Sparkles className="h-4 w-4 text-primary shadow-glow-sm" />
          <span>Comparison Insights</span>
          {performanceWinner && (
            <Badge
              variant="outline"
              className="ml-auto gap-1 border-violet-500/40 bg-violet-500/10 text-violet-200"
            >
              <Trophy className="h-3 w-3" />
              Video {performanceWinner}{" "}
              {performanceLeadLabel(videoA, videoB, performanceWinner)}
            </Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6 pt-5">
        <div className="space-y-5">
          <Bar
            label="Video A"
            value={videoA.engagement_rate}
            width={widthA}
            hasViews={videoA.views > 0}
            accent="from-violet-500 via-violet-400 to-fuchsia-400"
            glow="violet"
          />
          <Bar
            label="Video B"
            value={videoB.engagement_rate}
            width={widthB}
            hasViews={videoB.views > 0}
            accent="from-cyan-500 via-cyan-400 to-teal-400"
            glow="cyan"
          />
        </div>

        {comparison.headline_insights.length > 0 && (
          <ul className="space-y-2 border-t border-border/50 pt-5 text-sm text-muted-foreground">
            {comparison.headline_insights.map((insight, i) => (
              <li key={i} className="flex gap-3 rounded-lg border border-border/40 bg-muted/15 px-3 py-2">
                <span className="font-mono text-xs text-accent">0{i + 1}</span>
                <span className="text-foreground/85">{insight}</span>
              </li>
            ))}
          </ul>
        )}

        {comparison.ai_pending && !comparison.strategist_summary && !comparison.ai_error && (
          <div className="flex items-center gap-3 rounded-lg border border-primary/20 bg-primary/5 px-4 py-3 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin text-primary" />
            <span className="font-mono text-xs">AI_STRATEGIST :: generating narrative…</span>
          </div>
        )}

        {comparison.ai_error && (
          <div className="border-t border-border/50 pt-5">
            <p className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-300 backdrop-blur-sm">
              AI comparison failed: {comparison.ai_error}
            </p>
            <p className="mt-2 font-mono text-[10px] text-muted-foreground">
              AI comparison is temporarily unavailable. Try again in a moment or contact support.
            </p>
          </div>
        )}

        {comparison.strategist_summary && (
          <div className="border-t border-border/50 pt-5">
            <p className="sci-fi-label mb-3">AI Strategist Summary</p>
            <p className="rounded-xl border border-border/50 bg-muted/20 p-4 text-sm leading-relaxed text-foreground/90 backdrop-blur-sm selection:bg-accent/30">
              {comparison.strategist_summary}
            </p>
          </div>
        )}

        {comparison.recommendations.length > 0 && (
          <div className="border-t border-border/50 pt-5">
            <p className="mb-3 flex items-center gap-2 sci-fi-label">
              <Lightbulb className="h-3.5 w-3.5 text-primary" />
              Recommendations
            </p>
            <ul className="space-y-2">
              {comparison.recommendations.map((rec, i) => (
                <li
                  key={i}
                  className="flex gap-3 rounded-lg border border-border/50 bg-muted/15 px-4 py-3 text-sm text-foreground/90 transition-colors hover:border-primary/25"
                >
                  <span className="text-gradient shrink-0 font-mono text-xs font-bold">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <span>{rec}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function Bar({
  label,
  value,
  width,
  hasViews,
  accent,
  glow,
}: {
  label: string;
  value: number;
  width: string;
  hasViews: boolean;
  accent: string;
  glow: "violet" | "cyan";
}) {
  const glowClass =
    glow === "violet"
      ? "shadow-[0_0_20px_hsl(276_91%_66%/0.5)]"
      : "shadow-[0_0_20px_hsl(187_92%_53%/0.5)]";

  return (
    <div>
      <div className="mb-2 flex justify-between font-mono text-xs">
        <span className="font-semibold tracking-wide text-foreground/90">{label}</span>
        <span className={cn(hasViews ? "text-gradient font-bold" : "text-muted-foreground")}>
          {hasViews ? `${value}%` : "N/A"}
        </span>
      </div>
      <div className="bar-track">
        <div
          className={cn("bar-fill bg-gradient-to-r", accent, hasViews && glowClass)}
          style={{ width: hasViews ? width : "0%" }}
        />
      </div>
    </div>
  );
}

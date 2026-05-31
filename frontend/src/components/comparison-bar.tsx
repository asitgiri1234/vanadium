"use client";

import { useEffect, useState } from "react";
import { Lightbulb, Loader2, Sparkles, Trophy } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { getAnalysis } from "@/lib/api";
import type { ComparisonInsights, VideoMetadata } from "@/lib/types";
import { cn } from "@/lib/utils";

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

  const max = Math.max(videoA.engagement_rate, videoB.engagement_rate, 0.01);
  const widthA = `${(videoA.engagement_rate / max) * 100}%`;
  const widthB = `${(videoB.engagement_rate / max) * 100}%`;
  const hasViews = videoA.views > 0 && videoB.views > 0;

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex flex-wrap items-center gap-2 text-base">
          <Sparkles className="h-4 w-4 text-primary" />
          Comparison insights
          {comparison.winner && hasViews && (
            <Badge variant="outline" className="ml-auto gap-1 border-violet-500/40 text-violet-300">
              <Trophy className="h-3 w-3" />
              Video {comparison.winner} leads by {comparison.engagement_delta} pts
            </Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="space-y-4">
          <Bar
            label="Video A"
            value={videoA.engagement_rate}
            width={widthA}
            hasViews={videoA.views > 0}
            accent="from-violet-500 to-violet-400"
          />
          <Bar
            label="Video B"
            value={videoB.engagement_rate}
            width={widthB}
            hasViews={videoB.views > 0}
            accent="from-cyan-500 to-cyan-400"
          />
        </div>

        {comparison.headline_insights.length > 0 && (
          <ul className="space-y-1.5 border-t border-border pt-4 text-sm text-muted-foreground">
            {comparison.headline_insights.map((insight, i) => (
              <li key={i} className="flex gap-2">
                <span className="text-primary">→</span>
                <span>{insight}</span>
              </li>
            ))}
          </ul>
        )}

        {comparison.ai_pending && !comparison.strategist_summary && (
          <div className="flex items-center gap-2 border-t border-border pt-4 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin text-primary" />
            Generating AI strategist summary…
          </div>
        )}

        {comparison.strategist_summary && (
          <div className="border-t border-border pt-4">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              AI strategist summary
            </p>
            <p className="rounded-lg border border-border bg-muted/30 p-4 text-sm leading-relaxed text-foreground/90">
              {comparison.strategist_summary}
            </p>
          </div>
        )}

        {comparison.recommendations.length > 0 && (
          <div className="border-t border-border pt-4">
            <p className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              <Lightbulb className="h-3.5 w-3.5 text-primary" />
              Recommendations
            </p>
            <ul className="space-y-2">
              {comparison.recommendations.map((rec, i) => (
                <li
                  key={i}
                  className="flex gap-2 rounded-lg border border-border/60 bg-muted/20 px-3 py-2 text-sm text-foreground/90"
                >
                  <span className="text-gradient shrink-0 font-semibold">{i + 1}.</span>
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
}: {
  label: string;
  value: number;
  width: string;
  hasViews: boolean;
  accent: string;
}) {
  return (
    <div>
      <div className="mb-1 flex justify-between text-xs">
        <span className="font-medium">{label}</span>
        <span className={cn(hasViews ? "text-gradient font-semibold" : "text-muted-foreground")}>
          {hasViews ? `${value}%` : "N/A"}
        </span>
      </div>
      <div className="h-3 w-full overflow-hidden rounded-full bg-muted">
        <div
          className={cn("h-full rounded-full bg-gradient-to-r transition-all", accent)}
          style={{ width: hasViews ? width : "0%" }}
        />
      </div>
    </div>
  );
}

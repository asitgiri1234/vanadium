"use client";

import { Sparkles } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ComparisonInsights, VideoMetadata } from "@/lib/types";

export function ComparisonBar({
  videoA,
  videoB,
  comparison,
}: {
  videoA: VideoMetadata;
  videoB: VideoMetadata;
  comparison: ComparisonInsights;
}) {
  const max = Math.max(videoA.engagement_rate, videoB.engagement_rate, 1);
  const widthA = `${(videoA.engagement_rate / max) * 100}%`;
  const widthB = `${(videoB.engagement_rate / max) * 100}%`;

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <Sparkles className="h-4 w-4 text-primary" />
          Engagement comparison
          {comparison.winner && (
            <span className="ml-auto text-sm font-normal text-muted-foreground">
              Video {comparison.winner} leads by {comparison.engagement_delta} pts
            </span>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <Bar label="Video A" value={videoA.engagement_rate} width={widthA} color="bg-sky-500" />
        <Bar label="Video B" value={videoB.engagement_rate} width={widthB} color="bg-violet-500" />

        {comparison.headline_insights.length > 0 && (
          <ul className="mt-4 space-y-1.5 border-t border-border pt-4 text-sm text-muted-foreground">
            {comparison.headline_insights.map((insight, i) => (
              <li key={i} className="flex gap-2">
                <span className="text-primary">→</span>
                <span>{insight}</span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function Bar({
  label,
  value,
  width,
  color,
}: {
  label: string;
  value: number;
  width: string;
  color: string;
}) {
  return (
    <div>
      <div className="mb-1 flex justify-between text-xs">
        <span className="font-medium">{label}</span>
        <span className="text-muted-foreground">{value}%</span>
      </div>
      <div className="h-3 w-full overflow-hidden rounded-full bg-muted">
        <div className={`h-full rounded-full ${color} transition-all`} style={{ width }} />
      </div>
    </div>
  );
}

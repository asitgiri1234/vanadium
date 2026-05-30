"use client";

import { Calendar, Clock, Eye, Heart, MessageCircle, Users } from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { thumbnailSrc } from "@/lib/api";
import type { VideoMetadata } from "@/lib/types";
import { cn, formatNumber } from "@/lib/utils";

function formatDuration(seconds: number): string {
  if (!seconds) return "—";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function Metric({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ElementType;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-center gap-2 rounded-md bg-muted/40 px-3 py-2">
      <Icon className="h-4 w-4 text-muted-foreground" />
      <div className="leading-tight">
        <div className="text-sm font-semibold">{value}</div>
        <div className="text-[11px] text-muted-foreground">{label}</div>
      </div>
    </div>
  );
}

export function VideoCard({ video }: { video: VideoMetadata }) {
  const thumb = thumbnailSrc(video.thumbnail, video.platform);
  const viewsKnown = video.views > 0;
  const accentRing =
    video.video_id === "A" ? "ring-violet-500/40" : "ring-cyan-500/40";
  return (
    <Card className={cn("overflow-hidden ring-1", accentRing)}>
      <div className="relative aspect-video w-full bg-muted">
        {thumb ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={thumb}
            alt={video.title}
            className="h-full w-full object-cover"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-sm text-muted-foreground">
            No thumbnail
          </div>
        )}
        <div className="absolute left-3 top-3 flex items-center gap-2">
          <Badge variant="outline" className="bg-background/70 backdrop-blur">
            Video {video.video_id}
          </Badge>
          <Badge variant="muted" className="bg-background/70 capitalize backdrop-blur">
            {video.platform}
          </Badge>
        </div>
      </div>

      <CardHeader className="pb-3">
        <h3 className="line-clamp-2 text-base font-semibold">{video.title}</h3>
        <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
          <Users className="h-3.5 w-3.5" />
          <span>{video.creator}</span>
          {video.follower_count > 0 && (
            <span className="text-xs">· {formatNumber(video.follower_count)} followers</span>
          )}
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        <div className="rounded-lg border border-border bg-muted/30 p-4 text-center">
          <div className="text-4xl font-extrabold">
            {viewsKnown ? (
              <span className="text-gradient">{video.engagement_rate}%</span>
            ) : (
              <span className="text-muted-foreground">N/A</span>
            )}
          </div>
          <div className="text-xs uppercase tracking-wide text-muted-foreground">
            Engagement rate
          </div>
          {!viewsKnown && (
            <div className="mt-1 text-[11px] text-[hsl(var(--warning))]">
              View count not reported by {video.platform}
            </div>
          )}
        </div>

        <div className="grid grid-cols-3 gap-2">
          <Metric icon={Eye} label="Views" value={viewsKnown ? formatNumber(video.views) : "—"} />
          <Metric icon={Heart} label="Likes" value={formatNumber(video.likes)} />
          <Metric icon={MessageCircle} label="Comments" value={formatNumber(video.comments)} />
        </div>

        <div className="grid grid-cols-2 gap-2">
          <Metric icon={Clock} label="Duration" value={formatDuration(video.duration_seconds)} />
          <Metric
            icon={Calendar}
            label="Uploaded"
            value={video.upload_date || "—"}
          />
        </div>

        {video.hashtags.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {video.hashtags.slice(0, 10).map((tag) => (
              <Badge key={tag} variant="muted">
                {tag}
              </Badge>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

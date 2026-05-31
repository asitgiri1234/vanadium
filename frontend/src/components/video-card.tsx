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
    <div className="metric-tile flex items-center gap-2">
      <Icon className="h-4 w-4 text-accent/70" />
      <div className="leading-tight">
        <div className="text-sm font-semibold">{value}</div>
        <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
          {label}
        </div>
      </div>
    </div>
  );
}

export function VideoCard({ video }: { video: VideoMetadata }) {
  const thumb = thumbnailSrc(video.thumbnail, video.platform);
  const viewsKnown = video.views > 0;
  const isA = video.video_id === "A";
  const accentGlow = isA
    ? "shadow-[0_0_40px_-12px_hsl(276_91%_66%/0.35)] ring-violet-500/30"
    : "shadow-[0_0_40px_-12px_hsl(187_92%_53%/0.35)] ring-cyan-500/30";

  return (
    <Card className={cn("overflow-hidden ring-1 transition-shadow duration-500 hover:shadow-glow-sm", accentGlow)}>
      <div className="relative aspect-video w-full bg-muted/50">
        {thumb ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={thumb}
            alt={video.title}
            className="h-full w-full object-cover"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center font-mono text-xs text-muted-foreground">
            NO SIGNAL
          </div>
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-card via-transparent to-transparent opacity-80" />
        <div className="absolute left-3 top-3 flex items-center gap-2">
          <Badge variant="outline" className="border-white/10 bg-background/60 backdrop-blur-md">
            Video {video.video_id}
          </Badge>
          <Badge variant="muted" className="bg-background/60 capitalize backdrop-blur-md">
            {video.platform}
          </Badge>
        </div>
      </div>

      <CardHeader className="pb-3">
        <h3 className="line-clamp-2 text-base font-semibold leading-snug">{video.title}</h3>
        <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
          <Users className="h-3.5 w-3.5 text-primary/70" />
          <span>{video.creator}</span>
          {video.follower_count > 0 && (
            <span className="font-mono text-xs">
              · {formatNumber(video.follower_count)} followers
            </span>
          )}
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        <div className="engagement-orb">
          <div className="text-4xl font-extrabold tracking-tight">
            {viewsKnown ? (
              <span className="text-gradient">{video.engagement_rate}%</span>
            ) : (
              <span className="text-muted-foreground">N/A</span>
            )}
          </div>
          <div className="sci-fi-label mt-1">Engagement Rate</div>
          {!viewsKnown && (
            <div className="mt-2 font-mono text-[10px] text-[hsl(var(--warning))]">
              Views unavailable · {video.platform}
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
          <Metric icon={Calendar} label="Uploaded" value={video.upload_date || "—"} />
        </div>

        {video.hashtags.length > 0 && (
          <div className="flex flex-wrap gap-1.5 border-t border-border/40 pt-3">
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

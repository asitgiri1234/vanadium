"use client";

import { Eye, Heart, MessageCircle, Users, Trophy } from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { VideoMetadata, VideoSlot } from "@/lib/types";
import { cn, formatNumber } from "@/lib/utils";

const SLOT_ACCENT: Record<VideoSlot, string> = {
  A: "from-sky-500/20 ring-sky-500/40",
  B: "from-violet-500/20 ring-violet-500/40",
};

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

export function VideoCard({
  video,
  isWinner,
}: {
  video: VideoMetadata;
  isWinner: boolean;
}) {
  return (
    <Card className={cn("overflow-hidden ring-1 ring-border", isWinner && `ring-2 ${SLOT_ACCENT[video.video_id]}`)}>
      <div className="relative aspect-video w-full bg-muted">
        {video.thumbnail ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={video.thumbnail}
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
        {isWinner && (
          <div className="absolute right-3 top-3">
            <Badge variant="success" className="gap-1">
              <Trophy className="h-3 w-3" /> Top performer
            </Badge>
          </div>
        )}
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
          <div className="text-3xl font-bold text-primary">
            {video.engagement_rate}%
          </div>
          <div className="text-xs uppercase tracking-wide text-muted-foreground">
            Engagement rate
          </div>
        </div>

        <div className="grid grid-cols-3 gap-2">
          <Metric icon={Eye} label="Views" value={formatNumber(video.views)} />
          <Metric icon={Heart} label="Likes" value={formatNumber(video.likes)} />
          <Metric icon={MessageCircle} label="Comments" value={formatNumber(video.comments)} />
        </div>

        {video.hashtags.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {video.hashtags.slice(0, 8).map((tag) => (
              <Badge key={tag} variant="muted">
                {tag}
              </Badge>
            ))}
          </div>
        )}

        {!video.transcript_available && (
          <p className="text-xs text-[hsl(var(--warning))]">
            No transcript available — analysis uses metadata only.
          </p>
        )}
      </CardContent>
    </Card>
  );
}

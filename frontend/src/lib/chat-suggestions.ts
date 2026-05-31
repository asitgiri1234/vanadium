import type { VideoMetadata, VideoSlot } from "./types";

/** Same rules as backend: views when both known, otherwise likes. */
export function determinePerformanceWinner(
  videoA: VideoMetadata,
  videoB: VideoMetadata,
): VideoSlot | null {
  if (videoA.views > 0 && videoB.views > 0 && videoA.views !== videoB.views) {
    return videoA.views > videoB.views ? "A" : "B";
  }
  if (videoA.likes !== videoB.likes) {
    return videoA.likes > videoB.likes ? "A" : "B";
  }
  return null;
}

export function weakerSlot(winner: VideoSlot | null): VideoSlot | null {
  if (winner === "A") return "B";
  if (winner === "B") return "A";
  return null;
}

export function performanceLeadLabel(
  videoA: VideoMetadata,
  videoB: VideoMetadata,
  winner: VideoSlot,
): string {
  const hi = winner === "A" ? videoA : videoB;
  const lo = winner === "A" ? videoB : videoA;
  const byViews =
    videoA.views > 0 && videoB.views > 0 && videoA.views !== videoB.views;
  if (byViews) {
    const viewGap = hi.views - lo.views;
    return `+${viewGap.toLocaleString()} views`;
  }
  const likeGap = hi.likes - lo.likes;
  return `+${likeGap.toLocaleString()} likes`;
}

/** Chat suggestion chips — always derived from live video metrics, not stale labels. */
export function buildChatSuggestions(
  videoA: VideoMetadata,
  videoB: VideoMetadata,
): string[] {
  const winner = determinePerformanceWinner(videoA, videoB);
  const weaker = weakerSlot(winner);
  const suggestions: string[] = [];

  if (winner && weaker) {
    suggestions.push(
      `Why did Video ${winner} get more views and likes than Video ${weaker}?`,
    );
    suggestions.push(
      `Suggest improvements for Video ${weaker} based on what worked in Video ${winner}.`,
    );
  } else {
    suggestions.push("Why do these videos have similar views and likes?");
    suggestions.push("What are the main differences between Video A and Video B?");
  }

  suggestions.push("Compare the hooks used in the first 5 seconds.");
  suggestions.push("Which video had a stronger CTA?");
  suggestions.push("Summarize the key differences between the two videos.");

  return [...new Set(suggestions)].slice(0, 5);
}

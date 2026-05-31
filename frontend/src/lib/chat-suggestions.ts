import type {
  AnalysisSnapshot,
  ComparisonInsights,
  VideoMetadata,
  VideoSlot,
} from "./types";

/** Which slot leads on raw view count (when views are known). */
export function viewsLeader(
  videoA: VideoMetadata,
  videoB: VideoMetadata,
): VideoSlot | null {
  if (videoA.views <= 0 && videoB.views <= 0) return null;
  if (videoA.views === videoB.views) return null;
  return videoA.views > videoB.views ? "A" : "B";
}

export function weakerSlot(winner: VideoSlot | null): VideoSlot | null {
  if (winner === "A") return "B";
  if (winner === "B") return "A";
  return null;
}

/** Chat suggestion chips grounded in actual comparison results. */
export function buildChatSuggestions(
  videoA: VideoMetadata,
  videoB: VideoMetadata,
  comparison: ComparisonInsights,
): string[] {
  const { winner } = comparison;
  const weaker = weakerSlot(winner);
  const vLeader = viewsLeader(videoA, videoB);
  const suggestions: string[] = [];

  if (winner && weaker) {
    suggestions.push(
      `Why did Video ${winner} get more engagement than Video ${weaker}?`,
    );
    suggestions.push(
      `Suggest improvements for Video ${weaker} based on what worked in Video ${winner}.`,
    );
  } else {
    suggestions.push("Why do these videos have similar engagement?");
    suggestions.push("What are the main differences between Video A and Video B?");
  }

  if (vLeader) {
    const vOther = vLeader === "A" ? "B" : "A";
    if (winner && vLeader !== winner) {
      suggestions.push(
        `Video ${vOther} has more views but Video ${winner} leads on engagement — explain why.`,
      );
    } else {
      suggestions.push(
        `Video ${vLeader} has more views — what content choices likely drove that?`,
      );
    }
  }

  suggestions.push("Compare the hooks used in the first 5 seconds.");
  suggestions.push("Which video had a stronger CTA?");
  suggestions.push("Summarize the key differences between the two videos.");

  // Dedupe and cap at 5 chips.
  return [...new Set(suggestions)].slice(0, 5);
}

export function performanceFromSnapshot(snapshot: AnalysisSnapshot) {
  return {
    winner: snapshot.comparison.winner,
    weaker: weakerSlot(snapshot.comparison.winner),
    viewsLeader: viewsLeader(snapshot.videos.A, snapshot.videos.B),
  };
}

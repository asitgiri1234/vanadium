"use client";

import { useState } from "react";
import type { Citation as CitationType } from "@/lib/types";
import { cn } from "@/lib/utils";

export function CitationChip({ citation }: { citation: CitationType }) {
  const [open, setOpen] = useState(false);
  const color =
    citation.video_id === "A"
      ? "bg-violet-500/15 text-violet-300 hover:bg-violet-500/25"
      : "bg-cyan-500/15 text-cyan-300 hover:bg-cyan-500/25";
  const label =
    citation.chunk_index === -1
      ? `Video ${citation.video_id} · visual`
      : `Video ${citation.video_id} · #${citation.chunk_index} · ${citation.timestamp}`;

  return (
    <div className="relative inline-block">
      <button
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "rounded-md px-2 py-1 text-xs font-medium transition-colors",
          color,
        )}
        title={citation.snippet}
      >
        {label}
      </button>
      {open && citation.snippet && (
        <div className="absolute z-10 mt-1 w-72 rounded-md border border-border bg-card p-3 text-xs text-muted-foreground shadow-lg">
          <div className="mb-1 font-medium text-foreground">
            {citation.source_platform} · {citation.timestamp}
          </div>
          “{citation.snippet}”
        </div>
      )}
    </div>
  );
}

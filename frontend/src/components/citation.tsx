"use client";

import { useState } from "react";
import type { Citation as CitationType } from "@/lib/types";
import { cn } from "@/lib/utils";

export function CitationChip({ citation }: { citation: CitationType }) {
  const [open, setOpen] = useState(false);
  const isA = citation.video_id === "A";
  const color = isA
    ? "border-violet-500/30 bg-violet-500/10 text-violet-200 hover:border-violet-400/50 hover:shadow-[0_0_16px_-4px_hsl(276_91%_66%/0.5)]"
    : "border-cyan-500/30 bg-cyan-500/10 text-cyan-200 hover:border-cyan-400/50 hover:shadow-[0_0_16px_-4px_hsl(187_92%_53%/0.5)]";
  const label =
    citation.chunk_index === -1
      ? `VID_${citation.video_id} · VISUAL`
      : `VID_${citation.video_id} · #${citation.chunk_index} · ${citation.timestamp}`;

  return (
    <div className="relative inline-block">
      <button
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "rounded-md border px-2 py-1 font-mono text-[10px] font-medium backdrop-blur-sm transition-all duration-300",
          color,
        )}
        title={citation.snippet}
      >
        {label}
      </button>
      {open && citation.snippet && (
        <div className="absolute z-10 mt-2 w-72 rounded-xl border border-border/60 bg-card/95 p-4 text-xs text-muted-foreground shadow-glow backdrop-blur-xl">
          <div className="mb-2 font-mono text-[10px] uppercase tracking-wider text-accent">
            {citation.source_platform} · {citation.timestamp}
          </div>
          <p className="leading-relaxed text-foreground/85 selection:bg-accent/25">
            “{citation.snippet}”
          </p>
        </div>
      )}
    </div>
  );
}

"use client";

import { useState } from "react";
import { Loader2, Play, Radio } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";

export function UrlForm({
  onAnalyze,
  loading,
  error,
}: {
  onAnalyze: (a: string, b: string) => void;
  loading: boolean;
  error: string | null;
}) {
  const [urlA, setUrlA] = useState("");
  const [urlB, setUrlB] = useState("");

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (urlA.trim() && urlB.trim()) onAnalyze(urlA.trim(), urlB.trim());
  };

  return (
    <Card className="gradient-border shadow-glow-sm">
      <CardContent className="relative z-[1] pt-6">
        <div className="mb-5 flex items-center gap-2">
          <Radio className="h-4 w-4 text-accent animate-pulse-glow" />
          <span className="sci-fi-label">Enter video URLs</span>
        </div>
        <form
          onSubmit={submit}
          className="grid gap-4 md:grid-cols-[1fr_1fr_auto] md:items-end"
        >
          <Field
            label="Video A"
            placeholder="https://youtube.com/watch?v=..."
            value={urlA}
            onChange={setUrlA}
            disabled={loading}
            accent="text-violet-400"
            glow="shadow-[0_0_20px_-6px_hsl(276_91%_66%/0.3)]"
          />
          <Field
            label="Video B"
            placeholder="https://instagram.com/reel/..."
            value={urlB}
            onChange={setUrlB}
            disabled={loading}
            accent="text-cyan-400"
            glow="shadow-[0_0_20px_-6px_hsl(187_92%_53%/0.3)]"
          />
          <Button
            type="submit"
            variant="gradient"
            disabled={loading || !urlA || !urlB}
            className="md:mb-0 md:h-10"
          >
            {loading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Analyzing… this may take 30s
              </>
            ) : (
              <>
                <Play className="h-4 w-4" /> Analyze
              </>
            )}
          </Button>
        </form>
        {error && (
          <p className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-2.5 text-sm text-red-300 backdrop-blur-sm">
            {error}
          </p>
        )}
        <p className="mt-4 font-mono text-[11px] leading-relaxed text-muted-foreground/80">
          <span className="text-accent/80">&gt;</span> Supports YouTube + Instagram Reels ·
          extracts metadata, transcripts, visual frames, and indexes for RAG analysis.
        </p>
      </CardContent>
    </Card>
  );
}

function Field({
  label,
  placeholder,
  value,
  onChange,
  disabled,
  accent,
  glow,
}: {
  label: string;
  placeholder: string;
  value: string;
  onChange: (v: string) => void;
  disabled: boolean;
  accent: string;
  glow: string;
}) {
  return (
    <div>
      <label className={`mb-2 block font-mono text-[10px] font-semibold uppercase tracking-[0.18em] ${accent}`}>
        {label}
      </label>
      <Input
        type="url"
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className={glow}
      />
    </div>
  );
}

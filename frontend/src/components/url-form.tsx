"use client";

import { useState } from "react";
import { Loader2, Play } from "lucide-react";
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
    <Card>
      <CardContent className="pt-5">
        <form onSubmit={submit} className="grid gap-4 md:grid-cols-[1fr_1fr_auto] md:items-end">
          <Field
            label="Video A"
            placeholder="https://youtube.com/watch?v=..."
            value={urlA}
            onChange={setUrlA}
            disabled={loading}
            accent="text-sky-400"
          />
          <Field
            label="Video B"
            placeholder="https://instagram.com/reel/..."
            value={urlB}
            onChange={setUrlB}
            disabled={loading}
            accent="text-violet-400"
          />
          <Button type="submit" disabled={loading || !urlA || !urlB} className="md:mb-0">
            {loading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" /> Analyzing…
              </>
            ) : (
              <>
                <Play className="h-4 w-4" /> Analyze
              </>
            )}
          </Button>
        </form>
        {error && (
          <p className="mt-3 rounded-md bg-red-500/10 px-3 py-2 text-sm text-red-400">
            {error}
          </p>
        )}
        <p className="mt-3 text-xs text-muted-foreground">
          Supports YouTube and Instagram Reels. Ingestion extracts metadata + transcript,
          computes engagement, and indexes both videos for AI analysis.
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
}: {
  label: string;
  placeholder: string;
  value: string;
  onChange: (v: string) => void;
  disabled: boolean;
  accent: string;
}) {
  return (
    <div>
      <label className={`mb-1.5 block text-xs font-semibold uppercase tracking-wide ${accent}`}>
        {label}
      </label>
      <Input
        type="url"
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
      />
    </div>
  );
}

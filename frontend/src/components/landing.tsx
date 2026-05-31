"use client";

import Image from "next/image";
import Link from "next/link";
import {
  ArrowRight,
  BarChart3,
  Brain,
  Eye,
  FileText,
  MessageSquare,
  Sparkles,
  X,
  Zap,
} from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const STATS = [
  { value: "2 platforms", label: "YouTube + Instagram Reels supported" },
  { value: "Full stack", label: "Metadata · transcript · visual analysis" },
  { value: "Evidence-backed", label: "Every AI answer cites source chunks" },
];

const PROBLEMS = [
  {
    title: "You're guessing why one video wins",
    body: "Views and likes tell you what happened — not why. Creators waste hours manually comparing hooks, pacing, and CTAs.",
  },
  {
    title: "Cross-platform comparison is painful",
    body: "YouTube and Instagram expose different signals. Juggling tabs, screenshots, and notes doesn't scale.",
  },
  {
    title: "Generic AI advice ignores your content",
    body: "ChatGPT doesn't know your transcripts, on-screen text, or engagement numbers. Advice stays vague and ungrounded.",
  },
  {
    title: "No single source of truth",
    body: "Metadata, captions, and visual frames live in different places — never synthesized into one strategist view.",
  },
];

const SOLUTIONS = [
  {
    title: "Automatic deep ingest",
    body: "Paste two URLs. Vanadium pulls metadata, transcripts (Whisper for Reels), and vision analysis in one pass.",
  },
  {
    title: "AI strategist comparison",
    body: "A Groq-powered analyst explains why one video outperformed — hooks, CTAs, pacing, visuals — grounded in real data.",
  },
  {
    title: "RAG chat with citations",
    body: "Ask Vanadium anything. Answers retrieve transcript and visual evidence — with inline source references.",
  },
  {
    title: "Side-by-side intelligence dashboard",
    body: "Engagement bars, headline insights, transcripts, and visual readings — all in one premium workspace.",
  },
];

const FEATURES = [
  {
    id: "01",
    icon: BarChart3,
    title: "Engagement breakdown",
    body: "Views, likes, comments, and engagement rate computed per video — winner highlighted instantly.",
  },
  {
    id: "02",
    icon: FileText,
    title: "Transcript indexing",
    body: "YouTube captions or Whisper transcription for Reels. Chunked and embedded for semantic retrieval.",
  },
  {
    id: "03",
    icon: Eye,
    title: "Visual scene analysis",
    body: "Vision AI reads scene context and on-screen text — critical for music-only or text-overlay reels.",
  },
  {
    id: "04",
    icon: Brain,
    title: "LLM strategist summary",
    body: "Narrative comparison and actionable recommendations generated from metadata, transcripts, and visuals.",
  },
  {
    id: "05",
    icon: MessageSquare,
    title: "Ask Vanadium chat",
    body: "Follow-up questions with RAG — the model sees retrieved evidence, not just your question.",
  },
  {
    id: "06",
    icon: Sparkles,
    title: "Creator-first insights",
    body: "Hooks, CTAs, pacing, and format — explained the way a content strategist would, not a spreadsheet.",
  },
];

const FAQ = [
  {
    q: "Which platforms are supported?",
    a: "YouTube videos and Instagram Reels. Paste any public URL and hit Analyze.",
  },
  {
    q: "Do I need an API key?",
    a: "Yes — configure Groq (recommended) or OpenAI in backend/.env for AI comparison and chat. Ingest works without it for metadata and transcripts.",
  },
  {
    q: "How does Ask Vanadium work?",
    a: "Your question is embedded and matched against indexed transcript and visual chunks. The LLM answers using that evidence plus comparison context.",
  },
  {
    q: "Is my data stored?",
    a: "Analyses persist locally on disk (backend/data/) so sessions survive restarts. Nothing is sent to third parties except your configured LLM provider.",
  },
];

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-50 border-b border-border/40 bg-background/70 backdrop-blur-xl">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4 md:px-6">
        <Link href="/" className="flex items-center gap-3">
          <Image
            src="/logo.png"
            alt="Vanadium"
            width={36}
            height={36}
            className="rounded-lg shadow-glow-sm ring-1 ring-white/10"
          />
          <span className="text-gradient text-lg font-bold tracking-tight">Vanadium</span>
        </Link>
        <nav className="hidden items-center gap-8 sm:flex">
          <a href="#benefits" className="text-sm text-muted-foreground transition-colors hover:text-foreground">
            Benefits
          </a>
          <a href="#features" className="text-sm text-muted-foreground transition-colors hover:text-foreground">
            Features
          </a>
          <Link href="/analyze" className="text-sm text-muted-foreground transition-colors hover:text-foreground">
            Try it
          </Link>
        </nav>
        <Link href="/analyze" className={cn(buttonVariants({ variant: "gradient", size: "sm" }))}>
          Analyze videos <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      </div>
    </header>
  );
}

export function ToolHeader() {
  return (
    <header className="sticky top-0 z-50 border-b border-border/40 bg-background/70 backdrop-blur-xl">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4 md:px-6">
        <Link href="/" className="flex items-center gap-3">
          <Image
            src="/logo.png"
            alt="Vanadium"
            width={36}
            height={36}
            className="rounded-lg shadow-glow-sm ring-1 ring-white/10"
          />
          <span className="text-gradient text-lg font-bold tracking-tight">Vanadium</span>
        </Link>
        <nav className="hidden items-center gap-8 sm:flex">
          <Link href="/" className="text-sm text-muted-foreground transition-colors hover:text-foreground">
            Home
          </Link>
          <Link href="/#features" className="text-sm text-muted-foreground transition-colors hover:text-foreground">
            Features
          </Link>
          <Link href="/#benefits" className="text-sm text-muted-foreground transition-colors hover:text-foreground">
            Benefits
          </Link>
        </nav>
        <Link href="/" className={cn(buttonVariants({ variant: "outline", size: "sm" }))}>
          ← Home
        </Link>
      </div>
    </header>
  );
}

export function HeroSection() {
  return (
    <section className="mx-auto max-w-6xl px-4 pb-16 pt-14 md:px-6 md:pt-20">
      <div className="mx-auto max-w-3xl text-center">
        <p className="sci-fi-label mb-4">AI Content Intelligence for Creators</p>
        <h1 className="text-4xl font-bold leading-[1.1] tracking-tight md:text-5xl lg:text-6xl">
          Understand{" "}
          <span className="text-gradient">why one video beats another</span>
          {" "}— with evidence
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-base leading-relaxed text-muted-foreground md:text-lg">
          <strong className="font-semibold text-foreground">Vanadium</strong> compares two social
          videos side-by-side — metadata, transcripts, and visual frames — then an AI strategist
          explains what worked, what didn&apos;t, and what to do next.
        </p>
        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <Link href="/analyze" className={cn(buttonVariants({ variant: "gradient", size: "lg" }))}>
            Compare two videos <ArrowRight className="h-4 w-4" />
          </Link>
          <a href="#benefits" className={cn(buttonVariants({ variant: "outline", size: "lg" }))}>
            See how it works
          </a>
        </div>
      </div>

      <div className="mx-auto mt-14 grid max-w-4xl gap-4 sm:grid-cols-3">
        {STATS.map((s) => (
          <div
            key={s.label}
            className="glass-panel rounded-xl px-5 py-4 text-center transition-transform hover:scale-[1.02]"
          >
            <div className="text-gradient text-xl font-bold md:text-2xl">{s.value}</div>
            <div className="mt-1 text-xs leading-snug text-muted-foreground">{s.label}</div>
          </div>
        ))}
      </div>

      <p className="mt-10 text-center font-mono text-[11px] text-muted-foreground/70">
        {"// works with YouTube + Instagram · powered by Groq · RAG-backed chat"}
      </p>
    </section>
  );
}

export function BenefitsSection() {
  return (
    <section id="benefits" className="mx-auto max-w-6xl scroll-mt-24 px-4 py-16 md:px-6">
      <div className="mb-12 text-center">
        <h2 className="text-2xl font-bold tracking-tight md:text-3xl">
          The problem — and the fix
        </h2>
        <p className="mx-auto mt-3 max-w-xl text-sm text-muted-foreground md:text-base">
          Creators don&apos;t need more metrics. They need a strategist that reads both videos
          and tells them why one outperformed.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="glass-panel space-y-3 rounded-2xl p-6 md:p-8">
          <p className="sci-fi-label text-red-400/90">Problems</p>
          <ul className="space-y-4">
            {PROBLEMS.map((p) => (
              <li key={p.title} className="flex gap-3">
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-red-500/15 text-red-400">
                  <X className="h-3 w-3" />
                </span>
                <div>
                  <p className="font-medium text-foreground/95">{p.title}</p>
                  <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{p.body}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>

        <div className="glass-panel gradient-border space-y-3 rounded-2xl p-6 md:p-8">
          <p className="sci-fi-label text-accent">Solutions</p>
          <ul className="space-y-4">
            {SOLUTIONS.map((s) => (
              <li key={s.title} className="flex gap-3">
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-accent/15 text-accent">
                  <Zap className="h-3 w-3" />
                </span>
                <div>
                  <p className="font-medium text-foreground/95">{s.title}</p>
                  <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{s.body}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}

export function FeaturesSection() {
  return (
    <section id="features" className="mx-auto max-w-6xl scroll-mt-24 px-4 py-16 md:px-6">
      <div className="mb-12 text-center">
        <h2 className="text-2xl font-bold tracking-tight md:text-3xl">Features</h2>
        <p className="mx-auto mt-3 max-w-xl text-sm text-muted-foreground md:text-base">
          Everything under the hood that turns two URLs into strategist-grade intelligence.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {FEATURES.map((f) => (
          <div
            key={f.id}
            className="glass-panel group rounded-xl p-5 transition-all duration-300 hover:border-primary/30 hover:shadow-glow-sm"
          >
            <div className="mb-3 flex items-center justify-between">
              <span className="font-mono text-[10px] text-muted-foreground">
                feature_{f.id} →
              </span>
              <f.icon className="h-4 w-4 text-primary opacity-70 transition-opacity group-hover:opacity-100" />
            </div>
            <h3 className="font-semibold text-foreground">{f.title}</h3>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{f.body}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

export function CtaSection() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-20 md:px-6">
      <div className="glass-panel gradient-border mx-auto max-w-2xl rounded-2xl px-8 py-12 text-center">
        <p className="sci-fi-label mb-3">Ready to compare?</p>
        <h2 className="text-2xl font-bold tracking-tight md:text-3xl">
          Open the analysis workspace
        </h2>
        <p className="mx-auto mt-3 max-w-md text-sm text-muted-foreground">
          Paste two URLs and get metadata, transcripts, visual analysis, AI comparison,
          and evidence-backed chat — all in one place.
        </p>
        <Link
          href="/analyze"
          className={cn(buttonVariants({ variant: "gradient", size: "lg" }), "mt-8 inline-flex")}
        >
          Try it now <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    </section>
  );
}

export function FaqSection() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-16 md:px-6">
      <div className="mb-10 text-center">
        <h2 className="text-2xl font-bold tracking-tight md:text-3xl">FAQ</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Common questions before you run your first comparison.
        </p>
      </div>
      <div className="mx-auto max-w-2xl space-y-3">
        {FAQ.map((item) => (
          <details
            key={item.q}
            className="glass-panel group rounded-xl [&_summary::-webkit-details-marker]:hidden"
          >
            <summary className="cursor-pointer list-none px-5 py-4 font-medium transition-colors hover:text-primary">
              <span className="flex items-center justify-between gap-4">
                {item.q}
                <span className="text-muted-foreground transition-transform group-open:rotate-45">
                  +
                </span>
              </span>
            </summary>
            <p className="border-t border-border/40 px-5 pb-4 pt-3 text-sm leading-relaxed text-muted-foreground">
              {item.a}
            </p>
          </details>
        ))}
      </div>
    </section>
  );
}

export function SiteFooter() {
  return (
    <footer className="border-t border-border/40 bg-card/30">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-4 py-10 md:flex-row md:px-6">
        <div className="flex items-center gap-2">
          <Image src="/logo.png" alt="" width={28} height={28} className="rounded-md" />
          <span className="text-sm font-semibold">Vanadium</span>
        </div>
        <p className="text-center text-xs text-muted-foreground md:text-left">
          AI content intelligence · evidence-backed video comparison · RAG chat for creators
        </p>
        <div className="flex gap-4 font-mono text-[10px] text-muted-foreground">
          <span className="text-accent">RAG</span>
          <span>·</span>
          <span className="text-primary">Groq</span>
          <span>·</span>
          <span>YouTube + IG</span>
        </div>
      </div>
    </footer>
  );
}

export function SectionLabel({
  icon: Icon,
  label,
}: {
  icon: React.ElementType;
  label: string;
}) {
  return (
    <div className="flex items-center gap-3">
      <div className="flex h-7 w-7 items-center justify-center rounded-md border border-border/60 bg-muted/30">
        <Icon className="h-3.5 w-3.5 text-accent" />
      </div>
      <span className="sci-fi-label">{label}</span>
      <div className="h-px flex-1 bg-gradient-to-r from-border/80 to-transparent" />
    </div>
  );
}

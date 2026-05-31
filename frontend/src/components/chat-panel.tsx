"use client";

import { useEffect, useRef, useState } from "react";
import { Bot, Send, Sparkles, User } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CitationChip } from "@/components/citation";
import { streamChat } from "@/lib/api";
import { buildChatSuggestions } from "@/lib/chat-suggestions";
import type { ChatMessage, Citation, VideoMetadata } from "@/lib/types";

let idCounter = 0;
const nextId = () => `msg_${Date.now()}_${idCounter++}`;

export function ChatPanel({
  analysisId,
  videoA,
  videoB,
}: {
  analysisId: string;
  videoA: VideoMetadata;
  videoB: VideoMetadata;
}) {
  const suggestions = buildChatSuggestions(videoA, videoB);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const send = async (text: string) => {
    const question = text.trim();
    if (!question || streaming) return;

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    const userMsg: ChatMessage = { id: nextId(), role: "user", content: question };
    const assistantId = nextId();
    const assistantMsg: ChatMessage = {
      id: assistantId,
      role: "assistant",
      content: "",
      citations: [],
      streaming: true,
    };
    setMessages((m) => [...m, userMsg, assistantMsg]);
    setInput("");
    setStreaming(true);

    const update = (patch: Partial<ChatMessage>) =>
      setMessages((m) => m.map((msg) => (msg.id === assistantId ? { ...msg, ...patch } : msg)));

    let buffer = "";
    let citations: Citation[] = [];

    await streamChat(
      analysisId,
      question,
      {
        onToken: (t) => {
          buffer += t;
          update({ content: buffer });
        },
        onCitations: (c) => {
          citations = c;
          update({ citations: c });
        },
        onError: (detail) => {
          update({ content: buffer || `⚠️ ${detail}`, streaming: false });
          setStreaming(false);
        },
        onDone: () => {
          update({ content: buffer, citations, streaming: false });
          setStreaming(false);
        },
      },
      controller.signal,
    ).catch((err) => {
      if (err instanceof Error && err.name === "AbortError") {
        setStreaming(false);
        return;
      }
      update({ content: buffer || `⚠️ ${err.message}`, streaming: false });
      setStreaming(false);
    });
  };

  return (
    <Card className="flex h-[640px] flex-col shadow-glow-sm">
      <CardHeader className="border-b border-border/50 pb-4">
        <CardTitle className="flex items-center gap-3 text-base">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-primary/30 bg-primary/10">
            <Sparkles className="h-4 w-4 text-primary" />
          </div>
          <div>
            <span>Ask Vanadium</span>
            <p className="font-mono text-[10px] font-normal uppercase tracking-widest text-muted-foreground">
              RAG · Evidence-backed Q&A
            </p>
          </div>
        </CardTitle>
      </CardHeader>

      <CardContent
        ref={scrollRef}
        className="scroll-thin flex-1 space-y-5 overflow-y-auto py-5"
      >
        {messages.length === 0 ? (
          <EmptyState suggestions={suggestions} onPick={send} />
        ) : (
          messages.map((msg) => <MessageBubble key={msg.id} message={msg} />)
        )}
      </CardContent>

      <div className="border-t border-border/50 bg-muted/10 p-4 backdrop-blur-md">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            send(input);
          }}
          className="flex gap-2"
        >
          <Input
            placeholder="Query the intelligence layer…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={streaming}
            className="font-mono text-sm"
          />
          <Button type="submit" variant="gradient" size="icon" disabled={streaming || !input.trim()}>
            <Send className="h-4 w-4" />
          </Button>
        </form>
      </div>
    </Card>
  );
}

function EmptyState({
  suggestions,
  onPick,
}: {
  suggestions: string[];
  onPick: (q: string) => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-5 py-10 text-center">
      <div className="relative animate-float">
        <div className="absolute -inset-4 rounded-full bg-primary/20 blur-2xl" />
        <div className="relative flex h-16 w-16 items-center justify-center rounded-2xl border border-primary/30 bg-primary/10 shadow-glow-sm">
          <Bot className="h-8 w-8 text-primary" />
        </div>
      </div>
      <div>
        <p className="sci-fi-label mb-2">Neural Strategist Ready</p>
        <p className="max-w-sm text-sm text-muted-foreground">
          Ask anything about the two videos — answers are grounded in transcript and
          visual evidence.
        </p>
      </div>
      <div className="flex max-w-lg flex-wrap justify-center gap-2">
        {suggestions.map((s) => (
          <button key={s} onClick={() => onPick(s)} className="suggestion-chip">
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <div className={`flex gap-3 ${isUser ? "flex-row-reverse" : ""}`}>
      <div
        className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border ${
          isUser
            ? "border-border/60 bg-muted/40"
            : "border-primary/30 bg-primary/10 shadow-glow-sm"
        }`}
      >
        {isUser ? (
          <User className="h-4 w-4 text-muted-foreground" />
        ) : (
          <Bot className="h-4 w-4 text-primary" />
        )}
      </div>
      <div className={`max-w-[85%] ${isUser ? "text-right" : ""}`}>
        <div
          className={`inline-block whitespace-pre-wrap rounded-xl px-4 py-3 text-sm leading-relaxed ${
            isUser ? "chat-bubble-user" : "chat-bubble-ai"
          }`}
        >
          {message.content}
          {message.streaming && !message.content && (
            <span className="inline-flex gap-1 font-mono">
              <span className="typing-dot">▸</span>
              <span className="typing-dot">▸</span>
              <span className="typing-dot">▸</span>
            </span>
          )}
        </div>
        {message.citations && message.citations.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {message.citations.map((c, i) => (
              <CitationChip key={`${c.video_id}-${c.chunk_index}-${i}`} citation={c} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

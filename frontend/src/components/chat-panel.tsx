"use client";

import { useEffect, useRef, useState } from "react";
import { Bot, Send, Sparkles, User } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CitationChip } from "@/components/citation";
import { streamChat } from "@/lib/api";
import type { ChatMessage, Citation } from "@/lib/types";

const SUGGESTIONS = [
  "Why did Video A get more engagement than Video B?",
  "Compare the hooks used in the first 5 seconds.",
  "Which video had a stronger CTA?",
  "Suggest improvements for Video B based on what worked in Video A.",
  "Summarize the key differences between the two videos.",
];

let idCounter = 0;
const nextId = () => `msg_${Date.now()}_${idCounter++}`;

export function ChatPanel({ analysisId }: { analysisId: string }) {
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
    <Card className="flex h-[640px] flex-col">
      <CardHeader className="border-b border-border pb-4">
        <CardTitle className="flex items-center gap-2 text-base">
          <Sparkles className="h-4 w-4 text-primary" />
          Ask Vanadium
        </CardTitle>
      </CardHeader>

      <CardContent
        ref={scrollRef}
        className="scroll-thin flex-1 space-y-4 overflow-y-auto py-4"
      >
        {messages.length === 0 ? (
          <EmptyState onPick={send} />
        ) : (
          messages.map((msg) => <MessageBubble key={msg.id} message={msg} />)
        )}
      </CardContent>

      <div className="border-t border-border p-4">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            send(input);
          }}
          className="flex gap-2"
        >
          <Input
            placeholder="Ask why one video outperformed the other…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={streaming}
          />
          <Button type="submit" variant="gradient" size="icon" disabled={streaming || !input.trim()}>
            <Send className="h-4 w-4" />
          </Button>
        </form>
      </div>
    </Card>
  );
}

function EmptyState({ onPick }: { onPick: (q: string) => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-8 text-center">
      <Bot className="h-10 w-10 text-primary" />
      <div>
        <p className="font-medium">Your AI content strategist is ready.</p>
        <p className="text-sm text-muted-foreground">
          Ask anything about the two videos — answers are backed by transcript evidence.
        </p>
      </div>
      <div className="flex flex-wrap justify-center gap-2">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => onPick(s)}
            className="rounded-full border border-border bg-muted/40 px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
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
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
          isUser ? "bg-muted" : "bg-primary/15"
        }`}
      >
        {isUser ? (
          <User className="h-4 w-4" />
        ) : (
          <Bot className="h-4 w-4 text-primary" />
        )}
      </div>
      <div className={`max-w-[85%] ${isUser ? "text-right" : ""}`}>
        <div
          className={`inline-block whitespace-pre-wrap rounded-lg px-4 py-2.5 text-sm ${
            isUser ? "bg-primary text-primary-foreground" : "bg-muted/50"
          }`}
        >
          {message.content}
          {message.streaming && !message.content && (
            <span className="inline-flex gap-1">
              <span className="typing-dot">●</span>
              <span className="typing-dot">●</span>
              <span className="typing-dot">●</span>
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

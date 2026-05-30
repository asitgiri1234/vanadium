import type { AnalysisSnapshot, Citation } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface HealthResponse {
  status: string;
  version: string;
  openai_configured: boolean;
  whisper_enabled: boolean;
}

async function jsonOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      /* ignore parse errors */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export async function getHealth(): Promise<HealthResponse> {
  return jsonOrThrow<HealthResponse>(await fetch(`${API_URL}/api/health`));
}

/**
 * Resolve a displayable thumbnail src. Instagram CDN images are routed through
 * the backend proxy because the CDN blocks direct hotlinking (needs a Referer).
 */
export function thumbnailSrc(
  url: string | null,
  platform: string,
): string | null {
  if (!url) return null;
  if (platform === "instagram") {
    return `${API_URL}/api/thumbnail?url=${encodeURIComponent(url)}`;
  }
  return url;
}

export async function ingest(
  videoAUrl: string,
  videoBUrl: string,
): Promise<AnalysisSnapshot> {
  const res = await fetch(`${API_URL}/api/ingest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ video_a_url: videoAUrl, video_b_url: videoBUrl }),
  });
  return jsonOrThrow<AnalysisSnapshot>(res);
}

export async function getAnalysis(id: string): Promise<AnalysisSnapshot> {
  return jsonOrThrow<AnalysisSnapshot>(await fetch(`${API_URL}/api/analysis/${id}`));
}

export interface ChatHandlers {
  onToken: (text: string) => void;
  onCitations: (citations: Citation[]) => void;
  onError: (detail: string) => void;
  onDone: (messageId: string) => void;
}

/**
 * Stream a chat answer over Server-Sent Events. The backend uses POST, so we
 * read the response body manually instead of the EventSource API.
 */
export async function streamChat(
  analysisId: string,
  message: string,
  handlers: ChatHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${API_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ analysis_id: analysisId, message }),
    signal,
  });

  if (!res.ok || !res.body) {
    handlers.onError(`Chat request failed (${res.status})`);
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE frames are separated by a blank line.
    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      dispatchFrame(frame, handlers);
    }
  }
}

function dispatchFrame(frame: string, handlers: ChatHandlers): void {
  let event = "message";
  const dataLines: string[] = [];

  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  if (dataLines.length === 0) return;

  let data: unknown;
  try {
    data = JSON.parse(dataLines.join("\n"));
  } catch {
    return;
  }

  switch (event) {
    case "token":
      handlers.onToken((data as { text: string }).text);
      break;
    case "citations":
      handlers.onCitations(data as Citation[]);
      break;
    case "error":
      handlers.onError((data as { detail: string }).detail);
      break;
    case "done":
      handlers.onDone((data as { message_id: string }).message_id);
      break;
  }
}

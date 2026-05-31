import type {
  AnalysisSnapshot,
  Citation,
  TranscriptResponse,
  VisualResponse,
} from "./types";

const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(
  /\/$/,
  "",
);

function fetchErrorMessage(err: unknown, path: string): string {
  if (err instanceof TypeError && /failed to fetch|networkerror|load failed/i.test(err.message)) {
    const isProd = typeof window !== "undefined" && window.location.protocol === "https:";
    const apiIsLocal =
      API_URL.includes("localhost") || API_URL.startsWith("http://127.0.0.1");
    if (isProd && apiIsLocal) {
      return (
        "Cannot reach the API — NEXT_PUBLIC_API_URL is still localhost. " +
        "Set it to your Render URL in Vercel env vars and redeploy the frontend."
      );
    }
    return (
      `Cannot reach the API at ${API_URL}${path}. ` +
      "Check that Render is running, CORS_ORIGINS includes your Vercel URL, " +
      "and the free tier instance has finished waking up (~60s)."
    );
  }
  return err instanceof Error ? err.message : "Request failed.";
}

async function apiFetch(input: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(input, init);
  } catch (err) {
    const path = input.startsWith(API_URL) ? input.slice(API_URL.length) : input;
    throw new Error(fetchErrorMessage(err, path));
  }
}

export interface HealthResponse {
  status: string;
  version: string;
  llm_provider: string;
  llm_configured: boolean;
  openai_configured: boolean;
  groq_configured: boolean;
  whisper_enabled: boolean;
  visual_enabled: boolean;
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
  return jsonOrThrow<HealthResponse>(await apiFetch(`${API_URL}/api/health`));
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
  const res = await apiFetch(`${API_URL}/api/ingest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ video_a_url: videoAUrl, video_b_url: videoBUrl }),
  });
  return jsonOrThrow<AnalysisSnapshot>(res);
}

export async function getAnalysis(id: string): Promise<AnalysisSnapshot> {
  return jsonOrThrow<AnalysisSnapshot>(await apiFetch(`${API_URL}/api/analysis/${id}`));
}

export async function getTranscript(id: string): Promise<TranscriptResponse> {
  return jsonOrThrow<TranscriptResponse>(
    await apiFetch(`${API_URL}/api/analysis/${id}/transcript`),
  );
}

export async function getVisual(id: string): Promise<VisualResponse> {
  return jsonOrThrow<VisualResponse>(
    await apiFetch(`${API_URL}/api/analysis/${id}/visual`),
  );
}

export interface ChatHandlers {
  onToken: (text: string) => void;
  onCitations: (citations: Citation[]) => void;
  onError: (detail: string) => void;
  onDone: (messageId: string) => void;
}

/** Normalize SSE wire format (sse-starlette defaults to CRLF). */
function normalizeSseBuffer(raw: string): string {
  return raw.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
}

function drainSseFrames(
  buffer: string,
  handlers: ChatHandlers,
  finished: { value: boolean },
): string {
  let rest = normalizeSseBuffer(buffer);
  let sep: number;
  while ((sep = rest.indexOf("\n\n")) !== -1) {
    const frame = rest.slice(0, sep);
    rest = rest.slice(sep + 2);
    dispatchFrame(frame, handlers, finished);
  }
  return rest;
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
  const finished = { value: false };

  const res = await apiFetch(`${API_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ analysis_id: analysisId, message }),
    signal,
  });

  if (!res.ok) {
    let detail = `Chat request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body?.detail) {
        detail =
          typeof body.detail === "string"
            ? body.detail
            : JSON.stringify(body.detail);
      }
    } catch {
      /* ignore parse errors */
    }
    handlers.onError(detail);
    return;
  }

  if (!res.body) {
    handlers.onError("Chat request failed (no response body)");
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    buffer = drainSseFrames(buffer, handlers, finished);
  }

  buffer += decoder.decode(undefined, { stream: false });
  buffer = drainSseFrames(buffer, handlers, finished);
  if (buffer.trim()) {
    dispatchFrame(buffer.trim(), handlers, finished);
  }

  if (!finished.value) {
    handlers.onError("Stream ended unexpectedly");
  }
}

function dispatchFrame(
  frame: string,
  handlers: ChatHandlers,
  finished: { value: boolean },
): void {
  let event = "message";
  const dataLines: string[] = [];

  for (const line of frame.split("\n")) {
    const trimmed = line.trimEnd();
    if (trimmed.startsWith("event:")) event = trimmed.slice(6).trim();
    else if (trimmed.startsWith("data:")) dataLines.push(trimmed.slice(5).trim());
  }
  if (dataLines.length === 0) return;

  let data: unknown;
  try {
    data = JSON.parse(dataLines.join("\n"));
  } catch {
    return;
  }

  switch (event) {
    case "token": {
      const text = (data as { text?: string }).text;
      if (text) handlers.onToken(text);
      break;
    }
    case "citations":
      handlers.onCitations(data as Citation[]);
      break;
    case "error":
      finished.value = true;
      handlers.onError((data as { detail: string }).detail);
      break;
    case "done":
      finished.value = true;
      handlers.onDone((data as { message_id: string }).message_id);
      break;
  }
}

import type {
  AnalysisSnapshot,
  AnalysisProgress,
  Citation,
  TranscriptResponse,
  VisualResponse,
} from "./types";
import {
  isLocalApiUrl,
  normalizeApiUrl,
  PRODUCTION_API_URL,
} from "./backend-url";

const BUILD_TIME_URL = normalizeApiUrl(
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
);

let resolvedApiUrl: string | null = null;
let apiUrlPromise: Promise<string> | null = null;

/** Resolve backend base URL (Render in prod, localhost in dev). */
export async function getApiBaseUrl(): Promise<string> {
  if (resolvedApiUrl) return resolvedApiUrl;
  if (!apiUrlPromise) apiUrlPromise = resolveApiBaseUrl();
  resolvedApiUrl = await apiUrlPromise;
  return resolvedApiUrl;
}

async function resolveApiBaseUrl(): Promise<string> {
  if (!isLocalApiUrl(BUILD_TIME_URL)) return BUILD_TIME_URL;

  // Production bundle still points at localhost — read runtime URL from Vercel.
  if (typeof window !== "undefined" && window.location.protocol === "https:") {
    try {
      const res = await fetch("/api/config");
      if (res.ok) {
        const body = (await res.json()) as { apiUrl?: string };
        let apiUrl = normalizeApiUrl(body.apiUrl ?? "");
        if (isLocalApiUrl(apiUrl)) apiUrl = PRODUCTION_API_URL;
        if (apiUrl) return apiUrl;
      }
    } catch {
      /* use production fallback below */
    }
    return PRODUCTION_API_URL;
  }

  return BUILD_TIME_URL;
}

function fetchErrorMessage(err: unknown, apiUrl: string, path: string): string {
  if (
    err instanceof TypeError &&
    /failed to fetch|networkerror|load failed/i.test(err.message)
  ) {
    const isProd =
      typeof window !== "undefined" && window.location.protocol === "https:";
    if (isProd && isLocalApiUrl(apiUrl)) {
      return (
        "Cannot reach the API — backend URL is still localhost. " +
        "In Vercel set API_URL=https://vanadium-1.onrender.com (or NEXT_PUBLIC_API_URL) " +
        "for Production, then redeploy."
      );
    }
    return (
      `Cannot reach the API at ${apiUrl}${path}. ` +
      "Check Render is running and CORS allows your Vercel domain (~60s cold start on free tier)."
    );
  }
  return err instanceof Error ? err.message : "Request failed.";
}

async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  const apiUrl = await getApiBaseUrl();
  const url = `${apiUrl}${path}`;
  try {
    return await fetch(url, init);
  } catch (err) {
    throw new Error(fetchErrorMessage(err, apiUrl, path));
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
  return jsonOrThrow<HealthResponse>(await apiFetch("/api/health"));
}

/**
 * Resolve a displayable thumbnail src. Instagram CDN images are routed through
 * the backend proxy because the CDN blocks direct hotlinking (needs a Referer).
 */
export async function thumbnailSrc(
  url: string | null,
  platform: string,
): Promise<string | null> {
  if (!url) return null;
  if (platform === "instagram") {
    const apiUrl = await getApiBaseUrl();
    return `${apiUrl}/api/thumbnail?url=${encodeURIComponent(url)}`;
  }
  return url;
}

export async function ingest(
  videoAUrl: string,
  videoBUrl: string,
): Promise<AnalysisSnapshot> {
  const res = await apiFetch("/api/ingest", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ video_a_url: videoAUrl, video_b_url: videoBUrl }),
  });
  return jsonOrThrow<AnalysisSnapshot>(res);
}

export async function startIngest(
  videoAUrl: string,
  videoBUrl: string,
): Promise<AnalysisProgress> {
  const res = await apiFetch("/api/ingest/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ video_a_url: videoAUrl, video_b_url: videoBUrl }),
  });
  return jsonOrThrow<AnalysisProgress>(res);
}

export async function getAnalysis(id: string): Promise<AnalysisSnapshot> {
  return jsonOrThrow<AnalysisSnapshot>(await apiFetch(`/api/analysis/${id}`));
}

export async function getAnalysisProgress(id: string): Promise<AnalysisProgress> {
  return jsonOrThrow<AnalysisProgress>(await apiFetch(`/api/analysis/${id}/progress`));
}

export async function getTranscript(id: string): Promise<TranscriptResponse> {
  return jsonOrThrow<TranscriptResponse>(
    await apiFetch(`/api/analysis/${id}/transcript`),
  );
}

export async function getVisual(id: string): Promise<VisualResponse> {
  return jsonOrThrow<VisualResponse>(
    await apiFetch(`/api/analysis/${id}/visual`),
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

  const res = await apiFetch("/api/chat", {
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

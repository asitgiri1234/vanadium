import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "edge";

type CaptionSegment = { text: string; start: number; duration: number };

function extractJsonArray(html: string, marker: string): unknown[] | null {
  const idx = html.indexOf(marker);
  if (idx < 0) return null;
  let start = idx + marker.length;
  while (start < html.length && " \t\n\r".includes(html[start])) start += 1;
  if (start >= html.length || html[start] !== "[") return null;

  let depth = 0;
  for (let i = start; i < html.length; i += 1) {
    const ch = html[i];
    if (ch === "[") depth += 1;
    else if (ch === "]") {
      depth -= 1;
      if (depth === 0) {
        try {
          const parsed = JSON.parse(html.slice(start, i + 1));
          return Array.isArray(parsed) ? parsed : null;
        } catch {
          return null;
        }
      }
    }
  }
  return null;
}

function parseJson3(raw: string): CaptionSegment[] {
  try {
    const payload = JSON.parse(raw) as {
      events?: Array<{ tStartMs?: number; segs?: Array<{ utf8?: string }> }>;
    };
    const segments: CaptionSegment[] = [];
    for (const event of payload.events ?? []) {
      const start = (event.tStartMs ?? 0) / 1000;
      const parts: string[] = [];
      for (const seg of event.segs ?? []) {
        const text = (seg.utf8 ?? "").trim();
        if (text && text !== "\n") parts.push(text);
      }
      const text = parts.join(" ").trim();
      if (text) segments.push({ text, start, duration: 0 });
    }
    return segments;
  } catch {
    return [];
  }
}

async function fetchWatchHtml(videoId: string): Promise<string | null> {
  for (const watchUrl of [
    `https://m.youtube.com/watch?v=${videoId}`,
    `https://www.youtube.com/watch?v=${videoId}`,
  ]) {
    try {
      const resp = await fetch(watchUrl, {
        headers: {
          "User-Agent":
            "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
          "Accept-Language": "en-US,en;q=0.9",
        },
        cache: "no-store",
      });
      if (resp.ok) return await resp.text();
    } catch {
      continue;
    }
  }
  return null;
}

async function fetchViaWatchHtml(videoId: string): Promise<CaptionSegment[]> {
  const html = await fetchWatchHtml(videoId);
  if (!html) return [];

  const tracks = extractJsonArray(html, '"captionTracks":') as
    | Array<{ languageCode?: string; baseUrl?: string }>
    | null;
  if (!tracks?.length) return [];

  for (const track of tracks) {
    const lang = String(track.languageCode ?? "");
    if (lang && !lang.startsWith("en")) continue;
    const baseUrl = String(track.baseUrl ?? "");
    if (!baseUrl) continue;

    const captionResp = await fetch(`${baseUrl}&fmt=json3`, { cache: "no-store" });
    if (!captionResp.ok) continue;
    const segments = parseJson3(await captionResp.text());
    if (segments.length) return segments;
  }

  return [];
}

async function fetchViaTranscriptApi(videoId: string): Promise<CaptionSegment[]> {
  try {
    const { YouTubeTranscriptApi } = await import("youtube-transcript-api");
    const api = new YouTubeTranscriptApi();
    const fetched = await api.fetch(videoId);
    return fetched.map((item) => ({
      text: item.text,
      start: item.start,
      duration: item.duration,
    }));
  } catch {
    return [];
  }
}

export async function GET(request: NextRequest) {
  const videoId = request.nextUrl.searchParams.get("videoId")?.trim();
  if (!videoId) {
    return NextResponse.json({ error: "videoId required" }, { status: 400 });
  }

  try {
    let segments = await fetchViaWatchHtml(videoId);
    if (!segments.length) {
      segments = await fetchViaTranscriptApi(videoId);
    }
    return NextResponse.json({ segments });
  } catch (error) {
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : "fetch failed",
        segments: [],
      },
      { status: 502 },
    );
  }
}

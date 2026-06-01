import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

type CaptionSegment = { text: string; start: number; duration: number };

const INNERTUBE_KEY = "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8";

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

function parseXmlTranscript(raw: string): CaptionSegment[] {
  const segments: CaptionSegment[] = [];
  const re = /<text start="([^"]+)"[^>]*>([\s\S]*?)<\/text>/g;
  let match: RegExpExecArray | null;
  while ((match = re.exec(raw)) !== null) {
    const start = parseFloat(match[1] || "0");
    const text = match[2]
      .replace(/<[^>]+>/g, "")
      .replace(/&amp;/g, "&")
      .replace(/&lt;/g, "<")
      .replace(/&gt;/g, ">")
      .replace(/&#39;/g, "'")
      .replace(/&quot;/g, '"')
      .trim();
    if (text) segments.push({ text, start, duration: 0 });
  }
  return segments;
}

async function fetchViaTranscriptPlus(videoId: string): Promise<CaptionSegment[]> {
  try {
    const { fetchTranscript } = await import("youtube-transcript-plus");
    const fetched = await fetchTranscript(videoId, { lang: "en" });
    return fetched.map((item) => ({
      text: item.text,
      start: item.offset ?? 0,
      duration: item.duration ?? 0,
    }));
  } catch {
    return [];
  }
}

async function fetchViaYoutubeTranscript(videoId: string): Promise<CaptionSegment[]> {
  try {
    const { YoutubeTranscript } = await import("youtube-transcript");
    const fetched = await YoutubeTranscript.fetchTranscript(videoId, { lang: "en" });
    return fetched.map((item) => ({
      text: item.text,
      start: (item.offset ?? 0) / 1000,
      duration: (item.duration ?? 0) / 1000,
    }));
  } catch {
    return [];
  }
}

async function fetchCaptionUrl(baseUrl: string): Promise<CaptionSegment[]> {
  for (const suffix of ["&fmt=json3", "&fmt=vtt", ""]) {
    try {
      const captionResp = await fetch(`${baseUrl}${suffix}`, { cache: "no-store" });
      if (!captionResp.ok) continue;
      const text = await captionResp.text();
      if (suffix.includes("json3") || text.trim().startsWith("{")) {
        const parsed = parseJson3(text);
        if (parsed.length) return parsed;
      }
      if (text.includes("<text")) {
        const parsed = parseXmlTranscript(text);
        if (parsed.length) return parsed;
      }
    } catch {
      continue;
    }
  }
  return [];
}

async function fetchViaInnertubeCaptions(videoId: string): Promise<CaptionSegment[]> {
  const clients = [
    { clientName: "ANDROID", clientVersion: "20.10.38", hl: "en", gl: "US" },
    { clientName: "MWEB", clientVersion: "2.20240405.01.00", hl: "en", gl: "US" },
    { clientName: "WEB", clientVersion: "2.20240405.00.00", hl: "en", gl: "US" },
    { clientName: "TVHTML5_SIMPLY_EMBEDDED_PLAYER", clientVersion: "2.0", hl: "en", gl: "US" },
  ];

  for (const client of clients) {
    const resp = await fetch(
      `https://youtubei.googleapis.com/youtubei/v1/player?key=${INNERTUBE_KEY}`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "User-Agent":
            "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
          Origin: "https://www.youtube.com",
          Referer: "https://www.youtube.com/",
        },
        body: JSON.stringify({ context: { client }, videoId }),
        cache: "no-store",
      },
    );
    if (!resp.ok) continue;

    const player = await resp.json().catch(() => ({}));
    const tracks =
      player?.captions?.playerCaptionsTracklistRenderer?.captionTracks ?? [];

    const sorted = [...tracks].sort((a, b) => {
      const la = String(a.languageCode ?? "");
      const lb = String(b.languageCode ?? "");
      const score = (lang: string) =>
        lang.startsWith("en") ? 0 : lang.startsWith("a.en") ? 1 : 2;
      return score(la) - score(lb);
    });

    for (const track of sorted) {
      const baseUrl = String(track.baseUrl ?? "");
      if (!baseUrl) continue;
      const segments = await fetchCaptionUrl(baseUrl);
      if (segments.length) return segments;
    }
  }
  return [];
}

export async function GET(request: NextRequest) {
  const videoId = request.nextUrl.searchParams.get("videoId")?.trim();
  if (!videoId) {
    return NextResponse.json({ error: "videoId required" }, { status: 400 });
  }

  try {
    let segments = await fetchViaTranscriptPlus(videoId);
    if (!segments.length) segments = await fetchViaYoutubeTranscript(videoId);
    if (!segments.length) segments = await fetchViaInnertubeCaptions(videoId);
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

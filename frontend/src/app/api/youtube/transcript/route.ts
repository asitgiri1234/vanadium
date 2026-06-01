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

async function fetchViaYoutubeTranscript(videoId: string): Promise<CaptionSegment[]> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 25000);
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
  } finally {
    clearTimeout(timer);
  }
}

async function fetchViaInnertubeCaptions(videoId: string): Promise<CaptionSegment[]> {
  const clients = [
    { clientName: "WEB", clientVersion: "2.20240405.00.00", hl: "en", gl: "US" },
    { clientName: "MWEB", clientVersion: "2.20240405.01.00", hl: "en", gl: "US" },
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
  }
  return [];
}

export async function GET(request: NextRequest) {
  const videoId = request.nextUrl.searchParams.get("videoId")?.trim();
  if (!videoId) {
    return NextResponse.json({ error: "videoId required" }, { status: 400 });
  }

  try {
    let segments = await fetchViaYoutubeTranscript(videoId);
    if (!segments.length) {
      segments = await fetchViaInnertubeCaptions(videoId);
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

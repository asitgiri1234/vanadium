import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "edge";

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

async function fetchInnertubePlayer(videoId: string) {
  const resp = await fetch(
    `https://youtubei.googleapis.com/youtubei/v1/player?key=${INNERTUBE_KEY}`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "User-Agent":
          "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
      },
      body: JSON.stringify({
        context: {
          client: {
            clientName: "WEB",
            clientVersion: "2.20240405.00.00",
            hl: "en",
            gl: "US",
          },
        },
        videoId,
      }),
      cache: "no-store",
    },
  );
  return resp.json().catch(() => ({}));
}

export async function GET(request: NextRequest) {
  const videoId = request.nextUrl.searchParams.get("videoId")?.trim();
  if (!videoId) {
    return NextResponse.json({ error: "videoId required" }, { status: 400 });
  }

  try {
    const player = await fetchInnertubePlayer(videoId);
    const tracks =
      player?.captions?.playerCaptionsTracklistRenderer?.captionTracks ?? [];

    for (const track of tracks) {
      const lang = String(track.languageCode ?? "");
      if (lang && !lang.startsWith("en")) continue;
      const baseUrl = String(track.baseUrl ?? "");
      if (!baseUrl) continue;

      const captionResp = await fetch(`${baseUrl}&fmt=json3`, {
        headers: {
          "User-Agent":
            "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        },
        cache: "no-store",
      });
      if (!captionResp.ok) continue;
      const segments = parseJson3(await captionResp.text());
      if (segments.length) {
        return NextResponse.json({ segments });
      }
    }

    return NextResponse.json({ segments: [] });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "fetch failed", segments: [] },
      { status: 502 },
    );
  }
}

import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "edge";

const METRIC_PATTERNS: Record<string, RegExp> = {
  viewCount: /"viewCount"\s*:\s*"(\d+)"/,
  lengthSeconds: /"lengthSeconds"\s*:\s*"(\d+)"/,
  likeCount: /"likeCount"\s*:\s*"(\d+)"/,
  commentCount: /"commentCount"\s*:\s*"(\d+)"/,
};

function firstMatch(html: string, pattern: RegExp): number | null {
  const match = pattern.exec(html);
  if (!match) return null;
  const value = Number.parseInt(match[1], 10);
  return Number.isFinite(value) ? value : null;
}

export async function GET(request: NextRequest) {
  const videoId = request.nextUrl.searchParams.get("videoId")?.trim();
  if (!videoId) {
    return NextResponse.json({ error: "videoId required" }, { status: 400 });
  }

  const watchUrls = [
    `https://m.youtube.com/watch?v=${videoId}`,
    `https://www.youtube.com/watch?v=${videoId}`,
  ];

  for (const watchUrl of watchUrls) {
    try {
      const resp = await fetch(watchUrl, {
        headers: {
          "User-Agent":
            "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
          "Accept-Language": "en-US,en;q=0.9",
        },
        cache: "no-store",
      });
      if (!resp.ok) continue;

      const html = await resp.text();
      const metrics: Record<string, number | null> = {};
      for (const [key, pattern] of Object.entries(METRIC_PATTERNS)) {
        metrics[key] = firstMatch(html, pattern);
      }

      if (metrics.lengthSeconds || metrics.viewCount) {
        return NextResponse.json({ ok: true, metrics });
      }
    } catch {
      continue;
    }
  }

  return NextResponse.json({ ok: false, metrics: {} });
}

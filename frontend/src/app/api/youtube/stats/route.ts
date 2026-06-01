import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "edge";

const SOCIALCOUNTS = "https://api.socialcounts.org/youtube-video-live-view-count";

export async function GET(request: NextRequest) {
  const videoId = request.nextUrl.searchParams.get("videoId")?.trim();
  if (!videoId) {
    return NextResponse.json({ error: "videoId required" }, { status: 400 });
  }

  try {
    const resp = await fetch(`${SOCIALCOUNTS}/${videoId}`, {
      headers: {
        Accept: "application/json, text/plain, */*",
        "User-Agent":
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        Referer: "https://socialcounts.org/",
        Origin: "https://socialcounts.org",
      },
      cache: "no-store",
    });
    const data = await resp.json().catch(() => ({}));
    return NextResponse.json({ status: resp.status, data });
  } catch (error) {
    return NextResponse.json(
      { status: 502, error: error instanceof Error ? error.message : "fetch failed" },
      { status: 502 },
    );
  }
}

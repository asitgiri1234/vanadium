import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "edge";

const INNERTUBE_KEY = "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8";
const INNERTUBE_URL = `https://youtubei.googleapis.com/youtubei/v1/player?key=${INNERTUBE_KEY}`;

export async function GET(request: NextRequest) {
  const videoId = request.nextUrl.searchParams.get("videoId")?.trim();
  if (!videoId) {
    return NextResponse.json({ error: "videoId required" }, { status: 400 });
  }

  const payload = {
    context: {
      client: {
        clientName: "MWEB",
        clientVersion: "2.20240405.01.00",
        hl: "en",
        gl: "US",
      },
    },
    videoId,
  };

  try {
    const resp = await fetch(INNERTUBE_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "User-Agent":
          "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        Origin: "https://www.youtube.com",
        Referer: "https://www.youtube.com/",
      },
      body: JSON.stringify(payload),
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

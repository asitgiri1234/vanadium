import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "edge";

function parseIso8601Duration(raw: string): number {
  const match = /^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$/.exec(raw || "");
  if (!match) return 0;
  const hours = Number.parseInt(match[1] || "0", 10);
  const minutes = Number.parseInt(match[2] || "0", 10);
  const seconds = Number.parseInt(match[3] || "0", 10);
  return hours * 3600 + minutes * 60 + seconds;
}

export async function GET(request: NextRequest) {
  const videoId = request.nextUrl.searchParams.get("videoId")?.trim();
  if (!videoId) {
    return NextResponse.json({ error: "videoId required" }, { status: 400 });
  }

  const apiKey = process.env.YOUTUBE_API_KEY?.trim();
  if (!apiKey) {
    return NextResponse.json({ ok: false, reason: "YOUTUBE_API_KEY not configured" });
  }

  try {
    const videoResp = await fetch(
      `https://www.googleapis.com/youtube/v3/videos?part=snippet,statistics,contentDetails&id=${videoId}&key=${apiKey}`,
      { cache: "no-store" },
    );
    if (!videoResp.ok) {
      return NextResponse.json({ ok: false, status: videoResp.status });
    }

    const videoData = await videoResp.json();
    const item = videoData.items?.[0];
    if (!item) {
      return NextResponse.json({ ok: false, reason: "video not found" });
    }

    const snippet = item.snippet || {};
    const stats = item.statistics || {};
    const content = item.contentDetails || {};
    const channelId = snippet.channelId as string | undefined;

    let subscriberCount: number | null = null;
    if (channelId) {
      const channelResp = await fetch(
        `https://www.googleapis.com/youtube/v3/channels?part=statistics&id=${channelId}&key=${apiKey}`,
        { cache: "no-store" },
      );
      if (channelResp.ok) {
        const channelData = await channelResp.json();
        const channelStats = channelData.items?.[0]?.statistics || {};
        subscriberCount = channelStats.subscriberCount
          ? Number.parseInt(String(channelStats.subscriberCount), 10)
          : null;
      }
    }

    const thumbs = snippet.thumbnails || {};
    const thumbnail =
      thumbs.maxres?.url || thumbs.high?.url || thumbs.medium?.url || null;

    return NextResponse.json({
      ok: true,
      metadata: {
        title: snippet.title || null,
        creator: snippet.channelTitle || null,
        creator_url: channelId ? `https://www.youtube.com/channel/${channelId}` : null,
        follower_count: subscriberCount,
        thumbnail,
        views: stats.viewCount ? Number.parseInt(String(stats.viewCount), 10) : 0,
        likes: stats.likeCount ? Number.parseInt(String(stats.likeCount), 10) : null,
        comments: stats.commentCount
          ? Number.parseInt(String(stats.commentCount), 10)
          : null,
        duration_seconds: parseIso8601Duration(content.duration || ""),
        upload_date: snippet.publishedAt ? String(snippet.publishedAt).slice(0, 10) : null,
      },
    });
  } catch (error) {
    return NextResponse.json(
      {
        ok: false,
        error: error instanceof Error ? error.message : "fetch failed",
      },
      { status: 502 },
    );
  }
}

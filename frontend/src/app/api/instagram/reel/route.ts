import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const IG_APP_ID = "936619743392459";

function decodeUrl(raw: string): string {
  let url = raw.replace(/\\\//g, "/");
  try {
    url = JSON.parse(`"${url.replace(/"/g, '\\"')}"`) as string;
  } catch {
    /* keep literal */
  }
  return url;
}

function extractUrls(html: string): { videoUrls: string[]; thumbUrls: string[] } {
  const videoUrls: string[] = [];
  const thumbUrls: string[] = [];
  const patterns = [
    /"video_url"\s*:\s*"([^"]+)"/g,
    /"playback_url"\s*:\s*"([^"]+)"/g,
    /"contentUrl"\s*:\s*"([^"]+)"/g,
  ];
  for (const re of patterns) {
    for (const match of html.matchAll(re)) {
      const u = decodeUrl(match[1]);
      if (u.startsWith("http") && !videoUrls.includes(u)) videoUrls.push(u);
    }
  }
  for (const match of html.matchAll(/"display_url"\s*:\s*"([^"]+)"/g)) {
    const u = decodeUrl(match[1]);
    if (u.startsWith("http") && !thumbUrls.includes(u)) thumbUrls.push(u);
  }
  return { videoUrls, thumbUrls };
}

async function fetchOembed(reelUrl: string) {
  const resp = await fetch(
    `https://www.instagram.com/api/v1/oembed/?url=${encodeURIComponent(reelUrl)}`,
    {
      headers: {
        "User-Agent":
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "x-ig-app-id": IG_APP_ID,
        Accept: "application/json",
      },
      cache: "no-store",
    },
  );
  if (!resp.ok) return null;
  return resp.json().catch(() => null);
}

function extractEngagement(html: string): {
  like_count: number | null;
  comment_count: number | null;
  view_count: number | null;
  duration_seconds: number | null;
} {
  const pick = (patterns: RegExp[]): number | null => {
    for (const re of patterns) {
      const m = html.match(re);
      if (m?.[1]) return parseInt(m[1], 10);
    }
    return null;
  };
  const dur = html.match(/"video_duration"\s*:\s*([\d.]+)/);
  return {
    like_count: pick([
      /"like_count"\s*:\s*(\d+)/,
      /"edge_media_preview_like"\s*:\s*\{\s*"count"\s*:\s*(\d+)/,
    ]),
    comment_count: pick([
      /"comment_count"\s*:\s*(\d+)/,
      /"edge_media_to_(?:parent_)?comment"\s*:\s*\{\s*"count"\s*:\s*(\d+)/,
    ]),
    view_count: pick([/"play_count"\s*:\s*(\d+)/]),
    duration_seconds: dur?.[1] ? Math.round(parseFloat(dur[1])) : null,
  };
}

async function fetchWatchHtml(reelUrl: string): Promise<string> {
  try {
    const resp = await fetch(reelUrl.split("?")[0].replace(/\/$/, ""), {
      headers: {
        "User-Agent":
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
      },
      cache: "no-store",
    });
    if (resp.ok) return resp.text();
  } catch {
    /* ignore */
  }
  return "";
}

async function fetchEmbedHtml(reelUrl: string): Promise<string> {
  const clean = reelUrl.split("?")[0].replace(/\/$/, "");
  for (const suffix of ["/embed/captioned/", "/embed/"]) {
    try {
      const resp = await fetch(`${clean}${suffix}`, {
        headers: {
          "User-Agent":
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        },
        cache: "no-store",
      });
      if (resp.ok) return resp.text();
    } catch {
      continue;
    }
  }
  return "";
}

export async function GET(request: NextRequest) {
  const reelUrl = request.nextUrl.searchParams.get("url")?.trim();
  if (!reelUrl || !reelUrl.includes("instagram.com")) {
    return NextResponse.json({ error: "url required" }, { status: 400 });
  }

  try {
    const oembed = await fetchOembed(reelUrl);
    const embedHtml = await fetchEmbedHtml(reelUrl);
    const watchHtml = await fetchWatchHtml(reelUrl);
    const combinedHtml = `${embedHtml}\n${watchHtml}`;

    const { videoUrls, thumbUrls } = extractUrls(combinedHtml);
    let engagement = extractEngagement(combinedHtml);
    let mediaTitle: string | null = null;

    try {
      const mediaUrl = new URL("/api/instagram/media", request.url);
      mediaUrl.searchParams.set("url", reelUrl);
      const mediaResp = await fetch(mediaUrl.toString(), { cache: "no-store" });
      if (mediaResp.ok) {
        const media = await mediaResp.json();
        if (media?.ok) {
          engagement = {
            like_count: media.like_count ?? engagement.like_count,
            comment_count: media.comment_count ?? engagement.comment_count,
            view_count: media.view_count ?? engagement.view_count,
            duration_seconds: media.duration_seconds ?? engagement.duration_seconds,
          };
          mediaTitle = media.title ?? null;
          for (const u of media.video_urls ?? []) {
            if (u && !videoUrls.includes(u)) videoUrls.push(u);
          }
          for (const u of media.thumbnail_urls ?? []) {
            if (u && !thumbUrls.includes(u)) thumbUrls.push(u);
          }
        }
      }
    } catch {
      /* ignore */
    }

    const title = oembed?.title ?? mediaTitle ?? null;
    const creator = oembed?.author_name ?? null;
    const creatorUrl = oembed?.author_url ?? null;
    const thumbnail = oembed?.thumbnail_url ?? thumbUrls[0] ?? null;

    return NextResponse.json({
      ok: Boolean(
        title ||
          thumbnail ||
          videoUrls.length ||
          engagement.like_count != null ||
          engagement.comment_count != null,
      ),
      title,
      creator,
      creator_url: creatorUrl,
      thumbnail_url: thumbnail,
      video_urls: videoUrls,
      thumbnail_urls: thumbUrls,
      like_count: engagement.like_count,
      comment_count: engagement.comment_count,
      view_count: engagement.view_count,
      duration_seconds: engagement.duration_seconds,
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

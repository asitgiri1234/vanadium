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
    const html = await fetchEmbedHtml(reelUrl);
    const { videoUrls, thumbUrls } = extractUrls(html);

    const title = oembed?.title ?? null;
    const creator = oembed?.author_name ?? null;
    const creatorUrl = oembed?.author_url ?? null;
    const thumbnail =
      oembed?.thumbnail_url ?? thumbUrls[0] ?? null;

    return NextResponse.json({
      ok: Boolean(title || thumbnail || videoUrls.length),
      title,
      creator,
      creator_url: creatorUrl,
      thumbnail_url: thumbnail,
      video_urls: videoUrls,
      thumbnail_urls: thumbUrls,
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

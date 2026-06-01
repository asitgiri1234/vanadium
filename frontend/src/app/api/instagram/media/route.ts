import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const IG_APP_ID = "936619743392459";
const ALPHABET =
  "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";

function shortcodeToPk(shortcode: string): string | null {
  try {
    let pk = BigInt(0);
    for (const char of shortcode) {
      const idx = ALPHABET.indexOf(char);
      if (idx < 0) return null;
      pk = pk * BigInt(64) + BigInt(idx);
    }
    return pk.toString();
  } catch {
    return null;
  }
}

function extractShortcode(url: string): string | null {
  const match = url.match(/\/(?:reel|reels|p|tv)\/([A-Za-z0-9_-]+)/);
  return match?.[1] ?? null;
}

function igHeaders(referer: string): Record<string, string> {
  const headers: Record<string, string> = {
    "User-Agent":
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "x-ig-app-id": IG_APP_ID,
    Accept: "*/*",
    "x-requested-with": "XMLHttpRequest",
    Referer: referer,
  };
  const cookieEnv = process.env.INSTAGRAM_COOKIE?.trim();
  if (cookieEnv) {
    headers.Cookie = cookieEnv;
    const csrf = cookieEnv
      .split(";")
      .map((p) => p.trim())
      .find((p) => p.startsWith("csrftoken="));
    if (csrf) headers["x-csrftoken"] = csrf.split("=")[1];
  }
  return headers;
}

export async function GET(request: NextRequest) {
  const reelUrl = request.nextUrl.searchParams.get("url")?.trim();
  if (!reelUrl || !reelUrl.includes("instagram.com")) {
    return NextResponse.json({ error: "url required" }, { status: 400 });
  }

  const shortcode = extractShortcode(reelUrl);
  if (!shortcode) {
    return NextResponse.json({ ok: false, error: "invalid url" }, { status: 400 });
  }

  const mediaPk = shortcodeToPk(shortcode);
  if (!mediaPk) {
    return NextResponse.json({ ok: false, error: "shortcode decode failed" }, { status: 400 });
  }

  const cleanUrl = reelUrl.split("?")[0].replace(/\/$/, "");

  try {
    const resp = await fetch(
      `https://www.instagram.com/api/v1/media/${mediaPk}/info/`,
      { headers: igHeaders(cleanUrl), cache: "no-store" },
    );
    if (!resp.ok) {
      return NextResponse.json({
        ok: false,
        error: `instagram HTTP ${resp.status}`,
        shortcode,
      });
    }

    const data = await resp.json();
    const item = data?.items?.[0];
    if (!item) {
      return NextResponse.json({ ok: false, error: "no items", shortcode });
    }

    const likeCount =
      item.like_count ?? item.edge_media_preview_like?.count ?? null;
    const commentCount =
      item.comment_count ??
      item.edge_media_to_parent_comment?.count ??
      item.edge_media_to_comment?.count ??
      null;
    const viewCount =
      item.play_count ?? item.view_count ?? item.video_view_count ?? null;

    const videoUrls: string[] = [];
    for (const v of item.video_versions ?? []) {
      if (v?.url && !videoUrls.includes(v.url)) videoUrls.push(v.url);
    }

    const thumbUrls: string[] = [];
    for (const c of item.image_versions2?.candidates ?? []) {
      if (c?.url && !thumbUrls.includes(c.url)) thumbUrls.push(c.url);
    }

    const username = item.user?.username;
    const caption = (item.caption?.text ?? "").trim();

    return NextResponse.json({
      ok: Boolean(
        likeCount != null ||
          commentCount != null ||
          videoUrls.length ||
          caption,
      ),
      shortcode,
      like_count: likeCount,
      comment_count: commentCount,
      view_count: viewCount,
      duration_seconds: item.video_duration
        ? Math.round(Number(item.video_duration))
        : null,
      video_urls: videoUrls,
      thumbnail_urls: thumbUrls,
      thumbnail_url: thumbUrls[0] ?? null,
      title: caption ? caption.slice(0, 300) : null,
      creator: item.user?.full_name ?? username ?? null,
      creator_url: username ? `https://www.instagram.com/${username}/` : null,
    });
  } catch (error) {
    return NextResponse.json(
      {
        ok: false,
        error: error instanceof Error ? error.message : "fetch failed",
        shortcode,
      },
      { status: 502 },
    );
  }
}

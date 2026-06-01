import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const IG_APP_ID = "936619743392459";

async function followersFromWebProfile(handle: string): Promise<number | null> {
  const resp = await fetch(
    `https://www.instagram.com/api/v1/users/web_profile_info/?username=${encodeURIComponent(handle)}`,
    {
      headers: {
        "User-Agent":
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "x-ig-app-id": IG_APP_ID,
        Accept: "*/*",
      },
      cache: "no-store",
    },
  );
  if (!resp.ok) return null;

  const data = await resp.json().catch(() => ({}));
  const count = data?.data?.user?.edge_followed_by?.count;
  return typeof count === "number" && count > 0 ? count : null;
}

async function followersFromProfileHtml(handle: string): Promise<number | null> {
  const resp = await fetch(`https://www.instagram.com/${encodeURIComponent(handle)}/`, {
    headers: {
      "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    },
    cache: "no-store",
  });
  if (!resp.ok) return null;

  const html = await resp.text();
  for (const pattern of [
    /"edge_followed_by"\s*:\s*\{\s*"count"\s*:\s*(\d+)/,
    /"follower_count"\s*:\s*(\d+)/,
  ]) {
    const match = html.match(pattern);
    if (match) {
      const n = parseInt(match[1], 10);
      if (n > 0) return n;
    }
  }
  return null;
}

export async function GET(request: NextRequest) {
  const handle = request.nextUrl.searchParams.get("handle")?.trim().replace(/^@/, "");
  if (!handle) {
    return NextResponse.json({ error: "handle required" }, { status: 400 });
  }

  try {
    let followerCount = await followersFromWebProfile(handle);
    if (!followerCount) {
      followerCount = await followersFromProfileHtml(handle);
    }

    return NextResponse.json({
      ok: Boolean(followerCount),
      handle,
      follower_count: followerCount,
      creator_url: `https://www.instagram.com/${handle}/`,
    });
  } catch (error) {
    return NextResponse.json(
      {
        ok: false,
        error: error instanceof Error ? error.message : "fetch failed",
        follower_count: null,
      },
      { status: 502 },
    );
  }
}

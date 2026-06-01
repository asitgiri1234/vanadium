import { NextResponse } from "next/server";
import { resolveBackendUrlFromEnv } from "@/lib/backend-url";

export const dynamic = "force-dynamic";

/** Runtime backend URL for the browser (reads Vercel env without a rebuild). */
export async function GET() {
  return NextResponse.json({ apiUrl: resolveBackendUrlFromEnv() });
}

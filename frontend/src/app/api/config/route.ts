import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

/** Runtime backend URL for the browser (reads Vercel env without a rebuild). */
export async function GET() {
  const apiUrl = (
    process.env.API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://localhost:8000"
  ).replace(/\/$/, "");

  return NextResponse.json({ apiUrl });
}

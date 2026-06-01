/** Default Render backend when env vars are missing (Vercel / local without .env). */
export const PRODUCTION_API_URL = "https://vanadium-1.onrender.com";

export function normalizeApiUrl(url: string): string {
  return url.replace(/\/$/, "");
}

export function isLocalApiUrl(url: string): boolean {
  return url.includes("localhost") || url.startsWith("http://127.0.0.1");
}

/** Server-side: resolve backend URL from env, with sensible production fallback. */
export function resolveBackendUrlFromEnv(): string {
  const fromEnv = process.env.API_URL || process.env.NEXT_PUBLIC_API_URL;
  if (fromEnv) return normalizeApiUrl(fromEnv);

  // Vercel / production builds should never fall back to localhost.
  if (process.env.VERCEL || process.env.NODE_ENV === "production") {
    return PRODUCTION_API_URL;
  }

  return "http://localhost:8000";
}

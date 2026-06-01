# Vanadium

> **AI-powered content intelligence for creators.** Drop in two social videos
> (YouTube / Instagram Reels), and Vanadium explains *why* one outperforms the
> other — with evidence-backed answers, source citations, and concrete
> recommendations to improve future content.

Vanadium behaves like an AI **content strategist**, not a chatbot. It ingests
both videos, extracts transcripts + metadata, computes engagement, indexes
everything in a vector store, and answers natural-language questions over a
RAG pipeline with conversation memory and streaming responses.

---

## ✨ What it does

- **Compare two videos** side by side: views, likes, comments, engagement rate,
  hashtags, creator + follower count, thumbnails.
- **Ask anything**, e.g.:
  - *Why did Video A get more engagement than Video B?*
  - *Compare the hooks used in the first 5 seconds.*
  - *Which video had a stronger CTA?*
  - *Suggest improvements for Video B based on what worked in Video A.*
- **Evidence-backed**: every answer cites transcript chunks (video + timestamp).
- **Memory**: ask *"which one was stronger?"* after *"compare the hooks"* — it
  understands context.

## 🧱 Tech Stack

| Layer | Tech |
|---|---|
| Frontend | Next.js (App Router), TypeScript, TailwindCSS, shadcn-style UI |
| Backend | FastAPI |
| AI orchestration | LangChain |
| Embeddings | OpenAI `text-embedding-3-small` |
| Vector DB | ChromaDB (persistent) |
| LLM | Groq (`llama-3.3-70b`) or OpenAI `gpt-4o-mini` |
| Vision | Groq Llama 4 Scout (on-screen text + scene) |
| Transcripts | YouTube captions (Vercel proxy) → Groq Whisper fallback; IG Reels → Groq Whisper |

See **[ARCHITECTURE.md](./ARCHITECTURE.md)** for the full design, API contract,
data model, RAG pipeline, and roadmap.

**Going live?** See **[DEPLOY.md](./DEPLOY.md)** for Vercel + Docker backend deployment.

---

## 🚀 Quickstart

### 1. Backend

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env          # then add your OPENAI_API_KEY
python run.py                 # serves on http://localhost:8000
```

> No `OPENAI_API_KEY`? Vanadium still runs — it falls back to a deterministic
> extractive analyst and a local hash-based embedder so you can demo the full
> flow offline.

### 2. Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local   # NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev                        # serves on http://localhost:3000
```

Open <http://localhost:3000>, paste two video URLs, hit **Analyze**, then chat.

---

## 🔌 API summary

| Method | Path | Purpose |
|---|---|---|
| `GET`  | `/api/health` | liveness + capability probe |
| `POST` | `/api/ingest` | ingest two videos → analysis snapshot |
| `GET`  | `/api/analysis/{id}` | fetch a saved analysis |
| `POST` | `/api/chat` | streaming RAG chat (SSE) with citations |

Full request/response shapes live in [ARCHITECTURE.md](./ARCHITECTURE.md#3-api-design).

---

## 📁 Project layout

```
vanadium/
├── backend/    # FastAPI + LangChain + ChromaDB RAG service
└── frontend/   # Next.js dashboard + streaming chat
```

## ⚠️ Notes

- **Transcription** uses **Groq Whisper** (`whisper-large-v3-turbo`) when
  `ENABLE_WHISPER=true` — same `GROQ_API_KEY` as chat/vision. Instagram Reels
  always go through audio → Groq; YouTube tries captions first, then Groq.
  See [DEPLOY.md](./DEPLOY.md) for env vars.
- **Instagram** often needs a Netscape `cookies.txt` from a logged-in session
  on production (Render datacenter IPs are blocked). Export steps are in
  [DEPLOY.md § Instagram session cookies](./DEPLOY.md#instagram-session-cookies-cookiestxt).
- The analysis + memory store is in-memory by default; swap for Redis/Postgres
  for multi-instance deployments.

---

## 🐛 Production bugs & lessons learned

This section documents real failures discovered when moving Vanadium from local
dev to **Render (backend)** + **Vercel (frontend)**. Local development often
masks these because your home IP is not blocked the same way datacenter IPs are.

### 1. Render datacenter IPs are blocked by YouTube & Instagram

**Symptom:** Metadata, transcripts, and downloads work on your laptop but return
empty data, `403`, or timeouts on Render.

**Root cause:** YouTube and Instagram aggressively rate-limit or block cloud
provider IP ranges (Render, Railway, Fly.io, AWS, etc.). Direct calls to
`youtube.com`, watch-page HTML scraping, `yt-dlp` full downloads, and
SocialCounts often fail from the backend container.

**What we built:**

| Data | Works from Render? | Solution |
|------|-------------------|----------|
| YT views / likes | Partially | Return YouTube Dislike API + innertube via `googleapis.com` |
| YT comments | ❌ direct | Vercel proxy → SocialCounts (`/api/youtube/stats`) |
| YT duration / subscribers | ❌ scrape | `YOUTUBE_API_KEY` (Data API v3) on Render **and** Vercel metadata proxy |
| YT transcripts | ❌ direct | Vercel Node proxy (`/api/youtube/transcript`) + Groq Whisper fallback |
| YT visual frames | ❌ yt-dlp | `i.ytimg.com` thumbnail/storyboard URLs (no download) |
| IG followers / views | ❌ direct | `cookies.txt` + Vercel IG profile proxy (`/api/instagram/profile`) |
| IG audio / visual | ❌ full download | Direct CDN URL extraction + Groq Whisper / vision on thumbnails |

Set `FRONTEND_PROXY_URL=https://<your-vercel-app>.vercel.app` on Render so the
backend can call these proxy routes.

---

### 2. YouTube Data API key does **not** unlock transcripts

**Symptom:** `YOUTUBE_API_KEY` fixes duration and subscriber counts but
transcripts stay empty.

**Root cause:** The Data API `captions.list` endpoint works with an API key, but
`captions.download` requires **OAuth user consent** — an API key alone cannot
download caption text.

**Fix / alternatives (layered):**

1. **Vercel transcript proxy** — runs `youtube-transcript` npm + innertube on a
   non-datacenter IP (`frontend/src/app/api/youtube/transcript/route.ts`, Node
   runtime, not Edge).
2. **Groq Whisper** — download audio (yt-dlp or direct CDN URL) →
   `whisper-large-v3-turbo` when captions return empty (`ENABLE_WHISPER=true`,
   `WHISPER_PROVIDER=groq`).
3. **Supadata** (optional paid) — set `SUPADATA_API_KEY` as another cloud
   fallback.

**Lesson:** “Works yesterday locally” ≠ “works in production.” Local backend
uses Python `youtube-transcript-api` successfully; Render must use the Vercel
proxy or Whisper.

---

### 3. Vercel Edge transcript route returned empty / hung

**Symptom:** Production `GET /api/youtube/transcript?videoId=…` timed out (60s+)
or returned `{ segments: [] }`.

**Root cause:** An earlier Edge-runtime route tried to scrape the YouTube watch
page HTML for `captionTracks`. That approach is fragile, slow, and often blocked.

**Fix:** Switched to **`runtime = "nodejs"`** and the `youtube-transcript` npm
package (innertube fallback). Must redeploy **Vercel** after changes — Render
alone is not enough.

---

### 4. Instagram “0 followers” AI hallucination

**Symptom:** Strategist summary claimed things like *“Video B's creator has only
0 followers”* and *“0 views”* even for established creators.

**Root cause:** Multiple compounding issues:

1. `follower_count` defaulted to `int = 0`, so **unknown = zero** in the schema.
2. LLM prompts formatted `{follower_count:,}` → literal **“0 followers”**.
3. Instagram often **hides** view counts and follower data without a logged-in
   session — scrapers return nothing, which was stored as `0`.
4. Engagement rate computed as `0.0%` when `views == 0`, reinforcing the bad
   narrative.

**Fix:**

- `follower_count` is now `Optional[int] = None` when unknown.
- `metadata_display.py` formats unknowns as *“unknown (Instagram often hides…”*
  not zero.
- System + RAG prompts explicitly forbid interpreting hidden metrics as zero
  reach.
- UI only shows followers when `follower_count > 0`.

**Lesson:** Never use `0` as a sentinel for “missing” in LLM-facing metadata.

---

### 5. Visual analysis showed “No Visual Data” on production

**Symptoms:** Transcripts empty, visual panel empty for both YouTube and
Instagram on Render despite `ENABLE_VISUAL=true`.

**Root causes found:**

1. **Missing import** — `visual_service.py` referenced `extract_youtube_id`
   without importing it, breaking the cloud thumbnail path silently.
2. **No cloud fallback for Instagram** — visual pipeline tried full yt-dlp video
   download, which fails on Render.
3. **Vision requires Groq** — `ENABLE_VISUAL` + `GROQ_API_KEY` +
   `GROQ_VISION_MODEL`; OCR-only fallback is off by default.

**Fix:**

- YouTube cloud: download frames from `i.ytimg.com` (no yt-dlp).
- Instagram cloud: CDN thumbnail URLs via `instagram_media.py`.
- Groq Llama 4 Scout reads scene + on-screen text from sampled frames.

---

### 6. Accidental regex deletion caused 500 on debug endpoint (v0.3.1 hotfix)

**Symptom:** `GET /api/debug/youtube-metadata` returned **500 Internal Server
Error** after a refactor.

**Root cause:** `_VIEW_RE` regex was accidentally removed from
`youtube_innertube.py` during a merge; downstream parsing crashed.

**Fix:** Restored `_VIEW_RE` in commit `1270726`.

**Lesson:** Always smoke-test debug/diagnostic routes after metadata refactors.

---

### 7. Instagram session cookies required for reliable enrichment

**Symptom:** Follower counts, view counts, reel audio downloads, and profile
API calls fail on Render even when they work in a logged-in browser.

**Root cause:** Instagram’s authenticated API path (used by yt-dlp for play
counts and profile data) requires session cookies. Datacenter IPs without cookies
get partial/empty JSON.

**Fix:** Export Netscape `cookies.txt` from a **throwaway** Instagram account and
set `INSTAGRAM_COOKIES_FILE` on Render (Secret File at
`/etc/secrets/instagram_cookies.txt`). Full steps in
[DEPLOY.md](./DEPLOY.md#instagram-session-cookies-cookiestxt).

**Do not** commit cookies to git or use your primary Instagram account.

---

### 8. Environment variables must be set on **both** Render and Vercel

**Symptom:** Duration/subscribers fixed on backend but still `0` in some paths.

**Root cause:** Vercel `/api/youtube/metadata` proxy reads `YOUTUBE_API_KEY`
from **Vercel** env, not Render. Each platform only sees its own env vars.

**Checklist:**

| Variable | Render | Vercel |
|----------|--------|--------|
| `GROQ_API_KEY` | ✅ | — |
| `YOUTUBE_API_KEY` | ✅ | ✅ (metadata proxy) |
| `FRONTEND_PROXY_URL` | ✅ | — |
| `NEXT_PUBLIC_API_URL` | — | ✅ |
| `INSTAGRAM_COOKIES_FILE` | ✅ | — |

---

### 9. Stale analysis data after fixes

**Symptom:** UI/prompts still mention “0 followers” after deploying fixes.

**Root cause:** Ingestion embeds metadata cards into ChromaDB at analyze-time.
Old analyses retain pre-fix `follower_count: 0` in the vector store.

**Fix:** **Re-run Analyze** on the same URLs after deploying. There is no
automatic backfill of persisted analyses.

---

### Quick production smoke test

```bash
# Backend health
curl https://<render-url>/api/health

# Vercel transcript proxy (should return segments > 0 for a popular video)
curl "https://<vercel-url>/api/youtube/transcript?videoId=dQw4w9WgXcQ"

# Debug metadata (optional)
curl "https://<render-url>/api/debug/youtube-metadata?url=https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

See [DEPLOY.md](./DEPLOY.md) for full deployment and troubleshooting.

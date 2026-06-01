# Vanadium — Production Deployment

Vanadium is a **split deployment**: Next.js on **Vercel**, FastAPI on a **container host with persistent disk**.

```
Browser ──► Vercel (frontend)     NEXT_PUBLIC_API_URL
         └──► Render/Railway/Fly (backend)  GROQ_API_KEY, CORS_ORIGINS, /data volume
```

---

## Prerequisites

| Item | Where |
|------|-------|
| Groq API key | [console.groq.com](https://console.groq.com) → backend env |
| OpenAI API key (recommended) | Embeddings only — improves RAG retrieval |
| GitHub repo | `asitgiri1234/vanadium` |
| Vercel account | Free tier works for frontend |
| Render account (or Railway/Fly) | Backend with ≥4 GB RAM, persistent disk |

---

## 1. Deploy backend (Render — recommended)

### Option A: Blueprint (`render.yaml`)

1. Push this repo to GitHub.
2. In [Render Dashboard](https://dashboard.render.com) → **New** → **Blueprint**.
3. Connect the repo; Render reads [`render.yaml`](render.yaml).
4. Set secret env vars in the dashboard:
   - `GROQ_API_KEY`
   - `OPENAI_API_KEY` (optional but recommended)
   - `CORS_ORIGINS` — your Vercel URL, e.g. `https://vanadium.vercel.app`
5. Deploy. Note the public URL, e.g. `https://vanadium-api.onrender.com`.

The blueprint mounts a **2 GB disk** at `/data` for ChromaDB and analysis JSON.

### Option B: Manual Web Service (what you used)

Render failed with **"Exited with status 1 while building"** if **Runtime** is set to Node/Python instead of Docker — there is no app at the repo root for native builds.

**Correct settings in Render → New Web Service:**

| Setting | Value |
|---------|-------|
| **Repository** | `asitgiri1234/vanadium` |
| **Branch** | `main` |
| **Root Directory** | *(leave blank — repo root)* |
| **Runtime** | **Docker** ← critical |
| **Dockerfile Path** | `Dockerfile` *(repo root — auto-detected)* or `backend/Dockerfile` |
| **Health Check Path** | `/api/health` |

Then add env vars:

```env
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_...
CORS_ORIGINS=https://your-app.vercel.app
CHROMA_PERSIST_DIR=/data/chroma
ANALYSIS_PERSIST_DIR=/data/analyses
ENABLE_WHISPER=true
WHISPER_PROVIDER=groq
GROQ_WHISPER_MODEL=whisper-large-v3-turbo
ENABLE_VISUAL=true
```

**Transcription (Groq Whisper):** Uses the same `GROQ_API_KEY` — no local PyTorch needed.

| Platform | Flow |
|----------|------|
| **Instagram Reels** | Download reel audio → Groq `whisper-large-v3-turbo` |
| **YouTube** | Try captions (Vercel proxy) → if empty, download audio → Groq Whisper |

Set `ENABLE_WHISPER=true` and `WHISPER_PROVIDER=groq` on Render.

**Free instance limits:**
- Persistent disk is **not available** on Free — analyses reset on redeploy. Upgrade to Starter+ and mount `/data` for persistence.
- Visual analysis (`ENABLE_VISUAL=true`) downloads reel video + calls Groq vision — usually fine on Free; disable if you hit OOM.

**Optional embeddings (recommended):**

```env
OPENAI_API_KEY=sk-...
```

### Local Docker test

```bash
cd backend
docker build -t vanadium-api .
docker run --rm -p 8000:8000 \
  -v vanadium-data:/data \
  -e GROQ_API_KEY=gsk_... \
  -e LLM_PROVIDER=groq \
  -e CORS_ORIGINS=http://localhost:3000 \
  -e ENABLE_WHISPER=true \
  -e WHISPER_PROVIDER=groq \
  -e ENABLE_VISUAL=true \
  vanadium-api
curl http://localhost:8000/api/health
```

---

## 2. Deploy frontend (Vercel)

Vercel detects this monorepo as multi-service. The root [`vercel.json`](vercel.json) deploys **frontend only** — do **not** add the backend service to Vercel (FastAPI needs Render/Railway instead).

1. [vercel.com/new](https://vercel.com/new) → import GitHub repo.
2. Vercel reads `vercel.json` at the repo root (frontend at `/`, Next.js).
3. **Environment Variables** (required before first deploy):

```env
NEXT_PUBLIC_API_URL=https://vanadium-api.onrender.com
```

5. Deploy. Your app will be at `https://<project>.vercel.app`.

6. Update backend `CORS_ORIGINS` to include the Vercel URL if not already set, then redeploy/restart backend.

### Vercel CLI (optional)

```bash
cd frontend
npx vercel --prod
# Set NEXT_PUBLIC_API_URL in Vercel project settings first
```

---

## 3. Smoke tests

From repo root:

```bash
# Health + CORS only
python scripts/smoke_test.py
API_URL=https://vanadium-api.onrender.com FRONTEND_ORIGIN=https://your-app.vercel.app python scripts/smoke_test.py

# Full YouTube ingest + chat (slow)
API_URL=https://vanadium-api.onrender.com \
TEST_YT_URL_A="https://www.youtube.com/watch?v=..." \
TEST_YT_URL_B="https://www.youtube.com/watch?v=..." \
python scripts/smoke_test.py
```

Manual checklist:

- [ ] `GET /api/health` → 200
- [ ] `/analyze` on Vercel loads without CORS errors
- [ ] Analyze two YouTube URLs completes
- [ ] Chat streams tokens (SSE)
- [ ] Instagram reel: set `INSTAGRAM_COOKIES_FILE` if metadata/transcripts fail

---

## Environment variable reference

### Vercel (frontend)

| Variable | Required | Example |
|----------|----------|---------|
| `NEXT_PUBLIC_API_URL` | Yes | `https://vanadium-api.onrender.com` |

### Backend

| Variable | Required | Notes |
|----------|----------|-------|
| `GROQ_API_KEY` | Yes (Groq mode) | Chat, comparison, vision |
| `LLM_PROVIDER` | Yes | `groq` |
| `CORS_ORIGINS` | Yes in prod | Comma-separated Vercel/custom domains |
| `CHROMA_PERSIST_DIR` | Yes in prod | `/data/chroma` with volume |
| `ANALYSIS_PERSIST_DIR` | Yes in prod | `/data/analyses` with volume |
| `OPENAI_API_KEY` | Recommended | Embeddings only |
| `ENABLE_WHISPER` | Yes for IG + YT fallback | `true` — Groq Whisper (`GROQ_API_KEY`) |
| `WHISPER_PROVIDER` | Yes with Whisper | `groq` (not `local`) |
| `GROQ_WHISPER_MODEL` | Optional | `whisper-large-v3-turbo` |
| `ENABLE_VISUAL` | For frame analysis | `true` |
| `INSTAGRAM_COOKIES_FILE` | Recommended for IG | Netscape `cookies.txt` path on Render |

---

## Instagram session cookies (`cookies.txt`)

Vanadium uses a **Netscape-format cookies file** so yt-dlp and profile API calls act as a logged-in browser. Use a **throwaway Instagram account** — never your main account.

### Step 1 — Create / log into throwaway account

1. In Chrome or Edge, open a **new profile** (optional but cleaner): `Settings → Profiles → Add profile`.
2. Go to [instagram.com](https://www.instagram.com) and log in with your throwaway account.
3. Confirm you can open a public profile and see follower counts in the browser.

### Step 2 — Install cookie export extension

**Chrome / Edge (recommended):**

1. Open the extension store and search **“Get cookies.txt LOCALLY”** (by kairi003).
   - Chrome: [Chrome Web Store listing](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
2. Click **Add to Chrome** / **Get**.

> Use “LOCALLY” — it exports on your machine only. Avoid extensions that upload cookies to third-party servers.

**Firefox alternative:** **“cookies.txt”** by erik (exports Netscape format).

### Step 3 — Export cookies for Instagram

1. While logged into Instagram, go to **any** `https://www.instagram.com/...` page.
2. Click the **Get cookies.txt LOCALLY** extension icon.
3. Click **Export** / **Download** — save as `instagram_cookies.txt`.
4. Open the file in a text editor. It should look like:

```text
# Netscape HTTP Cookie File
.instagram.com	TRUE	/	TRUE	1735689600	sessionid	xxxx...
.instagram.com	TRUE	/	TRUE	1735689600	csrftoken	xxxx...
```

5. **Required cookies:** at minimum you should see `sessionid` and `csrftoken` for `.instagram.com`. If those lines are missing, export again while on instagram.com and still logged in.

### Step 4 — Local development

1. Save the file somewhere **outside git**, e.g. `backend/secrets/instagram_cookies.txt`.
2. Add to `backend/.env`:

```env
INSTAGRAM_COOKIES_FILE=./secrets/instagram_cookies.txt
```

3. Restart the backend. Logs should show: `yt-dlp: using cookies file ...`

### Step 5 — Production (Render)

**Option A — Secret file (recommended)**

1. Render dashboard → your **vanadium-api** service → **Environment**.
2. Scroll to **Secret Files** → **Add Secret File**.
3. **Filename:** `instagram_cookies.txt`
4. Paste the **entire contents** of your exported file.
5. Add environment variable:

```env
INSTAGRAM_COOKIES_FILE=/etc/secrets/instagram_cookies.txt
```

6. **Save Changes** → Render redeploys automatically.

**Vercel (optional but recommended for IG likes/comments on production)**

Add the same session as a single header string so `/api/instagram/media` can authenticate from Vercel’s IP:

```env
INSTAGRAM_COOKIE=sessionid=YOUR_SESSION_ID; csrftoken=YOUR_CSRF_TOKEN
```

Vercel → Project → Settings → Environment Variables → add for **Production**, then redeploy the frontend.

### Step 6 — Verify

1. Re-run an Instagram reel analysis on production.
2. Check Render logs for `Instagram followers for @handle` or `yt-dlp: using cookies file`.
3. Follower count should appear on the video card (not blank); transcripts should populate via Groq Whisper.

### Cookie hygiene

| Do | Don't |
|----|-------|
| Use a throwaway IG account | Use your personal/business account |
| Re-export every **4–8 weeks** (sessions expire) | Commit `cookies.txt` to GitHub |
| Rotate if IG forces re-login | Share the file publicly |

---

## Platform notes

| Constraint | Detail |
|------------|--------|
| Request timeout | Ingest can take several minutes; use Render Standard+ or increase timeout |
| Memory | Whisper + Chroma + PyTorch → plan **≥4 GB RAM** |
| Single instance | Do not scale to multiple replicas without external DB/queue |
| Image size | ~2–4 GB (PyTorch + Whisper); first deploy is slow |
| HTTPS | Frontend is HTTPS; backend must be HTTPS too (Render provides this) |

---

## Troubleshooting

**CORS error in browser**  
Add your exact Vercel origin to `CORS_ORIGINS` on the backend (no trailing slash).

**Chat/ingest hits localhost:8000**  
Rebuild Vercel after setting `NEXT_PUBLIC_API_URL` — it is baked in at build time.

**502 / timeout on Analyze**  
Backend plan too small or cold start; upgrade RAM or disable Whisper for YouTube-only demos.

**Render build fails immediately ("status 1")**  
Runtime is not Docker. Delete the service, recreate with **Runtime → Docker**. Do not use Node or Python native runtime.

**Instagram views hidden / 0 followers / no transcript**  
Set `INSTAGRAM_COOKIES_FILE` (see [Instagram session cookies](#instagram-session-cookies-cookiestxt)). Ensure `ENABLE_WHISPER=true` and `GROQ_API_KEY` is set for reel audio → Groq Whisper.

**YouTube transcript empty on production**  
Set `SERP_API_KEY` (SerpApi [YouTube Video Transcript](https://serpapi.com/youtube-video-transcript)) — tried first on Render. Fallbacks: Innertube captions, Vercel proxy, Groq Whisper. Confirm `ENABLE_WHISPER=true` and redeploy Render after adding the key.

**Instagram likes/comments still N/A**  
Set `INSTAGRAM_COOKIES_FILE` on Render **and** `INSTAGRAM_COOKIE` on Vercel (see cookies section). Re-run Analyze after deploy — old analyses keep stale metadata.

**Instagram transcript empty**  
Set `APIFY_API_KEY` on Render (Apify → Settings → Integrations). Uses **`apify/instagram-scraper`** with `directUrls` for post metrics and comments. Caption is used as transcript text; Groq Whisper remains the fallback when caption is empty.

**Empty RAG answers**  
Add `OPENAI_API_KEY` for real embeddings; Groq-only uses hash fallback.

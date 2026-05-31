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
```

**Free instance notes (purple banner in Render):**
- Persistent disk is **not available** on Free — analyses reset on redeploy. Upgrade to Starter+ and mount `/data` for persistence.
- 512 MB RAM will **OOM** with Whisper. On Free, start with:
  ```env
  ENABLE_WHISPER=false
  ENABLE_VISUAL=false
  ```
  YouTube comparisons still work; Instagram Whisper/visual need a paid plan (≥4 GB RAM).

**Paid plan:** add a **persistent disk** mounted at `/data` (≥1 GB), then enable Whisper/visual:

```env
ENABLE_WHISPER=true
WHISPER_MODEL=base
ENABLE_VISUAL=true
ENABLE_OCR=true
OPENAI_API_KEY=sk-...          # optional, for embeddings
```

9. **Plan:** Starter or Standard (Free works for YouTube-only demos with Whisper disabled).

### Local Docker test

```bash
cd backend
docker build -t vanadium-api .
docker run --rm -p 8000:8000 \
  -v vanadium-data:/data \
  -e GROQ_API_KEY=gsk_... \
  -e LLM_PROVIDER=groq \
  -e CORS_ORIGINS=http://localhost:3000 \
  -e ENABLE_WHISPER=false \
  -e ENABLE_VISUAL=false \
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
| `ENABLE_WHISPER` | For IG audio | `true` + ffmpeg in image |
| `ENABLE_VISUAL` | For frame analysis | `true` |
| `INSTAGRAM_COOKIES_FILE` | Often for IG | Netscape cookies file path |

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

**Instagram views = 0**  
Set `INSTAGRAM_COOKIES_FILE` with exported session cookies.

**Empty RAG answers**  
Add `OPENAI_API_KEY` for real embeddings; Groq-only uses hash fallback.
